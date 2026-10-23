"""F08 + F10: typed input on /api/analyze and the parent allowlist."""
from fastapi.testclient import TestClient

from guard import auth
from guard.server import Msg, app

client = TestClient(app)


def test_msg_rejects_bad_sender_and_empty_text():
    import pydantic
    for bad in ({"from": "admin", "text": "hi"}, {"from": "them", "text": ""}, {"from": "them", "text": "x" * 2001}):
        try:
            Msg(**bad)
        except pydantic.ValidationError:
            continue
        raise AssertionError(f"accepted {bad}")
    assert Msg(**{"from": "them", "text": "hi"}).as_dict()["from"] == "them"


def test_analyze_rejects_malformed_messages_before_the_model():
    r = client.post("/api/analyze", json={"messages": [{"from": "them", "text": 5}]})
    assert r.status_code == 422
    r = client.post("/api/analyze", json={"messages": [{"from": "x", "text": "hi"}]})
    assert r.status_code == 422


def test_health_reports_deploy_commit():
    r = client.get("/api/health").json()
    assert r["ok"] and "commit" in r


def test_only_verified_allowlisted_emails_are_parents(monkeypatch):
    monkeypatch.setattr(auth, "PARENT_EMAILS", {"parent@example.test"})
    assert auth.is_parent({"email": "Parent@Example.test", "email_verified": True})
    assert not auth.is_parent({"email": "parent@example.test", "email_verified": False})
    assert not auth.is_parent({"email": "kid@example.test", "email_verified": True})
    assert not auth.is_parent({"email_verified": True})
