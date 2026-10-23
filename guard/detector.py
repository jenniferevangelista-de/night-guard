"""Night Guard detector: reads a chat with one contact and returns risk signals.

By default everything runs locally through Ollama + Gemma: no chat text leaves
the computer. NG_BACKEND=tinker is only for the public demo (fictional examples),
where the Tinker fine-tuned Qwen3-8B is used instead.
"""

import json
import os
import re
import time

import httpx

from . import telemetry
from .signals import HIGH_ALONE, PARENT_STEPS, SIGNAL_IDS, SIGNALS

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
BACKEND = os.environ.get("NG_BACKEND", "ollama")
MODEL = os.environ.get("NG_MODEL", "gemma4:e4b") if BACKEND == "ollama" else "qwen3-8b + Tinker LoRA"

# Two narrow tactics are easy to over-match (a classmate's new account, a compliment on a build),
# so they only count when the chat actually contains the tactic's own words.
EVIDENCE = {
    "returning_after_block": re.compile(r"block|bloque|ignor|ban(ned|iu|ido)?\b|new account.*(since|because) you|me tirou|me exclu", re.I),
    "flattery": re.compile(r"matur|madur|for your age|pra (sua|tua) idade|para (sua|a sua) idade|older than|mais velh|nem parece", re.I),
}

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
- flattery: calls the child unusually mature or special for their age ("you're so mature for your age").
- returning_after_block: says they made a new account or came back after being blocked ("it's me, I made another account").
- sextortion: threatens to share pictures/secrets, or demands money, gift cards or more images ("pay or I post your pics").

Rules:
- Normal gaming talk (strategies, trading in-game items fairly, friendly jokes, "gg", "add me in the game") is NOT a signal.
- Asking to play together in the same game is NOT platform_move.
- A fair in-game trade or price ("50 coins for my sword") is NOT gift_offer; gift_offer is something given for free or "for you".
- returning_after_block ONLY when they say the child blocked/ignored them and they came back. A friend who lost a password and made a new account is NOT it.
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
    if BACKEND == "tinker":
        from . import cloud
        return cloud.classify(SYSTEM, "Chat:\n" + _format_chat(messages) + "\n\nReturn the JSON.")
    payload = {
        "model": MODEL,
        "stream": False,
        "format": SCHEMA,
        "think": False,
        "keep_alive": "30m",  # avoid a ~25 s cold reload between checks
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
    # Sentry agent trace: one agent run with one model call. Only counts and labels are recorded.
    with telemetry.transaction("night-guard.check", backend=BACKEND, n_messages=len(messages), lang=lang) as tx:
        with telemetry.span("gen_ai.chat", f"chat {MODEL}", model=MODEL, backend=BACKEND):
            try:
                raw = _call_model(messages)
            except Exception as e:
                raw = None  # model down or unreadable: reported as "couldn't analyze", never as "no risk"
                if telemetry.ENABLED:
                    telemetry.sentry_sdk.capture_message(f"model call failed: {type(e).__name__}", level="warning")
        with telemetry.span("night_guard.postprocess", "check evidence and severity"):
            res = postprocess(raw, messages, lang)
        res["latency_s"] = round(time.time() - t0, 2)
        if tx is not None:
            tx.set_data("severity", res["severity"])
            tx.set_data("signals", ",".join(s["id"] for s in res["signals"]))
            tx.set_data("latency_s", res["latency_s"])
    return res


def postprocess(raw, messages, lang="en", model=MODEL):
    """Clean the model's JSON into the UI/eval result (shared with other backends).

    An unreadable answer gives severity "unknown" (shown as "couldn't analyze"), never "none".
    Evidence is checked against the chat: the index must point to a contact message, and a
    quote that isn't in that message is replaced by the message itself.
    """
    if not isinstance(raw, dict) or not isinstance(raw.get("signals"), list):
        return {"severity": "unknown", "analysis_status": "error", "signals": [], "links": [],
                "summary": "", "notify_family": False, "model": model}

    def contact_msg(i):
        return type(i) is int and 0 <= i < len(messages) and messages[i].get("from") != "me"

    found = {}
    for s in raw["signals"]:
        if not isinstance(s, dict) or s.get("id") not in SIGNALS:
            continue
        sid, idx = s["id"], s.get("message_index")
        quote = s.get("quote") if isinstance(s.get("quote"), str) else ""
        if not contact_msg(idx):
            # Bad index: find the contact message that contains the quote, else drop it.
            idx = next((i for i, m in enumerate(messages)
                        if contact_msg(i) and quote.strip() and quote.strip() in m.get("text", "")), None)
            if idx is None:
                continue
        text = messages[idx].get("text", "")
        if not quote.strip() or quote.strip() not in text:
            quote = text  # the model paraphrased: show the real message instead
        need = EVIDENCE.get(sid)
        if need and not any(need.search(m.get("text", "")) for i, m in enumerate(messages) if contact_msg(i)):
            continue  # narrow tactics need their own evidence in the chat (see EVIDENCE)
        found.setdefault(sid, {"id": sid, "message_index": idx, "quote": quote.strip()})

    links = []
    for i, m in enumerate(messages):
        if m.get("from") != "me":
            for u in URL_RE.findall(m.get("text", "")):
                links.append({"url": u, "message_index": i})

    sigs = list(found.values())
    for s in sigs:
        meta = SIGNALS[s["id"]]
        for field in ("label", "lesson", "kid", "parent"):
            s[field] = meta[field].get(lang, meta[field]["en"])

    sev = severity(found.keys())
    return {
        "severity": sev,
        "analysis_status": "ok",
        "signals": sigs,
        "links": links,
        "summary": raw.get("summary", ""),
        "notify_family": sev == "high",
        "parent_steps": PARENT_STEPS.get(sev, {}).get(lang, PARENT_STEPS.get(sev, {}).get("en", [])),
        "model": model,
    }
