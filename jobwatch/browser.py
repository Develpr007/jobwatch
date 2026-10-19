"""Headless-browser adapter for sites that only render jobs with JavaScript.

Loads the page in Chromium (Playwright), waits for it to settle, scrolls a few times,
clicks 'load more' style buttons if present, then collects job-looking links.
Same link heuristics as the HTML adapter, so results feed the same filter.
"""
import re
from urllib.parse import urljoin
from .models import Job
from .adapters import _parse_links

LOAD_MORE = re.compile(r"(load more|show more|view more|more jobs|see more|next)", re.I)


CARD_SELECTORS = (
    "[class*='job-title'], [class*='jobTitle'], [class*='job_title'], [class*='JobTitle'], "
    "[class*='position-title'], [class*='positionTitle'], [class*='opening-title'], [class*='role-title'], "
    "[data-automation-id='jobTitle'], [class*='job-card'] h2, [class*='job-card'] h3, [class*='jobCard'] h3, "
    "[class*='job-list'] h3, [class*='job-list'] h4, [class*='jobs-list'] h3, [class*='opening'] h3, "
    "[class*='career'] [class*='title'], [class*='job-name'], [class*='jobName']"
)


def _cards(page, company, page_url):
    """Fallback for pages where jobs are clickable cards without links: take the card titles."""
    out, seen = [], set()
    try:
        els = page.query_selector_all(CARD_SELECTORS)
    except Exception:
        return out
    for el in els[:400]:
        try:
            t = (el.inner_text() or "").strip().split("\n")[0].strip()
        except Exception:
            continue
        if not (5 <= len(t) <= 120) or t.lower() in seen:
            continue
        seen.add(t.lower())
        href = ""
        try:
            href = el.evaluate("e => (e.closest('a') || {}).href || ''") or ""
        except Exception:
            pass
        url = href if href and href.startswith("http") else f"{page_url.split('#')[0]}#card={len(out)}"
        out.append(Job(company, t, url, "", "", "browser-card"))
    return out


def fetch_with_browser(cfg):
    from playwright.sync_api import sync_playwright
    urls = cfg.get("urls") or [cfg["url"]]
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, args=["--disable-http2", "--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            locale="en-IN", viewport={"width": 1366, "height": 900}, ignore_https_errors=True, accept_downloads=False)
        page = ctx.new_page()
        for u in urls:
            try:
                page.goto(u, wait_until="commit", timeout=cfg.get("timeout_ms", 45000))
                for state, ms in (("domcontentloaded", 30000), ("networkidle", 20000)):
                    try:
                        page.wait_for_load_state(state, timeout=ms)
                    except Exception:
                        pass
                if cfg.get("wait_for"):
                    try:
                        page.wait_for_selector(cfg["wait_for"], timeout=20000)
                    except Exception:
                        pass
                page.wait_for_timeout(2500)
                # accept cookie banners that block clicks
                for txt in ("Accept all", "Accept All", "Accept", "I agree", "Got it", "OK"):
                    try:
                        page.get_by_role("button", name=txt, exact=False).first.click(timeout=1500)
                        break
                    except Exception:
                        continue
                for _ in range(cfg.get("scrolls", 4)):
                    page.mouse.wheel(0, 2500)
                    page.wait_for_timeout(1200)
                    try:
                        btn = page.get_by_role("button", name=LOAD_MORE).first
                        if btn.is_visible():
                            btn.click(timeout=2000)
                            page.wait_for_timeout(2000)
                    except Exception:
                        pass
                html = page.content()
                found = _parse_links(cfg["name"], html, u, "browser", selector=cfg.get("selector"))
                # click-only SPAs (TurboHire, Darwinbox, Keka...) have no job <a href>; read title text from cards
                if not found:
                    found = _cards(page, cfg["name"], u)
                if not found and cfg.get("card_selector"):
                    for el in page.query_selector_all(cfg["card_selector"]):
                        title = (el.inner_text() or "").strip().split("\n")[0]
                        href = el.get_attribute("href") or el.get_attribute("data-href") or ""
                        if title and href:
                            found.append(Job(cfg["name"], title, urljoin(u, href), "", "", "browser"))
                out.extend(found)
            except Exception as e:  # keep going with the other URLs
                out.append(Job(cfg["name"], f"__error__ {e}", u, "", "", "browser"))
        b.close()
    errors = [j for j in out if j.title.startswith("__error__")]
    out = [j for j in out if not j.title.startswith("__error__")]
    if errors and not out:
        raise RuntimeError(errors[0].title[10:200])
    return out
