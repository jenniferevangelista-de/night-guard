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
PARENT_EMAILS = {e.strip().lower() for e in os.environ.get("PARENT_EMAILS", "").split(",") if e.strip()}
# The public demo has no family data or session middleware. Ignore Auth0 settings
# there, including when the host happens to have the local app's credentials.
ENABLED = BACKEND == "ollama" and all([DOMAIN, CLIENT_ID, CLIENT_SECRET, SESSION_SECRET])


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
        return await oauth.auth0.authorize_redirect(request, str(request.url_for("auth_callback")))

    @app.get("/auth/callback", name="auth_callback")
    async def callback(request: Request):
        token = await oauth.auth0.authorize_access_token(request)
        info = token.get("userinfo") or {}
        if not is_parent(info):
            request.session.clear()
            return RedirectResponse("/?tab=family&auth=not_parent")
        request.session["parent"] = {"name": info.get("name"), "email": info.get("email"), "sub": info.get("sub")}
        return RedirectResponse("/?tab=family")

    @app.get("/auth/logout")
    def logout(request: Request):
        request.session.clear()
        home = str(request.url_for("index"))
        return RedirectResponse(f"https://{DOMAIN}/v2/logout?client_id={CLIENT_ID}&returnTo={home}")
