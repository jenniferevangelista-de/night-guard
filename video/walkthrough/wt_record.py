"""Record a real walkthrough of the local Night Guard app (Gemma via Ollama), with a visible cursor.

  python video/walkthrough/wt_record.py pt
Writes rec_<lang>/*.webm, events_<lang>.json (segment starts and spoken-warning times) and
docs/screens/<lang>/*.png (one screenshot per feature).
Every chat used here is fictional. The model failure in the last segment is simulated (request blocked).
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = "http://127.0.0.1:8765"
LANG = sys.argv[1] if len(sys.argv) > 1 else "pt"
NARR = {n["id"]: n["dur"] for n in json.loads((HERE / f"narr_{LANG}.json").read_text(encoding="utf-8"))}
SHOTS = ROOT / "docs" / "screens" / LANG
SHOTS.mkdir(parents=True, exist_ok=True)
REC = HERE / f"rec_{LANG}"
REC.mkdir(exist_ok=True)
for f in REC.glob("*.webm"):
    f.unlink()

CURSOR = """
(() => {
  const mk = () => {
    if (document.getElementById('__cur')) return;
    const c = document.createElement('div'); c.id = '__cur';
    c.style.cssText = 'position:fixed;z-index:2147483647;left:0;top:0;width:22px;height:22px;margin:-3px 0 0 -3px;pointer-events:none;' +
      'background:url("data:image/svg+xml;utf8,<svg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 24 24%27><path d=%27M3 2l7 19 2.5-7.5L20 11z%27 fill=%27white%27 stroke=%27black%27 stroke-width=%271.6%27/></svg>") no-repeat;';
    document.documentElement.appendChild(c);
    addEventListener('mousemove', e => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; }, true);
    addEventListener('mousedown', e => {
      const r = document.createElement('div');
      r.style.cssText = `position:fixed;z-index:2147483646;left:${e.clientX - 18}px;top:${e.clientY - 18}px;width:36px;height:36px;border-radius:50%;` +
        'border:3px solid #ffd36e;pointer-events:none;transition:all .45s ease-out;opacity:1';
      document.documentElement.appendChild(r);
      requestAnimationFrame(() => { r.style.transform = 'scale(1.8)'; r.style.opacity = '0'; });
      setTimeout(() => r.remove(), 500);
    }, true);
  };
  if (document.readyState === 'loading') addEventListener('DOMContentLoaded', mk); else mk();
  // remember when a spoken warning starts (the recording has no sound; the builder adds the same MP3 there)
  window.__audio = [];
  const A = window.Audio;
  window.Audio = function (src) { const a = new A(src); const p = a.play.bind(a);
    a.play = () => { window.__audio.push({ src: String(src), t: Date.now() }); a.muted = true; return p(); }; return a; };
})();
"""

events = {"segments": [], "audio": []}


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(channel="chrome", headless=True)
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, device_scale_factor=1)
        ctx.add_init_script(CURSOR)
        page = ctx.new_page()
        t0 = time.time()
        frames = []                                       # (seconds since t0, jpeg bytes) from Chrome's own screencast
        cdp = ctx.new_cdp_session(page)

        def on_frame(ev):
            frames.append((ev["metadata"]["timestamp"], ev["data"]))
            try: cdp.send("Page.screencastFrameAck", {"sessionId": ev["sessionId"]})
            except Exception: pass
        cdp.on("Page.screencastFrame", on_frame)

        def cast(on=True):
            cdp.send("Page.startScreencast" if on else "Page.stopScreencast",
                     {"format": "jpeg", "quality": 85, "maxWidth": 1280, "maxHeight": 800, "everyNthFrame": 1} if on else {})

        def sleep(sec):
            page.wait_for_timeout(int(sec * 1000))   # keeps Playwright pumping screencast events
        mouse = {"x": 640, "y": 400}

        def now():
            return time.time() - t0

        def move_to(sel, steps=18):
            loc = page.locator(sel).first
            loc.scroll_into_view_if_needed()
            b = loc.bounding_box()
            x, y = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
            page.mouse.move(x, y, steps=steps); mouse.update(x=x, y=y)
            return loc

        def click(sel, pause=0.25):
            move_to(sel); sleep(0.12)
            page.mouse.down(); page.mouse.up(); sleep(pause)

        def scroll_to(sel):
            page.locator(sel).first.evaluate("e => e.scrollIntoView({behavior:'smooth', block:'center'})"); sleep(0.6)

        def shot(name):
            page.screenshot(path=str(SHOTS / f"{name}.png"))

        def collect_audio():
            for a in page.evaluate("window.__audio || []"):
                events["audio"].append({"src": a["src"], "t": a["t"] / 1000 - t0})
            page.evaluate("window.__audio = []")

        class seg:
            def __init__(self, sid): self.sid = sid
            def __enter__(self):
                self.start = now(); events["segments"].append({"id": self.sid, "start": round(self.start, 2)}); return self
            def __exit__(self, *a):
                rest = NARR[self.sid] + 0.35 - (now() - self.start)
                if rest > 0: sleep(rest)

        page.goto(f"{BASE}/?lang={LANG}"); page.wait_for_selector("#gbToggle"); cast(True); sleep(0.8)

        with seg("home"):
            page.mouse.move(640, 300, steps=10)
            move_to("#gbar"); sleep(1.2); shot("01_home_bar")
            click("#gbToggle", 1.6); shot("02_guard_on")
            click("#gbToggle", 1.0)

        with seg("check"):
            click('nav button[data-p="check"]', 0.3)
            click('.chip[data-ex="secret"]', 0.5)
            shot("03_paste_example")
            click("#analyzeBtn", 0.2)
            page.wait_for_selector("#result [data-a]", timeout=90000); sleep(0.4)

        with seg("result"):
            scroll_to("#result"); shot("04_quiz_first")
            click("#result [data-a]", 0.8)
            scroll_to("#result .sig"); sleep(0.6); shot("05_result_kid_words")
            if page.locator("#result [data-say]").count():
                click("#result [data-say]", 0.5)
            scroll_to("#toTell"); sleep(0.6)
            collect_audio()

        with seg("tell"):
            click("#toTell", 0.8)
            click("#draftBtn", 0.8)
            scroll_to("#draftOut"); shot("06_tell_someone_message")

        with seg("benign"):
            page.evaluate("window.scrollTo({top:0,behavior:'smooth'})"); sleep(0.3)
            click('nav button[data-p="check"]', 0.4)
            page.evaluate("window.scrollTo({top:0,behavior:'smooth'})"); sleep(0.5)
            click('.chip[data-ex="normal"]', 0.3)
            click("#analyzeBtn", 0.2)
            page.wait_for_selector("#result [data-a], #result .verdict", timeout=90000); sleep(0.3)
            if page.locator("#result [data-a]").count():
                scroll_to("#result"); click("#result [data-a]", 0.6)
            scroll_to("#result"); shot("07_normal_chat_no_alarm")

        with seg("practice"):
            page.evaluate("window.scrollTo({top:0,behavior:'smooth'})"); sleep(0.3)
            click('nav button[data-p="practice"]', 0.6); shot("08_practice_levels")
            click("#scnList .scn", 0.8)
            scroll_to("#scnPlay")
            click('#scnPlay .opt[data-c="ask"]', 1.2)
            scroll_to("#fb"); shot("09_practice_medal")
            page.evaluate("window.scrollTo({top:0,behavior:'smooth'})"); sleep(0.8)

        with seg("parents"):
            page.evaluate("window.scrollTo({top:0,behavior:'smooth'})"); sleep(0.3)
            click('nav button[data-p="family"]', 0.8); shot("10_parents_area")
            scroll_to("#alerts"); sleep(1.4); shot("11_parent_alerts")
            scroll_to("#rules"); sleep(1.2); shot("12_family_rules")

        collect_audio()
        page.goto(f"{BASE}/game?lang={LANG}"); page.wait_for_selector("#play"); sleep(0.6)

        with seg("game"):
            click("#play", 0.2)
            page.wait_for_selector(".ng-pop", timeout=120000); sleep(0.4)
            # keep watching until the warning that also tells the family (it then says "tell your parents")
            try:
                page.wait_for_selector(".ng-pop .ng-fam", timeout=90000); sleep(0.4)
            except Exception:
                pass
            shot("13_live_game_warning")
            collect_audio()
            mine = [a for a in events["audio"] if a["t"] > self_start(events, "game")]
            if mine:
                import subprocess as sp
                last = mine[-1]
                d = float(sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                  str(ROOT / last["src"].lstrip("/"))], capture_output=True, text=True).stdout or 0)
                end = last["t"] + d + 0.6
                while now() < end:
                    sleep(0.2); collect_audio()
                    mine = [a for a in events["audio"] if a["t"] > self_start(events, "game")]
                    if mine[-1] is not last:
                        last = mine[-1]
                        d = float(sp.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                          str(ROOT / last["src"].lstrip("/"))], capture_output=True, text=True).stdout or 0)
                        end = last["t"] + d + 0.6

        with seg("off"):
            page.locator(".ng-pop .ng-a").first.click() if page.locator(".ng-pop .ng-a").count() else None
            click("#gToggle", 0.8); shot("14_guard_off")
            page.evaluate("add('Alex_17', 'u still there? dont tell anyone ok')"); sleep(2.0)

        with seg("fault"):
            page.route("**/api/analyze", lambda r: r.abort())                     # simulated model failure
            click("#gToggle", 0.6)
            page.evaluate("add('Alex_17', 'u there?')")
            page.wait_for_selector(".ng-badge.ng-paused", timeout=20000); sleep(0.6)
            move_to(".ng-badge"); shot("15_guard_paused_simulated_failure")
            page.unroute("**/api/analyze")

        page.goto(f"{BASE}/?lang={LANG}"); page.wait_for_selector("#gbToggle")
        with seg("end"):
            page.mouse.move(640, 260, steps=10); sleep(0.5)

        collect_audio()
        cast(False); sleep(0.3)
        ctx.close(); browser.close()
    # frames -> video with each frame held until the next one (variable frame timing)
    import base64, subprocess
    wall0 = frames[0][0]
    events["frames_t0"] = round(wall0 - t0, 3)
    lst = []
    for i, (ts, data) in enumerate(frames):
        f = REC / f"f{i:05d}.jpg"; f.write_bytes(base64.b64decode(data))
        nxt = frames[i + 1][0] if i + 1 < len(frames) else ts + 1.0
        lst.append(f"file '{f.name}'\nduration {max(0.001, nxt - ts):.4f}")
    lst.append(f"file '{f.name}'")
    (REC / "frames.txt").write_text("\n".join(lst), encoding="utf-8")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(REC / "frames.txt"),
                    "-vf", "fps=24,format=yuv420p", "-c:v", "libx264", "-crf", "18", str(HERE / f"rec_{LANG}.mp4")], check=True)
    for f in REC.glob("f*.jpg"): f.unlink()
    events["video"] = f"rec_{LANG}.mp4"
    (HERE / f"events_{LANG}.json").write_text(json.dumps(events, indent=2), encoding="utf-8")
    print(json.dumps(events, indent=1)[:1500])


def self_start(ev, sid):
    return next(s["start"] for s in ev["segments"] if s["id"] == sid)


if __name__ == "__main__":
    main()
