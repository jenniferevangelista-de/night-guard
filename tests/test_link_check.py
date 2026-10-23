"""Link inspector verdicts (Browserbase and SerpApi answers are simulated: no network in tests)."""
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
