"""Local Night Guard server. Run:  .venv\\Scripts\\python -m uvicorn guard.server:app --port 8765"""

import json
import os
import re
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Literal

from pydantic import BaseModel, Field

from .detector import BACKEND, MODEL, analyze, _format_chat
from .family import (APPS, DEFAULT_RULES, apply_rules, contacts_across_apps, get_alerts, get_rules,
                     set_rules)
from . import notify
from .helper import draft_help
from .demo_budget import DemoBudget

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = json.loads((Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
ME_PREFIX = re.compile(r"^\s*(me|eu|i|euzinho)\s*[:\-]\s*", re.I)
NAME_PREFIX = re.compile(r"^\s*([^:]{1,30}):\s*(.*)$")

DEMO = BACKEND != "ollama"
_analysis_budget = DemoBudget(hourly=120, per_client=30, concurrent=2)
_link_budget = DemoBudget(hourly=30, per_client=10, concurrent=2)


def _deploy_info():
    """Which code and which model are actually running (evidence for reviewers; no secrets)."""
    import os
    commit = os.environ.get("RENDER_GIT_COMMIT", "")
    if not commit:
        try:
            commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True,
                                    timeout=5).stdout.strip()
        except Exception:
            commit = ""
    info = {"commit": commit[:12]}
    if BACKEND == "tinker":
        from .cloud import FT_PATH
        info["tinker_model"] = FT_PATH.split("tinker://")[-1].split(":")[0]  # run id, e.g. 34d43b69-... (v2)
    return info


DEPLOY = _deploy_info()

from .env import load_env  # noqa: E402
from . import telemetry  # noqa: E402

load_env()
telemetry.init()  # Sentry agent tracing, only if SENTRY_DSN is set; no chat content is sent

from . import auth  # noqa: E402  (reads Auth0 settings from .env, so it comes after load_env)

app = FastAPI(title="Night Guard")
if auth.ENABLED and not DEMO:
    from starlette.middleware.sessions import SessionMiddleware

    app.add_middleware(SessionMiddleware, secret_key=auth.SESSION_SECRET, same_site="lax", https_only=False)
auth.add_routes(app)
PARENTS_ONLY = [Depends(auth.require_parent)]


class Msg(BaseModel):
    """One chat message, validated before it ever reaches the model."""
    model_config = {"populate_by_name": True}
    from_: Literal["me", "them"] = Field(alias="from")
    text: str = Field(min_length=1, max_length=2000)
    name: str = Field(default="", max_length=60)

    def as_dict(self):
        return {"from": self.from_, "text": self.text, "name": self.name}


class AnalyzeReq(BaseModel):
    text: str | None = Field(default=None, max_length=4000)   # pasted chat, one message per line
    messages: list[Msg] | None = Field(default=None, max_length=60)
    lang: str = Field(default="en", max_length=12)
    app: str = Field(default="Other", max_length=60)
    family_rules: dict | None = None   # public demo only: the visitor's own rules


class HelpReq(BaseModel):
    quotes: list[str]
    who: str = "Mom"
    note: str = ""
    lang: str = "en"


def parse_paste(text):
    """'Me: hi' / 'Eu: oi' lines are the child; any other 'Name: ...' line is the contact."""
    out = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if ME_PREFIX.match(line):
            out.append({"from": "me", "text": ME_PREFIX.sub("", line).strip()})
            continue
        m = NAME_PREFIX.match(line)
        out.append({"from": "them", "name": m.group(1).strip() if m else "",
                    "text": (m.group(2) if m else line).strip()})
    return out


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL, "demo": BACKEND != "ollama", **DEPLOY,
            "voice": (ROOT / "web" / "audio" / "en").is_dir(),
            "runs": "locally via Ollama" if BACKEND == "ollama" else "public demo on Render + Tinker"}


@app.post("/api/analyze")
def api_analyze(req: AnalyzeReq, request: Request):
    msgs = [m.as_dict() for m in req.messages] if req.messages else parse_paste(req.text or "")
    if not msgs:
        return {"severity": "none", "signals": [], "links": [], "summary": "", "messages": []}
    # Bound the whole model input, including names and separators added by the
    # detector. This also covers the structured messages used by the live demo.
    if DEMO and (len(_format_chat(msgs)) + sum(len(m.get("name", "")) for m in msgs) > 4000):
        raise HTTPException(422, "The demo accepts at most 4,000 chat characters per check.")
    caller = request.client.host if request.client else "unknown"
    with _analysis_budget.reserve(caller) if DEMO else nullcontext():
        res = analyze(msgs, lang=req.lang)
    res["messages"] = msgs
    # The contact is whoever sent the flagged messages (not simply the first name in the chat:
    # in a group or game chat, a friend may have spoken first).
    flagged_names = [msgs[s["message_index"]].get("name", "") for s in res["signals"]
                     if isinstance(s.get("message_index"), int) and 0 <= s["message_index"] < len(msgs)]
    contact = next((n for n in flagged_names if n), "") or \
        next((m.get("name", "") for m in msgs if m.get("from") != "me" and m.get("name")), "")
    # Public demo: rules come from the visitor's browser and nothing is saved on the server.
    event = apply_rules(res, app=req.app, contact=contact,
                        rules=req.family_rules if DEMO else None, persist=not DEMO)
    res["family_event"] = event
    res["family_alert"] = event if event and event["shared"] else None
    if res["family_alert"] and not DEMO:
        notify.push_alert(res["family_alert"], lang=req.lang)  # phone push: risk type only, no chat
    return res


class NotifyReq(BaseModel):
    enabled: bool
    lang: str = "en"


@app.get("/api/family/notify", dependencies=PARENTS_ONLY)
def notify_get():
    if DEMO:
        return {"available": False}
    s = notify.get_settings()
    return {"available": True, "enabled": s.get("enabled", False), "topic": s["topic"]}


@app.post("/api/family/notify", dependencies=PARENTS_ONLY)
def notify_set(req: NotifyReq):
    if DEMO:
        raise HTTPException(403, "Phone alerts are only available in the family's local app.")
    s = notify.get_settings()
    s["enabled"] = req.enabled
    notify.save_settings(s)
    sent = notify.push_test(req.lang) if req.enabled else False
    return {"available": True, "enabled": s["enabled"], "topic": s["topic"], "test_sent": sent}


@app.get("/api/family/rules")
def api_get_rules():
    return {"rules": DEFAULT_RULES if DEMO else get_rules(), "apps": APPS, "demo": DEMO}


@app.post("/api/family/rules", dependencies=PARENTS_ONLY)
def api_set_rules(rules: dict):
    if DEMO:
        raise HTTPException(403, "The public demo keeps family rules in your browser only.")
    return {"rules": set_rules(rules)}


@app.get("/api/family/alerts", dependencies=PARENTS_ONLY)
def api_alerts():
    if DEMO:  # never expose one visitor's alerts to another
        return {"alerts": [], "cross_app_contacts": {}, "demo": True}
    return {"alerts": get_alerts(), "cross_app_contacts": contacts_across_apps()}


# ---- Screen guard (installed apps), local app only ----
_guard = {"proc": None, "app": None, "seen": 0.0}
# Same list as guard/screen_guard.py (not imported here: it needs Windows, and the demo runs on Linux).
SCREEN_APPS = ["Roblox", "Discord", "Minecraft", "Fortnite", "TikTok", "WhatsApp", "Instagram"]


class GuardStart(BaseModel):
    lang: str = "en"


@app.get("/api/guard/status")
def guard_status():
    if DEMO:
        return {"available": False}
    p = _guard["proc"]
    running = p is not None and p.poll() is None
    fresh = time.time() - _guard["seen"] < 15
    return {"available": True, "running": running, "watching": _guard["app"] if running and fresh else None,
            "watched_apps": SCREEN_APPS}


@app.post("/api/guard/start", dependencies=PARENTS_ONLY)
def guard_start(req: GuardStart, request: Request):
    if DEMO:
        raise HTTPException(403, "The screen guard runs only on the family's computer.")
    if _guard["proc"] is None or _guard["proc"].poll() is not None:
        server = f"http://127.0.0.1:{request.url.port or 80}"
        _guard["proc"] = subprocess.Popen(
            [sys.executable, "-m", "guard.screen_guard", "--server", server, "--lang", req.lang]
            + (["--demo-page"] if os.environ.get("NG_SCREEN_DEMO") == "1" else []),
            cwd=ROOT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return guard_status()


@app.post("/api/guard/stop", dependencies=PARENTS_ONLY)
def guard_stop():
    p = _guard["proc"]
    if p is not None and p.poll() is None:
        p.terminate()
    _guard["proc"], _guard["app"] = None, None
    return guard_status()


@app.post("/api/guard/heartbeat")
def guard_heartbeat(body: dict):
    _guard["app"], _guard["seen"] = body.get("app"), time.time()
    return {"ok": True}


# ---- Link inspector (Browserbase + SerpApi): only the link leaves the computer, never the chat ----
_link_calls = []


class LinkReq(BaseModel):
    url: str = Field(min_length=3, max_length=500)
    lang: str = "en"


@app.get("/api/link/status")
def link_status():
    from . import link_check
    return link_check.enabled()


@app.post("/api/link/check")
def link_check_api(req: LinkReq, request: Request):
    from . import link_check
    on = link_check.enabled()
    if not any(on.values()):
        raise HTTPException(503, "Link inspector is not configured.")
    if DEMO:
        caller = request.client.host if request.client else "unknown"
        with _link_budget.reserve(caller):
            return link_check.check_link(req.url, req.lang)
    now = time.time()
    _link_calls[:] = [c for c in _link_calls if now - c < 3600]
    if len(_link_calls) >= 200:
        raise HTTPException(429, "Too many link checks right now, try again later.")
    _link_calls.append(now)
    return link_check.check_link(req.url, req.lang)


@app.get("/demo/free-gems")
def fake_gems_page():
    """A fictional look-alike scam page for the demo (BlockQuest is made up). It sends nothing anywhere."""
    return FileResponse(ROOT / "web" / "demo_free_gems.html")


@app.get("/api/scenarios")
def api_scenarios():
    return SCENARIOS


@app.post("/api/help")
def api_help(req: HelpReq):
    return {"message": draft_help(req.quotes, req.who, req.note, req.lang)}


@app.get("/", name="index")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/game")
def game():
    """Live demo: a fictional game chat where Night Guard reacts on its own."""
    return FileResponse(ROOT / "web" / "game.html")


app.mount("/web", StaticFiles(directory=ROOT / "web"), name="web")
