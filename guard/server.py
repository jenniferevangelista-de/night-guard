"""Local Night Guard server. Run:  .venv\\Scripts\\python -m uvicorn guard.server:app --port 8765"""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .detector import BACKEND, MODEL, analyze
from .family import (APPS, DEFAULT_RULES, apply_rules, contacts_across_apps, get_alerts, get_rules,
                     set_rules)
from . import notify
from .helper import draft_help

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = json.loads((Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
ME_PREFIX = re.compile(r"^\s*(me|eu|i|euzinho)\s*[:\-]\s*", re.I)
NAME_PREFIX = re.compile(r"^\s*([^:]{1,30}):\s*(.*)$")

DEMO = BACKEND != "ollama"

app = FastAPI(title="Night Guard")


class AnalyzeReq(BaseModel):
    text: str | None = Field(default=None, max_length=4000)   # pasted chat, one message per line
    messages: list[dict] | None = Field(default=None, max_length=60)
    lang: str = "en"
    app: str = "Other"
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
    return {"ok": True, "model": MODEL, "demo": BACKEND != "ollama",
            "runs": "locally via Ollama" if BACKEND == "ollama" else "public demo on Render + Tinker"}


@app.post("/api/analyze")
def api_analyze(req: AnalyzeReq):
    msgs = req.messages if req.messages else parse_paste(req.text or "")
    if not msgs:
        return {"severity": "none", "signals": [], "links": [], "summary": "", "messages": []}
    res = analyze(msgs, lang=req.lang)
    res["messages"] = msgs
    contact = next((m.get("name", "") for m in msgs if m.get("from") != "me" and m.get("name")), "")
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


@app.get("/api/family/notify")
def notify_get():
    if DEMO:
        return {"available": False}
    s = notify.get_settings()
    return {"available": True, "enabled": s.get("enabled", False), "topic": s["topic"]}


@app.post("/api/family/notify")
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


@app.post("/api/family/rules")
def api_set_rules(rules: dict):
    if DEMO:
        raise HTTPException(403, "The public demo keeps family rules in your browser only.")
    return {"rules": set_rules(rules)}


@app.get("/api/family/alerts")
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


@app.post("/api/guard/start")
def guard_start(req: GuardStart, request: Request):
    if DEMO:
        raise HTTPException(403, "The screen guard runs only on the family's computer.")
    if _guard["proc"] is None or _guard["proc"].poll() is not None:
        server = f"http://127.0.0.1:{request.url.port or 80}"
        _guard["proc"] = subprocess.Popen(
            [sys.executable, "-m", "guard.screen_guard", "--server", server, "--lang", req.lang],
            cwd=ROOT, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return guard_status()


@app.post("/api/guard/stop")
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


@app.get("/api/scenarios")
def api_scenarios():
    return SCENARIOS


@app.post("/api/help")
def api_help(req: HelpReq):
    return {"message": draft_help(req.quotes, req.who, req.note, req.lang)}


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


@app.get("/game")
def game():
    """Live demo: a fictional game chat where Night Guard reacts on its own."""
    return FileResponse(ROOT / "web" / "game.html")


app.mount("/web", StaticFiles(directory=ROOT / "web"), name="web")
