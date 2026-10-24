"""Link inspector: what is really behind a link a stranger sent, without the kid clicking it.

Only the link itself leaves the computer (never the chat):
  - Browserbase opens it in an isolated cloud browser: where it really ends up, the page title, whether it asks for a
    password, and a small screenshot.
  - SerpApi searches the web for reports about that domain (scam, phishing, fake).
Each part is optional (BROWSERBASE_API_KEY + BROWSERBASE_PROJECT_ID, SERPAPI_KEY in .env); the verdict says what was
checked and never claims a link is safe just because nothing was found.
"""

import base64
import os
import re
import time
from urllib.parse import urlparse

import httpx

from . import telemetry

OFFICIAL = {  # where the official sites of the apps kids use live
    "roblox.com", "discord.com", "discord.gg", "minecraft.net", "mojang.com", "epicgames.com", "fortnite.com",
    "tiktok.com", "instagram.com", "whatsapp.com", "youtube.com",
}
# General-purpose content hosts such as sites.google.com and docs.google.com
# cannot establish that a page belongs to the official game or app.
SCAM_WORDS = re.compile(r"\b(scam|phishing|fake|fraud|golpe|falso|malware|steal|stolen|hack(ed)?)\b", re.I)


def enabled():
    return {"browserbase": bool(os.environ.get("BROWSERBASE_API_KEY") and os.environ.get("BROWSERBASE_PROJECT_ID")),
            "serpapi": bool(os.environ.get("SERPAPI_KEY"))}


def normalize(url):
    url = url.strip().rstrip(".,!?)\"'")
    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url
    return url


def domain_of(url):
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def is_official(host):
    return any(host == d or host.endswith("." + d) for d in OFFICIAL)


def open_in_browserbase(url):
    """Open the link in a Browserbase cloud browser and look at the page (no typing, no clicking)."""
    from playwright.sync_api import sync_playwright
    key, project = os.environ["BROWSERBASE_API_KEY"], os.environ["BROWSERBASE_PROJECT_ID"]
    headers = {"X-BB-API-Key": key, "Content-Type": "application/json"}
    r = httpx.post("https://api.browserbase.com/v1/sessions", headers=headers,
                   json={"projectId": project, "timeout": 60, "keepAlive": False,
                         "browserSettings": {"recordSession": False, "logSession": False,
                                             "viewport": {"width": 1024, "height": 640}}}, timeout=30)
    r.raise_for_status()
    sess = r.json()
    out = {"session": sess.get("id")}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(sess["connectUrl"], timeout=20000)
            try:
                ctx = browser.contexts[0] if browser.contexts else browser.new_context()
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                try:
                    # Existing CDP pages can retain a viewport larger than the
                    # session setting, leaving centered content outside the clip.
                    page.set_viewport_size({"width": 1024, "height": 640})
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    page.wait_for_timeout(1500)
                    out["status"] = resp.status if resp else None
                    out["final_url"] = page.url
                    out["title"] = (page.title() or "")[:120]
                    out["asks_password"] = page.locator("input[type=password]").count() > 0
                    out["asks_login"] = out["asks_password"] or bool(page.locator(
                        "input[type=email], input[name*=user i], input[name*=login i]").count())
                    shot = page.screenshot(type="jpeg", quality=55, clip={"x": 0, "y": 0, "width": 1024, "height": 640})
                    out["screenshot"] = "data:image/jpeg;base64," + base64.b64encode(shot).decode()
                except Exception as e:  # dead domain, timeout, TLS error...
                    out["error"] = type(e).__name__
                    out["unreachable"] = True
            finally:
                browser.close()
    finally:
        # Also release sessions if Playwright cannot connect or browser.close()
        # fails. The short provider timeout remains a fallback for API outages.
        if sess.get("id"):
            try:
                release = httpx.post(f'https://api.browserbase.com/v1/sessions/{sess["id"]}', headers=headers,
                                     json={"status": "REQUEST_RELEASE"}, timeout=10)
                release.raise_for_status()
            except httpx.HTTPError:
                pass  # Do not hide an inspection result or the original error.
    return out


def search_reports(host):
    """Ask SerpApi (Google results) whether people report this domain as a scam."""
    r = httpx.get("https://serpapi.com/search.json", params={
        "engine": "google", "q": f'"{host}" scam OR phishing OR fake', "num": 6, "api_key": os.environ["SERPAPI_KEY"]},
        timeout=30)
    r.raise_for_status()
    hits = []
    for o in (r.json().get("organic_results") or [])[:6]:
        txt = f'{o.get("title", "")} {o.get("snippet", "")}'
        hits.append({"title": o.get("title", "")[:120], "link": o.get("link", ""), "snippet": o.get("snippet", "")[:200],
                     "mentions_scam": bool(SCAM_WORDS.search(txt)) and host.split(".")[0] in txt.lower()})
    return hits


TXT = {
    "en": {"password": "This page asks for a password and it is not the official game or app site. Never log in from a link someone sent you.",
           "moved": "This link sends you to a different site than it shows: {final}.",
           "unofficial": "{host} is not an official site of the game or app.",
           "dead": "This link doesn't open (the site may be fake or already taken down).",
           "reports": "People online report this site as a scam ({n} results).",
           "noreports": "No reports found online yet. That does not mean it is safe: new scam pages often have none.",
           "official": "This is the official site of {host}. Still, only log in by typing the address yourself.",
           "verdict_bad": "Don't open this link", "verdict_ok": "Looks like the official site", "verdict_unknown": "Be careful with this link",
           "failed": "{tool} couldn't check this link right now, so this is not a full check.",
           "listed": "{host} is on the list of official sites, but the page itself could not be checked.",
           "verdict_error": "Couldn't check this link"},
    "pt": {"password": "Essa página pede senha e não é o site oficial do jogo ou app. Nunca faça login por um link que alguém te mandou.",
           "moved": "Esse link leva para outro site, diferente do que mostra: {final}.",
           "unofficial": "{host} não é um site oficial do jogo ou do app.",
           "dead": "Esse link não abre (o site pode ser falso ou já ter sido derrubado).",
           "reports": "Tem gente na internet denunciando esse site como golpe ({n} resultados).",
           "noreports": "Nenhuma denúncia encontrada ainda. Isso não quer dizer que é seguro: páginas de golpe novas costumam não ter.",
           "official": "Esse é o site oficial de {host}. Mesmo assim, só faça login digitando o endereço você mesmo.",
           "verdict_bad": "Não abra esse link", "verdict_ok": "Parece o site oficial", "verdict_unknown": "Cuidado com esse link",
           "failed": "O {tool} não conseguiu conferir esse link agora, então esta não é uma checagem completa.",
           "listed": "{host} está na lista de sites oficiais, mas a página em si não pôde ser conferida.",
           "verdict_error": "Não consegui conferir esse link"},
}


def check_link(url, lang="en"):
    t = TXT.get(lang, TXT["en"])
    url = normalize(url)
    host = domain_of(url)
    res = {"url": url, "host": host, "checked": [], "reasons": [], "browser": None, "reports": None}
    on = enabled()
    t0 = time.time()
    with telemetry.span("night_guard.link_check", "inspect link", n_tools=sum(on.values())):
        if on["browserbase"]:
            try:
                res["browser"] = open_in_browserbase(url); res["checked"].append("Browserbase")
            except Exception as e:
                res["browser"] = {"error": type(e).__name__}
        if on["serpapi"]:
            try:
                res["reports"] = search_reports(host); res["checked"].append("SerpApi")
            except Exception as e:
                res["reports"] = None; res["reports_error"] = type(e).__name__
    b = res["browser"] or {}
    bad = False
    final_host = domain_of(b.get("final_url", "")) if b.get("final_url") else host
    if b.get("unreachable"):
        res["reasons"].append(t["dead"]); bad = True
    if b.get("final_url") and final_host and final_host != host:
        res["reasons"].append(t["moved"].format(final=final_host)); bad = bad or not is_official(final_host)
    official = is_official(final_host)
    if b.get("asks_password") and not official:
        res["reasons"].insert(0, t["password"]); bad = True
    if not official:
        res["reasons"].append(t["unofficial"].format(host=final_host or host))
    if res["reports"] is not None:
        n = sum(1 for h in res["reports"] if h["mentions_scam"])
        # Scam pages often imitate an official brand, so search hits about the brand say nothing against the
        # official site itself. For other hosts, reports of a scam are a reason not to open the link.
        if not official:
            res["reasons"].append(t["reports"].format(n=n) if n else t["noreports"])
            bad = bad or n > 0
    # A provider that was asked and failed is reported, and never turned into a positive verdict.
    failed = [n for n, k in (("Browserbase", "browserbase"), ("SerpApi", "serpapi")) if on[k] and n not in res["checked"]]
    res["failed"] = failed
    for n in failed:
        res["reasons"].append(t["failed"].format(tool=n))
    page_seen = "Browserbase" in res["checked"]
    if official and not bad:
        res["reasons"].append(t["official"].format(host=final_host) if page_seen else t["listed"].format(host=final_host))
    if bad:
        res["verdict"], res["level"] = t["verdict_bad"], "bad"
    elif not res["checked"]:
        res["verdict"], res["level"] = t["verdict_error"], "error"          # nothing could be checked at all
    elif official and page_seen:
        res["verdict"], res["level"] = t["verdict_ok"], "ok"               # only after the page itself was inspected
    else:
        res["verdict"], res["level"] = t["verdict_unknown"], "unknown"
    res["latency_s"] = round(time.time() - t0, 2)
    return res
