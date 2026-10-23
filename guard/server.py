"""Local Night Guard server. Run:  .venv\\Scripts\\python -m uvicorn guard.server:app --port 8765"""

import json
import re
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .detector import MODEL, analyze
from .helper import draft_help

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = json.loads((Path(__file__).parent / "scenarios.json").read_text(encoding="utf-8"))
ME_PREFIX = re.compile(r"^\s*(me|eu|i|euzinho)\s*[:\-]\s*", re.I)
NAME_PREFIX = re.compile(r"^\s*([^:]{1,30}):\s*(.*)$")

app = FastAPI(title="Night Guard")


class AnalyzeReq(BaseModel):
    text: str | None = None          # pasted chat, one message per line
    messages: list[dict] | None = None
    lang: str = "en"


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
        out.append({"from": "them", "text": (m.group(2) if m else line).strip()})
    return out


@app.get("/api/health")
def health():
    return {"ok": True, "model": MODEL, "runs": "locally via Ollama"}


@app.post("/api/analyze")
def api_analyze(req: AnalyzeReq):
    msgs = req.messages if req.messages else parse_paste(req.text or "")
    if not msgs:
        return {"severity": "none", "signals": [], "links": [], "summary": "", "messages": []}
    res = analyze(msgs, lang=req.lang)
    res["messages"] = msgs
    return res


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
