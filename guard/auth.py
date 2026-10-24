"""Auth0 login for the Parents area (local app).

Why: the child uses the same computer. Without a login, a kid could open the Parents tab, read the
alerts, change the family rules or simply turn the automatic protection off. With Auth0, only a
signed-in parent can do that. The child-facing screens stay open: a kid never needs a password to
ask for help.

Enabled only when AUTH0_DOMAIN, AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET and SESSION_SECRET are set
in .env. The online demo never uses it (it has no family data to protect).
"""

import os

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse

from .detector import BACKEND

DOMAIN = os.environ.get("AUTH0_DOMAIN", "").strip()
CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "").strip()
CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET", "").strip()
SESSION_SECRET = os.environ.get("SESSION_SECRET", "").strip()
# Only these signed-in accounts are parents (comma-separated, verified e-mail required). Signing up
# on the Auth0 page is not enough to read a family's alerts.
# Optional fixed public address of the app (e.g. http://localhost:8765). Without it, the callback is built
# from whatever address the browser used, so 127.0.0.1 and localhost (and every port) are different URLs
# for Auth0. Set this and register exactly the printed callback URL in the Auth0 dashboard.
BASE_URL = os.environ.get("APP_BASE_URL", "").strip().rstrip("/")
PARENT_EMAILS = {e.strip().lower() for e in os.environ.get("PARENT_EMAILS", "").split(",") if e.strip()}
# The public demo has no family data or session middleware. Ignore Auth0 settings
# there, including when the host happens to have the local app's credentials.
ENABLED = BACKEND == "ollama" and all([DOMAIN, CLIENT_ID, CLIENT_SECRET, SESSION_SECRET])


def callback_url(request: Request):
    return f"{BASE_URL}/auth/callback" if BASE_URL else str(request.url_for("auth_callback"))


def home_url(request: Request):
    return f"{BASE_URL}/" if BASE_URL else str(request.url_for("index"))


def setup_hint(port=8765):
    """Text printed at startup: the exact URLs to paste in Auth0 > Applications > Settings."""
    if not ENABLED:
        return ""
    bases = [BASE_URL] if BASE_URL else [f"http://localhost:{port}", f"http://127.0.0.1:{port}"]
    return ("Auth0 is on. In Auth0 > Applications > Settings add:\n"
            f"  Allowed Callback URLs: {', '.join(b + '/auth/callback' for b in bases)}\n"
            f"  Allowed Logout URLs:   {', '.join(b + '/' for b in bases)}")


def is_parent(info):
    email = (info.get("email") or "").strip().lower()
    return bool(email) and info.get("email_verified") is True and email in PARENT_EMAILS

oauth = None
if ENABLED:
    from authlib.integrations.starlette_client import OAuth

    oauth = OAuth()
    oauth.register(
        "auth0",
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        server_metadata_url=f"https://{DOMAIN}/.well-known/openid-configuration",
        client_kwargs={"scope": "openid profile email"},
    )


def current_parent(request: Request):
    return request.session.get("parent") if ENABLED else None


def require_parent(request: Request):
    """FastAPI dependency for Parents-only endpoints."""
    if ENABLED and not request.session.get("parent"):
        raise HTTPException(401, "Parents only: sign in first.")


def add_routes(app):
    @app.get("/api/auth/me")
    def me(request: Request):
        p = current_parent(request)
        return {"enabled": ENABLED, "parent": {"name": p.get("name"), "email": p.get("email")} if p else None}

    if not ENABLED:
        return

    @app.get("/auth/login")
    async def login(request: Request):
        return await oauth.auth0.authorize_redirect(request, callback_url(request))

    @app.get("/auth/callback", name="auth_callback")
    async def callback(request: Request):
        try:
            token = await oauth.auth0.authorize_access_token(request)
        except Exception:  # expired login, state mismatch (opened with another host/port), Auth0 error
            request.session.clear()
            return RedirectResponse("/?tab=family&auth=failed")
        info = token.get("userinfo") or {}
        if not is_parent(info):
            request.session.clear()
            return RedirectResponse("/?tab=family&auth=not_parent")
        request.session["parent"] = {"name": info.get("name"), "email": info.get("email"), "sub": info.get("sub")}
        return RedirectResponse("/?tab=family")

    @app.get("/auth/logout")
    def logout(request: Request):
        request.session.clear()
        home = home_url(request)
        return RedirectResponse(f"https://{DOMAIN}/v2/logout?client_id={CLIENT_ID}&returnTo={home}")
