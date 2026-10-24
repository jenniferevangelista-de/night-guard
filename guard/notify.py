"""Phone notification for the family (local app only), through ntfy (https://ntfy.sh, free, no account).

The push says only the risk level, the app and the kind of risk. Never the chat, the quote or a name.
Details and "what to do now" stay in the Parents tab on the family's computer.
ntfy topics are public by name, so a long random topic is generated and kept in data/ (git-ignored).
"""

import json
import secrets
from pathlib import Path

import httpx

SETTINGS = Path(__file__).resolve().parent.parent / "data" / "notify.json"
TEXT = {
    "en": {"title": "Night Guard", "sev": {"high": "High risk", "medium": "Medium risk", "low": "Low risk"},
           "open": "Open the Parents tab on the family computer for what to do now.", "test": "Test: phone alerts are working."},
    "pt": {"title": "Guarda Noturno", "sev": {"high": "Risco alto", "medium": "Risco médio", "low": "Risco baixo"},
           "open": "Abra a aba dos Pais no computador da família para ver o que fazer.", "test": "Teste: os avisos no celular estão funcionando."},
}


def get_settings():
    try:
        s = json.loads(SETTINGS.read_text(encoding="utf-8"))
    except Exception:
        s = {}
    if not s.get("topic"):
        s = {"topic": "nightguard-" + secrets.token_hex(8), "enabled": False}
        save_settings(s)
    return s


def save_settings(s):
    SETTINGS.parent.mkdir(exist_ok=True)
    SETTINGS.write_text(json.dumps(s), encoding="utf-8")


def _push(title, body, priority, tags):
    s = get_settings()
    if not s.get("enabled"):
        return False
    try:
        r = httpx.post("https://ntfy.sh/", timeout=10, json={
            "topic": s["topic"], "title": title, "message": body, "priority": priority, "tags": [tags]})
        return r.status_code == 200
    except Exception:
        return False


def push_alert(event, lang="en"):
    """Report provider acceptance, never pretend a parent received or read an alert.

    The bounded request returns disabled/accepted/failed. No conversation, quote
    or contact name is sent. Provider acceptance is not a delivery receipt.
    """
    if not get_settings().get("enabled"):
        return "disabled"
    t = TEXT.get(lang, TEXT["en"])
    kinds = " + ".join(s["label"] for s in event["signals"])
    body = f"{t['sev'].get(event['severity'], event['severity'])} · {event['app']} · {kinds}\n{t['open']}"
    prio = 5 if event["severity"] == "high" else 3
    return "accepted" if _push(f"🌙 {t['title']}", body, prio, "shield") else "failed"


def push_test(lang="en"):
    t = TEXT.get(lang, TEXT["en"])
    return _push(f"🌙 {t['title']}", t["test"], 3, "shield")
