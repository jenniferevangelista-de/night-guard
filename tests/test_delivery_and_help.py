"""Delivery reporting and help context; all notification calls are simulated."""
import json

import pytest
from fastapi.testclient import TestClient

from guard import family, notify, server
from guard.helper import draft_help


EVENT = {"severity": "high", "app": "Discord", "contact": "private-name",
         "signals": [{"id": "credential_request", "label": "Asked for password", "quote": "private-quote"}]}


def test_disabled_notifications_make_no_provider_call(monkeypatch):
    monkeypatch.setattr(notify, "get_settings", lambda: {"enabled": False})
    monkeypatch.setattr(notify.httpx, "post", lambda *a, **k: pytest.fail("no network when disabled"))
    assert notify.push_alert(EVENT) == "disabled"


@pytest.mark.parametrize("code,expected", [(200, "accepted"), (503, "failed")])
def test_acceptance_is_not_a_receipt_and_sends_no_quote_or_name(monkeypatch, code, expected):
    from types import SimpleNamespace
    monkeypatch.setattr(notify, "get_settings", lambda: {"enabled": True, "topic": "fictional-topic"})
    sent = []
    monkeypatch.setattr(notify.httpx, "post", lambda *a, **k: sent.append(k["json"]) or SimpleNamespace(status_code=code))
    assert notify.push_alert(EVENT) == expected
    assert len(sent) == 1
    payload = json.dumps(sent[0])
    assert "private-name" not in payload and "private-quote" not in payload
    assert "Discord" in payload and "Asked for password" in payload


def test_notification_timeout_reports_failure(monkeypatch):
    monkeypatch.setattr(notify, "get_settings", lambda: {"enabled": True, "topic": "fictional-topic"})
    def fail(*a, **k):
        raise TimeoutError("simulated")
    monkeypatch.setattr(notify.httpx, "post", fail)
    assert notify.push_alert(EVENT) == "failed"


@pytest.mark.parametrize("demo,delivery", [(True, "demo_only"), (False, "failed"), (False, "accepted"), (False, "disabled")])
def test_analysis_keeps_the_risk_and_reports_actual_notification_state(monkeypatch, tmp_path, demo, delivery):
    monkeypatch.setattr(server, "DEMO", demo)
    monkeypatch.setattr(family, "DATA", tmp_path)
    monkeypatch.setattr(family, "ALERTS_FILE", tmp_path / "alerts.json")
    monkeypatch.setattr(family, "RULES_FILE", tmp_path / "rules.json")
    monkeypatch.setattr(server, "analyze", lambda *a, **k: {
        "severity": "high", "analysis_status": "ok", "signals": EVENT["signals"], "links": []})
    calls = []
    monkeypatch.setattr(notify, "push_alert", lambda *a, **k: calls.append(1) or delivery)
    r = TestClient(server.app).post("/api/analyze", json={"text": "Contact: give me your password", "app": "Discord"})
    assert r.status_code == 200
    result = r.json()
    assert result["notification_status"] == delivery
    assert result["severity"] == "high" and result["family_alert"]["shared"]
    assert len(calls) == (0 if demo else 1)
    assert (tmp_path / "alerts.json").exists() is (not demo)


def test_notification_exception_does_not_hide_risk(monkeypatch, tmp_path):
    monkeypatch.setattr(server, "DEMO", False)
    monkeypatch.setattr(family, "DATA", tmp_path)
    monkeypatch.setattr(family, "ALERTS_FILE", tmp_path / "alerts.json")
    monkeypatch.setattr(family, "RULES_FILE", tmp_path / "rules.json")
    monkeypatch.setattr(server, "analyze", lambda *a, **k: {
        "severity": "high", "signals": EVENT["signals"], "links": []})
    def fail(*a, **k):
        raise RuntimeError("simulated")
    monkeypatch.setattr(notify, "push_alert", fail)
    result = TestClient(server.app).post("/api/analyze", json={"text": "Contact: give me your password"}).json()
    assert result["severity"] == "high" and result["notification_status"] == "failed"


@pytest.mark.parametrize("lang,app,fragment", [("pt", "Instagram", "no Instagram"), ("en", "TikTok", "on TikTok"),
                                            ("pt", "Other", "numa conversa online"), ("en", "made-up", "in an online chat")])
def test_help_uses_the_source_instead_of_inventing_a_game(lang, app, fragment):
    result = draft_help(["the selected quote"], "Alex", "", lang, app)
    assert fragment in result and "the selected quote" in result
    assert "num jogo" not in result and "in a game" not in result and "made-up" not in result


def test_help_api_preserves_app_context():
    r = TestClient(server.app).post("/api/help", json={"quotes": ["selected words"], "who": "Dad", "app": "Instagram"})
    assert r.status_code == 200 and "on Instagram" in r.json()["message"]
