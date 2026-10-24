"""Typed input on /api/analyze and the parent allowlist."""
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


def _configured_auth(monkeypatch, backend, oauth_import):
    import builtins
    import importlib.util
    from guard import detector

    monkeypatch.setattr(detector, "BACKEND", backend)
    for name in ("AUTH0_DOMAIN", "AUTH0_CLIENT_ID", "AUTH0_CLIENT_SECRET", "SESSION_SECRET"):
        monkeypatch.setenv(name, "test-only")
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "authlib.integrations.starlette_client":
            return oauth_import()
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    spec = importlib.util.spec_from_file_location("guard._configured_auth_test", auth.__file__)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_demo_ignores_auth0_credentials_without_importing_authlib(monkeypatch):
    from fastapi import Depends, FastAPI

    def forbidden_import():
        raise AssertionError("The public demo must not import Auth0 dependencies")

    demo_auth = _configured_auth(monkeypatch, "tinker", forbidden_import)
    demo = FastAPI()
    demo_auth.add_routes(demo)

    @demo.get("/parents", dependencies=[Depends(demo_auth.require_parent)])
    def parents():
        return {"demo": True}

    demo_client = TestClient(demo)
    assert demo_client.get("/api/auth/me").json() == {"enabled": False, "parent": None}
    assert demo_client.get("/parents").status_code == 200
    assert demo_client.get("/auth/login").status_code == 404


def test_local_auth0_still_requires_parent_session(monkeypatch):
    from types import SimpleNamespace
    from fastapi import Depends, FastAPI
    from starlette.middleware.sessions import SessionMiddleware

    class OAuth:
        def register(self, *args, **kwargs):
            pass

    local_auth = _configured_auth(monkeypatch, "ollama", lambda: SimpleNamespace(OAuth=OAuth))
    local = FastAPI()
    local.add_middleware(SessionMiddleware, secret_key="test-only")
    local_auth.add_routes(local)

    @local.get("/parents", dependencies=[Depends(local_auth.require_parent)])
    def parents():
        return {"private": True}

    local_client = TestClient(local)
    assert local_client.get("/api/auth/me").json() == {"enabled": True, "parent": None}
    assert local_client.get("/parents").status_code == 401


def test_auth0_failures_show_a_message_and_never_open_a_parent_session(monkeypatch):
    from types import SimpleNamespace
    from fastapi import FastAPI
    from starlette.middleware.sessions import SessionMiddleware

    class Client:
        async def authorize_redirect(self, request, redirect_uri):
            raise RuntimeError("auth provider unreachable")

        async def authorize_access_token(self, request):
            raise RuntimeError("login declined, expired or interrupted")

    class OAuth:
        auth0 = Client()

        def register(self, *args, **kwargs):
            pass

    local_auth = _configured_auth(monkeypatch, "ollama", lambda: SimpleNamespace(OAuth=OAuth))
    local_auth.oauth = OAuth()
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-only")
    local_auth.add_routes(app)
    client = TestClient(app, follow_redirects=False)
    for path in ("/auth/login", "/auth/callback?error=access_denied"):
        r = client.get(path)
        assert r.status_code in (302, 307) and r.headers["location"] == "/?tab=family&auth=failed"
    assert client.get("/api/auth/me").json()["parent"] is None
