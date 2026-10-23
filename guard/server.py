"""Local Night Guard server. Run:  .venv\\Scripts\\python -m uvicorn guard.server:app --port 8765"""

import json
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .detector import BACKEND, MODEL, analyze
from .family import APPS, apply_rules, contacts_across_apps, get_alerts, get_rules, set_rules
from .helper import draft_help

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = json.loads((Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
ME_PREFIX = re.compile(r"^\s*(me|eu|i|euzinho)\s*[:\-]\s*", re.I)
NAME_PREFIX = re.compile(r"^\s*([^:]{1,30}):\s*(.*)$")

app = FastAPI(title="Night Guard")


class AnalyzeReq(BaseModel):
    text: str | None = Field(default=None, max_length=4000)   # pasted chat, one message per line
    messages: list[dict] | None = Field(default=None, max_length=60)
    lang: str = "en"
    app: str = "Other"


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
    res["family_alert"] = apply_rules(res, app=req.app, contact=contact)
    return res


@app.get("/api/family/rules")
def api_get_rules():
    return {"rules": get_rules(), "apps": APPS}


@app.post("/api/family/rules")
def api_set_rules(rules: dict):
    return {"rules": set_rules(rules)}


@app.get("/api/family/alerts")
def api_alerts():
    return {"alerts": get_alerts(), "cross_app_contacts": contacts_across_apps()}


@app.get("/api/scenarios")
def api_scenarios():
    return SCENARIOS


@app.post("/api/help")
def api_help(req: HelpReq):
    return {"message": draft_help(req.quotes, req.who, req.note, req.lang)}


@app.get("/")
def index():
    return FileResponse(ROOT / "web" / "index.html")


app.mount("/web", StaticFiles(directory=ROOT / "web"), name="web")
