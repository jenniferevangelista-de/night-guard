"""Night Guard detector: reads a chat with one contact and returns risk signals.

Everything runs locally through Ollama. No chat text leaves the computer.
"""

import json
import os
import re
import time

import httpx

from .signals import HIGH_ALONE, SIGNAL_IDS, SIGNALS

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
MODEL = os.environ.get("NG_MODEL", "gemma4:e4b")

URL_RE = re.compile(r"(https?://\S+|www\.\S+|\b[\w-]+\.(?:com|net|org|io|gg|xyz|live|site|online|top|ru)\S*)", re.I)

SCHEMA = {
    "type": "object",
    "properties": {
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "enum": SIGNAL_IDS},
                    "message_index": {"type": "integer"},
                    "quote": {"type": "string"},
                },
                "required": ["id", "message_index", "quote"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["signals", "summary"],
}

SYSTEM = """You are Night Guard, a child-safety classifier that runs on a child's own computer.
You read a chat between a child (marked CHILD) and an online contact (marked CONTACT).
Find ONLY risk signals sent by the CONTACT. Never flag the child's own messages.

Signal ids:
- secrecy: asks the child to hide the chat or anything from parents/family ("don't tell", "our secret", "delete this").
- platform_move: pushes to continue on another app or private channel (WhatsApp, Snap, Telegram, Discord DM, phone number).
- personal_info: asks for real name, school, address, city, phone, social profiles.
- age_probe: asks age, grade, or whether the child is alone / parents are home.
- photo_request: asks for a photo, selfie, video, or camera call of the child.
- gift_offer: offers free currency, items, skins, gift cards or money.
- credential_request: asks for password, login code, 2FA code, or account access.
- suspicious_link: sends a link promising rewards or asking to log in.
- meet_offline: suggests meeting in person.
- pressure: guilt-trips, insists after a no, threatens, or creates urgency.
- isolation: tries to separate the child from parents/friends ("only I understand you").

Rules:
- Normal gaming talk (strategies, trading in-game items fairly, friendly jokes, "gg", "add me in the game") is NOT a signal.
- Asking to play together in the same game is NOT platform_move.
- Be precise: only flag what is actually written. If nothing is risky, return an empty list.
- message_index is the [number] of the message. quote is the exact short phrase.
- summary: one neutral sentence in English describing what happened (no drama)."""


def _format_chat(messages):
    lines = []
    for i, m in enumerate(messages):
        who = "CHILD" if m.get("from") == "me" else "CONTACT"
        lines.append(f"[{i}] {who}: {m.get('text', '')}")
    return "\n".join(lines)


def _call_model(messages, timeout=120):
    payload = {
        "model": MODEL,
        "stream": False,
        "format": SCHEMA,
        "think": False,
        "options": {"temperature": 0, "num_ctx": 4096},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": "Chat:\n" + _format_chat(messages) + "\n\nReturn the JSON."},
        ],
    }
    r = httpx.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=timeout)
    r.raise_for_status()
    return json.loads(r.json()["message"]["content"])


def severity(signal_ids):
    """Turn a set of signals into none / low / medium / high."""
    ids = set(signal_ids)
    if not ids:
        return "none"
    score = sum(SIGNALS[s]["weight"] for s in ids)
    if ids & HIGH_ALONE or ("secrecy" in ids and len(ids) > 1) or score >= 5:
        return "high"
    if score >= 3:
        return "medium"
    return "low"


def analyze(messages, lang="en"):
    """Analyze one conversation. Returns a dict ready for the UI."""
    t0 = time.time()
    raw = _call_model(messages)
    res = postprocess(raw, messages, lang)
    res["latency_s"] = round(time.time() - t0, 2)
    return res


def postprocess(raw, messages, lang="en", model=MODEL):
    """Clean the model's JSON into the UI/eval result (shared with other backends)."""
    found = {}
    for s in raw.get("signals", []):
        sid = s.get("id")
        idx = s.get("message_index", -1)
        if sid not in SIGNALS:
            continue
        # Drop anything the model attributed to the child's own messages.
        if 0 <= idx < len(messages) and messages[idx].get("from") == "me":
            continue
        found.setdefault(sid, {"id": sid, "message_index": idx, "quote": s.get("quote", "")})

    links = []
    for i, m in enumerate(messages):
        if m.get("from") != "me":
            for u in URL_RE.findall(m.get("text", "")):
                links.append({"url": u, "message_index": i})

    sigs = list(found.values())
    for s in sigs:
        meta = SIGNALS[s["id"]]
        s["label"] = meta["label"].get(lang, meta["label"]["en"])
        s["lesson"] = meta["lesson"].get(lang, meta["lesson"]["en"])

    sev = severity(found.keys())
    return {
        "severity": sev,
        "signals": sigs,
        "links": links,
        "summary": raw.get("summary", ""),
        "notify_family": sev == "high",
        "model": model,
    }
