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


def fetch_with_browser(cfg):
    from playwright.sync_api import sync_playwright
    urls = cfg.get("urls") or [cfg["url"]]
    out = []
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        ctx = b.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            locale="en-IN", viewport={"width": 1366, "height": 900})
        page = ctx.new_page()
        for u in urls:
            try:
                page.goto(u, wait_until="domcontentloaded", timeout=45000)
                try:
                    page.wait_for_load_state("networkidle", timeout=20000)
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
                # some SPAs put job titles in non-anchor cards with a data-href / onclick; also try those
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
