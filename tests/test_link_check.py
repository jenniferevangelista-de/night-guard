"""Link inspector verdicts (Browserbase and SerpApi answers are simulated: no network in tests)."""
import sys
from types import SimpleNamespace

import pytest

from guard import link_check as lc


def run(monkeypatch, browser=None, reports=None, url="https://night-guard-demo.onrender.com/demo/free-gems"):
    monkeypatch.setattr(lc, "enabled", lambda: {"browserbase": browser is not None, "serpapi": reports is not None})
    monkeypatch.setattr(lc, "open_in_browserbase", lambda u: browser)
    monkeypatch.setattr(lc, "search_reports", lambda h: reports)
    return lc.check_link(url, "en")


def test_fake_login_page_is_flagged(monkeypatch):
    r = run(monkeypatch, browser={"final_url": "https://night-guard-demo.onrender.com/demo/free-gems", "asks_password": True})
    assert r["level"] == "bad" and "password" in r["reasons"][0]
    assert r["checked"] == ["Browserbase"]


def test_redirect_to_other_site_is_flagged(monkeypatch):
    r = run(monkeypatch, browser={"final_url": "https://evil-login.example/x", "asks_password": False}, url="https://bit.ly/abc")
    assert r["level"] == "bad" and any("evil-login.example" in x for x in r["reasons"])


def test_dead_link_is_not_called_safe(monkeypatch):
    r = run(monkeypatch, browser={"unreachable": True, "error": "TimeoutError"}, url="robux-gift-claim.xyz")
    assert r["level"] == "bad" and r["host"] == "robux-gift-claim.xyz"


def test_no_reports_is_not_an_all_clear(monkeypatch):
    r = run(monkeypatch, reports=[], url="new-gems-site.xyz")
    assert r["level"] == "unknown" and any("does not mean it is safe" in x for x in r["reasons"])


def test_scam_reports_flag_the_link(monkeypatch):
    r = run(monkeypatch, reports=[{"title": "free-gems-now scam warning", "snippet": "", "link": "", "mentions_scam": True}],
            url="free-gems-now.xyz")
    assert r["level"] == "bad"


def test_official_site_with_login(monkeypatch):
    r = run(monkeypatch, browser={"final_url": "https://www.roblox.com/login", "asks_password": True}, url="https://www.roblox.com/login")
    assert r["level"] == "ok" and "official" in r["verdict"].lower()


@pytest.mark.parametrize("host", ["sites.google.com", "docs.google.com"])
def test_user_hosted_page_is_not_an_official_game_login(monkeypatch, host):
    url = f"https://{host}/free-gems"
    r = run(monkeypatch, browser={"final_url": url, "asks_password": True}, url=url)
    assert r["level"] == "bad"
    assert "password" in r["reasons"][0]


def test_browserbase_releases_session_when_connection_fails(monkeypatch):
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "test-project")
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return lc.httpx.Response(200, request=lc.httpx.Request("POST", url),
                                 json={"id": "test-session", "connectUrl": "wss://example.test"})

    def connect(*args, **kwargs):
        raise RuntimeError("connection failed")

    class Playwright:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=connect))

        def __exit__(self, *args):
            return False

    monkeypatch.setitem(sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=Playwright))
    monkeypatch.setattr(lc.httpx, "post", post)

    with pytest.raises(RuntimeError, match="connection failed"):
        lc.open_in_browserbase("https://example.test")

    assert len(calls) == 2
    settings = calls[0][1]["json"]
    assert settings["timeout"] == 60 and settings["keepAlive"] is False
    assert settings["browserSettings"]["recordSession"] is False
    assert settings["browserSettings"]["logSession"] is False
    assert calls[1][0] == "https://api.browserbase.com/v1/sessions/test-session"
    assert calls[1][1]["json"] == {"status": "REQUEST_RELEASE"}


def test_cleanup_api_failure_keeps_original_error(monkeypatch):
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "test-project")

    def post(url, **kwargs):
        if url.endswith("/test-session"):
            raise lc.httpx.ConnectError("release unavailable")
        return lc.httpx.Response(200, request=lc.httpx.Request("POST", url),
                                 json={"id": "test-session", "connectUrl": "wss://example.test"})

    class Playwright:
        def __enter__(self):
            raise RuntimeError("playwright unavailable")

        def __exit__(self, *args):
            return False

    monkeypatch.setitem(sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=Playwright))
    monkeypatch.setattr(lc.httpx, "post", post)
    with pytest.raises(RuntimeError, match="playwright unavailable"):
        lc.open_in_browserbase("https://example.test")


def test_existing_browser_page_uses_screenshot_viewport_before_loading(monkeypatch):
    monkeypatch.setenv("BROWSERBASE_API_KEY", "test-key")
    monkeypatch.setenv("BROWSERBASE_PROJECT_ID", "test-project")
    events = []

    class Page:
        url = "https://example.test"

        def set_viewport_size(self, size):
            events.append(("viewport", size))

        def goto(self, url, **kwargs):
            events.append(("goto", url))
            return SimpleNamespace(status=200)

        def wait_for_timeout(self, milliseconds):
            pass

        def title(self):
            return "Fictional demo"

        def locator(self, selector):
            return SimpleNamespace(count=lambda: 1)

        def screenshot(self, **kwargs):
            assert kwargs["clip"]["width"] == 1024 and kwargs["clip"]["height"] == 640
            return b"test-image"

    page = Page()
    browser = SimpleNamespace(contexts=[SimpleNamespace(pages=[page])], close=lambda: events.append(("close",)))

    class Playwright:
        def __enter__(self):
            return SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=lambda *a, **k: browser))

        def __exit__(self, *args):
            return False

    def post(url, **kwargs):
        return lc.httpx.Response(200, request=lc.httpx.Request("POST", url),
                                 json={"id": "test-session", "connectUrl": "wss://example.test"})

    monkeypatch.setitem(sys.modules, "playwright.sync_api", SimpleNamespace(sync_playwright=Playwright))
    monkeypatch.setattr(lc.httpx, "post", post)
    result = lc.open_in_browserbase("https://example.test")
    assert events[:2] == [("viewport", {"width": 1024, "height": 640}), ("goto", "https://example.test")]
    assert result["asks_password"] is True
    assert result["screenshot"].startswith("data:image/jpeg;base64,")


# Review 006, R09: a provider failure is never shown as a positive inspection.
def _failing(monkeypatch, bb=True, serp=False, bb_ok=None):
    def bad_browser(u):
        raise lc.httpx.ConnectError("synthetic offline")
    def bad_search(h):
        raise lc.httpx.ConnectError("synthetic offline")
    monkeypatch.setattr(lc, "enabled", lambda: {"browserbase": bb, "serpapi": serp})
    monkeypatch.setattr(lc, "open_in_browserbase", (lambda u: bb_ok) if bb_ok else bad_browser)
    monkeypatch.setattr(lc, "search_reports", bad_search)


@pytest.mark.parametrize("url", ["https://www.roblox.com/login", "https://discord.com/login"])
def test_kuririn_006_r09_browser_failure_is_not_ok(monkeypatch, url):
    _failing(monkeypatch)
    r = lc.check_link(url, "en")
    assert r["level"] != "ok" and r["checked"] == [] and r["failed"] == ["Browserbase"]
    assert r["level"] == "error" and any("couldn't check" in x for x in r["reasons"])


def test_kuririn_006_r09_both_providers_down(monkeypatch):
    _failing(monkeypatch, bb=True, serp=True)
    r = lc.check_link("https://www.roblox.com/login", "pt")
    assert r["level"] == "error" and set(r["failed"]) == {"Browserbase", "SerpApi"}


def test_kuririn_006_r09_search_ok_but_page_not_seen_is_unknown(monkeypatch):
    monkeypatch.setattr(lc, "enabled", lambda: {"browserbase": True, "serpapi": True})
    monkeypatch.setattr(lc, "open_in_browserbase", lambda u: (_ for _ in ()).throw(RuntimeError("down")))
    monkeypatch.setattr(lc, "search_reports", lambda h: [])
    r = lc.check_link("https://www.roblox.com/login", "en")
    assert r["level"] == "unknown" and any("could not be checked" in x for x in r["reasons"])


def test_kuririn_006_r09_recovery_official_page_inspected_is_ok(monkeypatch):
    _failing(monkeypatch, bb_ok={"final_url": "https://www.roblox.com/login", "asks_password": True})
    r = lc.check_link("https://www.roblox.com/login", "en")
    assert r["level"] == "ok" and r["failed"] == []
