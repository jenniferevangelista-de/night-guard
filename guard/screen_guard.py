"""Night Guard screen guard (Windows): reads chats in installed apps, on this computer only.

Every few seconds, if the window in front is a watched app (Roblox, Discord, TikTok, WhatsApp,
Instagram...), it takes a screenshot of that window *in memory*, asks the local Gemma model
(vision) to read the chat messages, and sends the text to the local Night Guard server, which
runs the usual detector and family rules. The image is never written to disk and never leaves
the computer. Any other window (bank, email, school) is never captured.

Run (with the server and Ollama running):
    .venv\\Scripts\\python -m guard.screen_guard --server http://localhost:8765 --lang pt
"""

import argparse
import base64
import ctypes
import io
import json
import queue
import threading
import time
import tkinter as tk
from ctypes import wintypes

import httpx
from PIL import ImageGrab

from .detector import OLLAMA_URL

# A window is captured ONLY if the program that owns it is on this list (checked by the process
# executable, not by the window title, so "Bank statement - Discord receipts" in a browser is never
# captured). Web chats in a browser are covered by the extension, not by screenshots.
WATCHED_EXE = {
    "robloxplayerbeta.exe": "Roblox",
    "windows10universal.exe": "Roblox",           # Roblox from the Microsoft Store
    "discord.exe": "Discord",
    "minecraft.windows.exe": "Minecraft",         # Bedrock edition
    "fortniteclient-win64-shipping.exe": "Fortnite",
    "whatsapp.exe": "WhatsApp",
    "whatsapp.root.exe": "WhatsApp",
    "tiktok.exe": "TikTok",
}
JAVA_EXE = {"javaw.exe", "java.exe"}               # Minecraft Java: only with a Minecraft title
BROWSERS = {"chrome.exe", "msedge.exe", "firefox.exe", "brave.exe"}
DEMO_TITLE = "BlockQuest chat (Night Guard live demo)"   # the fictional demo game page, exact prefix
VISION_MODEL = "gemma4:e4b"
READ_PROMPT = """This is a screenshot of a game or chat app.
Read ONLY the chat messages that are visible (player chat, DMs, comments). Ignore menus, buttons and game text.
Return them oldest first as JSON: {"messages":[{"name":"sender name","text":"message text"}]}.
Copy the text exactly. If there is no chat, return {"messages":[]}."""
SCHEMA = {"type": "object", "properties": {"messages": {"type": "array", "items": {
    "type": "object", "properties": {"name": {"type": "string"}, "text": {"type": "string"}},
    "required": ["name", "text"]}}}, "required": ["messages"]}

TXT = {
    "en": {"on": "🛡️ Guard on", "watch": "watching {app}", "paused": "⚠️ Guard paused: can't analyze right now", "ok": "Got it", "fam": "Your family will know about this. You're not in trouble.",
           "title": {"high": "🛑 Stop! This could be dangerous", "medium": "⚠️ Careful", "low": "⚠️ Heads up"}},
    "pt": {"on": "🛡️ Guarda ligado", "watch": "vigiando {app}", "paused": "⚠️ Guarda pausado: não consigo analisar agora", "ok": "Entendi", "fam": "Sua família vai ficar sabendo. Você não está encrencado.",
           "title": {"high": "🛑 Pare! Isso pode ser perigoso", "medium": "⚠️ Cuidado", "low": "⚠️ Atenção"}},
}

AUDIO = __import__("pathlib").Path(__file__).resolve().parent.parent / "web" / "audio"
winmm = ctypes.windll.winmm


_voice_n = [0]


def play_voice(lang, *clip_ids):
    """Read the warning aloud with the pre-generated ElevenLabs MP3s, one after the other
    (e.g. the warning, then "family": tell your mom, dad or an adult you trust). Windows MCI, no extra packages."""
    _voice_n[0] += 1
    n = _voice_n[0]

    def run():
        for cid in clip_ids:
            if n != _voice_n[0]:
                return                       # a newer warning started: stop this one
            mp3 = AUDIO / lang / f"{cid}.mp3"
            if not mp3.exists():
                continue
            alias = f"ngvoice{n}"
            winmm.mciSendStringW(f'open "{mp3}" type mpegvideo alias {alias}', None, 0, 0)
            winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
            winmm.mciSendStringW(f"close {alias}", None, 0, 0)
    threading.Thread(target=run, daemon=True).start()


user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixel coordinates on scaled screens
except Exception:
    user32.SetProcessDPIAware()


kernel32 = ctypes.windll.kernel32


def process_exe(hwnd):
    """Executable file name (lower case) of the process that owns a window."""
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return ""
    try:
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return buf.value.replace("/", "\\").split("\\")[-1].lower()
        return ""
    finally:
        kernel32.CloseHandle(h)


def foreground_window():
    """(title, exe, (left, top, right, bottom)) of the window in front."""
    hwnd = user32.GetForegroundWindow()
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return hwnd, buf.value, process_exe(hwnd), (rect.left, rect.top, rect.right, rect.bottom)


def watched_app(title, exe, allow_demo_page=False):
    """Which watched app this window belongs to, or None. Decided by the owning process first."""
    exe = (exe or "").lower()
    if exe in WATCHED_EXE:
        return WATCHED_EXE[exe]
    if exe in JAVA_EXE and title.lower().startswith("minecraft"):
        return "Minecraft"
    if allow_demo_page and exe in BROWSERS and title.startswith(DEMO_TITLE):  # opt-in only (--demo-page)
        return "Roblox"  # fictional demo page only; real web chats go through the extension
    return None


def read_chat(hwnd, bbox):
    """Screenshot the window in memory and let local Gemma read the chat. Nothing is saved.
    Re-checks that the same watched window is still in front at the moment of capture."""
    if user32.GetForegroundWindow() != hwnd:
        return None
    return read_image(ImageGrab.grab(bbox=bbox, all_screens=True))


def read_image(img):
    img = img.convert("RGB")
    img.thumbnail((1280, 1280))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    b64 = base64.b64encode(buf.getvalue()).decode()
    del img, buf
    payload = {
        "model": VISION_MODEL, "stream": False, "format": SCHEMA, "think": False, "keep_alive": "30m",
        "options": {"temperature": 0, "num_ctx": 4096},
        "messages": [{"role": "user", "content": READ_PROMPT, "images": [b64]}],
    }
    r = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=120)
    r.raise_for_status()
    msgs = json.loads(r.json()["message"]["content"]).get("messages", [])
    out = []
    for m in msgs:
        if not isinstance(m, dict) or not str(m.get("text", "")).strip():
            continue
        m = {"name": str(m.get("name", "")).strip(), "text": str(m["text"]).strip()}
        if m["name"] == m["text"]:          # a cut-off line read as both name and text
            continue
        if any(m["text"] == o["text"] for o in out):   # repeated line (e.g. a quote inside a popup)
            continue
        out.append(m)
    return out[-12:]


SELF_NAMES = {"você", "voce", "you", "me", "eu"}  # how many chats label the child's own messages


def alert_key(app, signal, messages):
    """Identity of a shown warning: app + contact + tactic + exact words."""
    i = signal.get("message_index")
    name = messages[i].get("name", "") if isinstance(i, int) and 0 <= i < len(messages) else ""
    return (app, name.strip().lower(), signal["id"], (signal.get("quote") or "").strip().lower())


class Guard:
    def __init__(self, server, lang, me, interval, demo_page=False):
        self.demo_page = demo_page
        self.server, self.lang, self.me, self.interval = server.rstrip("/"), lang, me.lower(), interval
        self.t = TXT.get(lang, TXT["en"])
        self.q = queue.Queue()
        self.last = {}            # app -> last messages read
        self.seen = set()         # (app, signal) already shown
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.configure(bg="#161d3f")
        self.badge = tk.Label(self.root, text=self.t["on"], fg="#eef1ff", bg="#161d3f", font=("Segoe UI", 10, "bold"), padx=12, pady=6)
        self.badge.pack()
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"+{sw - self.root.winfo_width() - 20}+{sh - self.root.winfo_height() - 60}")
        threading.Thread(target=self.loop, daemon=True).start()
        self.root.after(300, self.pump)

    def loop(self):
        while True:
            try:
                hwnd, title, exe, bbox = foreground_window()
                app = watched_app(title, exe, self.demo_page)
                self.q.put(("status", app))
                try:  # tell the local server what we're watching (never the title or content)
                    httpx.post(f"{self.server}/api/guard/heartbeat", json={"app": app}, timeout=3)
                except Exception:
                    pass
                if app and bbox[2] - bbox[0] > 200:
                    t0 = time.time()
                    try:
                        msgs = read_chat(hwnd, bbox)
                    except Exception:
                        self.q.put(("degraded", True)); msgs = None
                    read_s = time.time() - t0
                    if msgs and msgs != self.last.get(app):
                        self.last[app] = msgs
                        convo = [{"from": "me" if m["name"].lower() in SELF_NAMES or (self.me and m["name"].lower() == self.me) else "them",
                                  "name": m["name"], "text": m["text"]} for m in msgs]
                        if convo[-1]["from"] == "them":
                            r = httpx.post(f"{self.server}/api/analyze", json={"messages": convo, "lang": self.lang, "app": app}, timeout=180)
                            res = r.json()
                            print(f"[screen-guard] {app}: read {len(msgs)} msgs in {read_s:.1f}s -> {res.get('severity')}", flush=True)
                            ok = res.get("analysis_status") in ("ok", "partial") and res.get("severity") != "unknown"
                            self.q.put(("degraded", not ok))
                            if ok and res.get("severity") in ("low", "medium", "high"):
                                self.q.put(("alert", app, res))
            except Exception as e:
                self.q.put(("degraded", True))
                print(f"[screen-guard] skipped: {type(e).__name__}", flush=True)  # never prints chat content
            time.sleep(self.interval)

    def pump(self):
        while not self.q.empty():
            item = self.q.get()
            if item[0] == "status":
                self.app_now = item[1]
                self._badge()
            elif item[0] == "degraded":
                self.degraded = item[1]  # analysis failing: say so instead of a calm "Guard on"
                self._badge()
            elif item[0] == "alert":
                self.show(*item[1:])
        self.root.after(300, self.pump)

    def _badge(self):
        if getattr(self, "degraded", False):
            self.badge.config(text=self.t["paused"], bg="#5a2330")
        else:
            app = getattr(self, "app_now", None)
            self.badge.config(text=self.t["on"] + (f" · {self.t['watch'].format(app=app)}" if app else ""), bg="#161d3f")

    def show(self, app, res):
        # Same contact + message + tactic is shown once; a new message (someone insisting) or the
        # same words from another contact are shown again.
        msgs = res.get("messages", [])
        fresh = [s for s in res["signals"] if alert_key(app, s, msgs) not in self.seen]
        if not fresh:
            return
        self.seen.update(alert_key(app, s, msgs) for s in fresh)
        high = res["severity"] == "high"
        win = tk.Toplevel(self.root)
        win.title("Night Guard")
        win.attributes("-topmost", True)
        win.configure(bg="#1d2550", highlightthickness=3, highlightbackground="#ff7a8a" if high else "#ffb35c")
        tk.Label(win, text=self.t["title"][res["severity"]], fg="#eef1ff", bg="#1d2550",
                 font=("Segoe UI", 14, "bold"), padx=16, pady=(10)).pack(anchor="w")
        for s in fresh:
            tk.Label(win, text=s.get("kid") or s["label"], fg="#eef1ff", bg="#1d2550", font=("Segoe UI", 11, "bold"),
                     wraplength=380, justify="left", padx=16).pack(anchor="w", pady=(4, 0))
            if s.get("quote"):
                tk.Label(win, text=f"“{s['quote']}”", fg="#a6aed6", bg="#1d2550", font=("Segoe UI", 10, "italic"),
                         wraplength=380, justify="left", padx=16).pack(anchor="w")
        if res.get("family_alert"):
            tk.Label(win, text="👨‍👩‍👧 " + self.t["fam"], fg="#ffd36e", bg="#1d2550", font=("Segoe UI", 10),
                     wraplength=380, justify="left", padx=16).pack(anchor="w", pady=(8, 0))
        tk.Button(win, text=self.t["ok"], command=win.destroy, bg="#ffd36e", fg="#2a2000",
                  font=("Segoe UI", 11, "bold"), relief="flat", padx=14, pady=4).pack(anchor="e", padx=16, pady=12)
        win.update_idletasks()
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"+{sw - win.winfo_width() - 20}+{sh - win.winfo_height() - 110}")
        win.lift()
        # Speak the most serious new warning (a kid may not be looking at the corner of the screen).
        loudest = next((s for s in fresh if str(s.get("kid", "")).startswith(("PERIGO", "DANGER"))), fresh[0])
        play_voice(self.lang, loudest["id"], *(["family"] if res.get("family_alert") else []))

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Night Guard screen guard (local only)")
    ap.add_argument("--server", default="http://localhost:8765")
    ap.add_argument("--lang", default="en", choices=["en", "pt"])
    ap.add_argument("--me", default="", help="the child's username, so their own messages aren't analyzed as the contact's")
    ap.add_argument("--interval", type=float, default=5.0, help="seconds between checks")
    ap.add_argument("--demo-page", action="store_true",
                    help="also watch the fictional BlockQuest demo page in a browser (off by default: a browser title proves nothing)")
    a = ap.parse_args()
    Guard(a.server, a.lang, a.me, a.interval, a.demo_page).run()
