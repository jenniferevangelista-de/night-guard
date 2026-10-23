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

WATCHED = {  # window title keyword -> app name used in alerts
    "roblox": "Roblox", "discord": "Discord", "tiktok": "TikTok", "whatsapp": "WhatsApp",
    "instagram": "Instagram", "minecraft": "Minecraft", "fortnite": "Fortnite",
    "blockquest": "Roblox",  # the fictional demo game
}
VISION_MODEL = "gemma4:e4b"
READ_PROMPT = """This is a screenshot of a game or chat app.
Read ONLY the chat messages that are visible (player chat, DMs, comments). Ignore menus, buttons and game text.Return them oldest first as JSON: {"messages":[{"name":"sender name","text":"message text"}]}.
Copy the text exactly. If there is no chat, return {"messages":[]}."""
SCHEMA = {"type": "object", "properties": {"messages": {"type": "array", "items": {
    "type": "object", "properties": {"name": {"type": "string"}, "text": {"type": "string"}},
    "required": ["name", "text"]}}}, "required": ["messages"]}

TXT = {
    "en": {"on": "🛡️ Guard on", "watch": "watching {app}", "ok": "Got it", "fam": "Your family will know about this. You're not in trouble.",
           "title": {"high": "🛑 Stop! This could be dangerous", "medium": "⚠️ Careful", "low": "⚠️ Heads up"}},
    "pt": {"on": "🛡️ Guarda ligado", "watch": "vigiando {app}", "ok": "Entendi", "fam": "Sua família vai ficar sabendo. Você não está encrencado.",
           "title": {"high": "🛑 Pare! Isso pode ser perigoso", "medium": "⚠️ Cuidado", "low": "⚠️ Atenção"}},
}

user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixel coordinates on scaled screens
except Exception:
    user32.SetProcessDPIAware()


def foreground_window():
    """(title, (left, top, right, bottom)) of the window in front."""
    hwnd = user32.GetForegroundWindow()
    n = user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(n + 1)
    user32.GetWindowTextW(hwnd, buf, n + 1)
    rect = wintypes.RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    return buf.value, (rect.left, rect.top, rect.right, rect.bottom)


def watched_app(title):
    low = title.lower()
    if "night guard" in low:
        return None
    return next((app for key, app in WATCHED.items() if key in low), None)


def read_chat(bbox):
    """Screenshot the window in memory and let local Gemma read the chat. Nothing is saved."""
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


class Guard:
    def __init__(self, server, lang, me, interval):
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
                title, bbox = foreground_window()
                app = watched_app(title)
                self.q.put(("status", app))
                try:  # tell the local server what we're watching (never the title or content)
                    httpx.post(f"{self.server}/api/guard/heartbeat", json={"app": app}, timeout=3)
                except Exception:
                    pass
                if app and bbox[2] - bbox[0] > 200:
                    t0 = time.time()
                    msgs = read_chat(bbox)
                    read_s = time.time() - t0
                    if msgs and msgs != self.last.get(app):
                        self.last[app] = msgs
                        convo = [{"from": "me" if m["name"].lower() in SELF_NAMES or (self.me and m["name"].lower() == self.me) else "them",
                                  "name": m["name"], "text": m["text"]} for m in msgs]
                        if convo[-1]["from"] == "them":
                            r = httpx.post(f"{self.server}/api/analyze", json={"messages": convo, "lang": self.lang, "app": app}, timeout=180)
                            res = r.json()
                            print(f"[screen-guard] {app}: read {len(msgs)} msgs in {read_s:.1f}s -> {res.get('severity')}", flush=True)
                            if res.get("severity") in ("low", "medium", "high"):
                                self.q.put(("alert", app, res))
            except Exception as e:
                print(f"[screen-guard] skipped: {type(e).__name__}", flush=True)  # never prints chat content
            time.sleep(self.interval)

    def pump(self):
        while not self.q.empty():
            item = self.q.get()
            if item[0] == "status":
                self.badge.config(text=self.t["on"] + (f" · {self.t['watch'].format(app=item[1])}" if item[1] else ""))
            elif item[0] == "alert":
                self.show(*item[1:])
        self.root.after(300, self.pump)

    def show(self, app, res):
        # Same message + tactic is shown once; a new message with the same tactic (someone
        # insisting) is escalation and is shown again.
        k = lambda s: (app, s["id"], (s.get("quote") or "").strip().lower())
        fresh = [s for s in res["signals"] if k(s) not in self.seen]
        if not fresh:
            return
        self.seen.update(k(s) for s in fresh)
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

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Night Guard screen guard (local only)")
    ap.add_argument("--server", default="http://localhost:8765")
    ap.add_argument("--lang", default="en", choices=["en", "pt"])
    ap.add_argument("--me", default="", help="the child's username, so their own messages aren't analyzed as the contact's")
    ap.add_argument("--interval", type=float, default=5.0, help="seconds between checks")
    a = ap.parse_args()
    Guard(a.server, a.lang, a.me, a.interval).run()
