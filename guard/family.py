"""Family rules and the family alert inbox.

Kids don't always recognize a bad intention, so some signals are shared with the
family automatically. The child is always told when that happens (no secret
monitoring), and the family sees the risk type and the flagged phrase, never
the whole conversation. Same pattern as Instagram supervision and Discord
Family Center: who/what kind of risk, not full message content.

Everything is stored locally in data/ (git-ignored).
"""

import json
import time
import uuid
from pathlib import Path

from .signals import SIGNAL_IDS

DATA = Path(__file__).resolve().parent.parent / "data"
RULES_FILE = DATA / "family_rules.json"
ALERTS_FILE = DATA / "family_alerts.json"

# "tell": the family is told automatically. "child": the child decides.
DEFAULT_RULES = {s: "child" for s in SIGNAL_IDS} | {
    "photo_request": "tell",
    "meet_offline": "tell",
    "credential_request": "tell",
    "secrecy": "tell",
}
APPS = ["Roblox", "Minecraft", "Fortnite", "Discord", "TikTok", "Instagram", "WhatsApp", "Other"]


def _read(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write(path, data):
    DATA.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def get_rules():
    return DEFAULT_RULES | _read(RULES_FILE, {})


def set_rules(rules):
    clean = {k: v for k, v in rules.items() if k in SIGNAL_IDS and v in ("tell", "child")}
    _write(RULES_FILE, get_rules() | clean)
    return get_rules()


def apply_rules(result, app="Other", contact=""):
    """Log every flagged check on this computer; share with the family only what the rules say.

    Returns the shared alert, or None if this one stays with the child.
    """
    if not result["signals"]:
        return None
    rules = get_rules()
    triggered = [s for s in result["signals"] if rules.get(s["id"]) == "tell"]
    if result["severity"] == "high" and not triggered:
        triggered = list(result["signals"])  # serious combinations are always shared
    event = {
        "id": uuid.uuid4().hex[:8],
        "time": time.strftime("%Y-%m-%d %H:%M"),
        "app": app if app in APPS else "Other",
        "contact": contact[:40],
        "severity": result["severity"],
        "shared": bool(triggered),
        "signals": [{"id": s["id"], "label": s["label"], "quote": s.get("quote", "")}
                    for s in (triggered or result["signals"])],
    }
    events = _read(ALERTS_FILE, [])
    events.insert(0, event)
    _write(ALERTS_FILE, events[:200])
    return event if triggered else None


def get_alerts():
    """What the family sees: shared alerts only."""
    return [e for e in _read(ALERTS_FILE, []) if e.get("shared")]


def contacts_across_apps():
    """Same contact in more than one app, with at least one shared alert.

    Moving a kid from a game to a private app is the classic pressure path,
    and no single platform's parental tools can see it.
    """
    events = _read(ALERTS_FILE, [])
    apps, shared, display = {}, set(), {}
    for e in reversed(events):  # oldest first, so the path reads in order (Roblox -> Instagram)
        name = e.get("contact", "")
        c = name.lower()
        if not c:
            continue
        display.setdefault(c, name)
        path = apps.setdefault(c, [])
        if e["app"] not in path:
            path.append(e["app"])
        if e.get("shared"):
            shared.add(c)
    return {display[c]: a for c, a in apps.items() if len(a) > 1 and c in shared}
