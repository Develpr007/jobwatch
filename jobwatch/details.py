"""Second pass: fetch the full job description for candidate roles so the filter can read
experience and education requirements, not just the title."""
import re
import html as htmlmod
from urllib.parse import urljoin
from bs4 import BeautifulSoup

from . import http
from .models import Job


def _text_from_html(h: str) -> str:
    if not h:
        return ""
    h = htmlmod.unescape(h)
    soup = BeautifulSoup(h, "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
        t.decompose()
    txt = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", txt)


def _page_text(s, url: str) -> str:
    try:
        r = http.get(s, url, timeout=25)
        if r.status_code != 200:
            return ""
        return _text_from_html(r.text)
    except Exception:
        return ""


def _browser_text(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True)
            page = b.new_context(locale="en-IN").new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=40000)
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            txt = _text_from_html(page.content())
            b.close()
            return txt
    except Exception:
        return ""


# ---- platform-specific detail fetchers -------------------------------------------------
def _workday(job, cfg, s):
    host = cfg.get("host") or f"https://{cfg['tenant']}.{cfg['pod']}.myworkdayjobs.com"
    path = job.extra.get("externalPath")
    if not path:
        return ""
    r = http.get(s, f"{host}/wday/cxs/{cfg['tenant']}/{cfg['site']}{path}", headers={"Accept": "application/json"})
    if r.status_code != 200:
        return ""
    info = r.json().get("jobPostingInfo") or {}
    return _text_from_html(info.get("jobDescription", ""))


def _eightfold(job, cfg, s):
    pid = job.extra.get("id")
    if not pid:
        return ""
    r = http.get(s, f"{cfg['base'].rstrip('/')}/api/apply/v2/jobs/{pid}?domain={cfg.get('domain','')}",
                 headers={"Accept": "application/json"})
    if r.status_code != 200:
        return ""
    return _text_from_html(r.json().get("job_description", ""))


def _oracle(job, cfg, s):
    rid = job.extra.get("id")
    if not rid:
        return ""
    url = (f"{cfg['host'].rstrip('/')}/hcmRestApi/resources/latest/recruitingCEJobRequisitionDetails"
           f"?expand=all&onlyData=true&finder=ById;Id=\"{rid}\",siteNumber={cfg['site']}")
    r = http.get(s, url, headers={"Accept": "application/json"})
    if r.status_code != 200:
        return ""
    items = r.json().get("items") or []
    if not items:
        return ""
    it = items[0]
    return _text_from_html(" ".join(str(it.get(k, "") or "") for k in
                                    ("ExternalDescriptionStr", "ExternalQualificationsStr", "ExternalResponsibilitiesStr")))


def _smartrecruiters(job, cfg, s):
    pid = job.extra.get("id")
    if not pid:
        return ""
    r = http.get(s, f"https://api.smartrecruiters.com/v1/companies/{cfg['company_id']}/postings/{pid}")
    if r.status_code != 200:
        return ""
    secs = ((r.json().get("jobAd") or {}).get("sections") or {})
    return _text_from_html(" ".join((secs.get(k) or {}).get("text", "") for k in
                                    ("jobDescription", "qualifications", "additionalInformation")))


SPECIFIC = {"workday": _workday, "eightfold": _eightfold, "oracle": _oracle, "smartrecruiters": _smartrecruiters}


def enrich(job: Job, cfg: dict, s, allow_browser: bool = True) -> str:
    """Fill job.description with the posting text. Returns the text ('' if nothing could be read)."""
    if job.description and len(job.description) > 300:
        return job.description
    txt = ""
    fn = SPECIFIC.get(cfg["adapter"])
    if fn:
        try:
            txt = fn(job, cfg, s)
        except Exception:
            txt = ""
    if len(txt) < 300 and job.url:
        txt = _page_text(s, job.url)
    if len(txt) < 300 and job.url and allow_browser:
        txt = _browser_text(job.url)
    job.description = txt
    return txt
