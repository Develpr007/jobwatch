"""One function per job-board platform. Each returns a list of Job objects for one company.

Adapters that use a simple HTTP request live here. The browser adapter (for sites that
only render jobs with JavaScript) is in browser.py and is loaded lazily.
"""
import re
import json
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

from .models import Job
from . import http

JOBISH_HREF = re.compile(
    r"/(job|jobs|career|careers|position|positions|opening|openings|role|roles|requisition|"
    r"vacanc|posting|postings|jobdetail|job-details|jobdetails|opportunit)[^\s]*", re.I)
NAV_WORDS = {"careers", "jobs", "home", "search", "apply", "login", "sign in", "view all",
             "all jobs", "see all", "learn more", "read more", "next", "previous", "back", "more"}


# --------------------------------------------------------------------------- Greenhouse
def greenhouse(cfg, s):
    token = cfg["token"]
    r = http.get(s, f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=false")
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs", []):
        out.append(Job(cfg["name"], j.get("title", ""), j.get("absolute_url", ""),
                       (j.get("location") or {}).get("name", ""), j.get("updated_at", ""), "greenhouse"))
    return out


# --------------------------------------------------------------------------- Lever
def lever(cfg, s):
    r = http.get(s, f"https://api.lever.co/v0/postings/{cfg['slug']}?mode=json")
    r.raise_for_status()
    out = []
    for p in r.json():
        cats = p.get("categories") or {}
        out.append(Job(cfg["name"], p.get("text", ""), p.get("hostedUrl", ""),
                       cats.get("location", ""), str(p.get("createdAt", "")), "lever",
                       extra={"team": cats.get("team", ""), "commitment": cats.get("commitment", "")}))
    return out


# --------------------------------------------------------------------------- SmartRecruiters
def smartrecruiters(cfg, s):
    cid = cfg["company_id"]
    out, offset = [], 0
    while True:
        url = f"https://api.smartrecruiters.com/v1/companies/{cid}/postings?limit=100&offset={offset}"
        if cfg.get("country"):
            url += f"&country={cfg['country']}"
        r = http.get(s, url)
        r.raise_for_status()
        data = r.json()
        for c in data.get("content", []):
            loc = c.get("location") or {}
            loc_txt = ", ".join(x for x in [loc.get("city"), loc.get("region"), loc.get("country")] if x)
            out.append(Job(cfg["name"], c.get("name", ""),
                           f"https://jobs.smartrecruiters.com/{cid}/{c.get('id')}",
                           loc_txt, c.get("releasedDate", ""), "smartrecruiters"))
        offset += 100
        if offset >= data.get("totalFound", 0) or not data.get("content"):
            break
    return out


# --------------------------------------------------------------------------- Amazon
def amazon(cfg, s):
    out, offset = [], 0
    while offset < 1000:
        url = (f"https://www.amazon.jobs/en/search.json?country=IND&result_limit=100&offset={offset}"
               f"&sort=recent")
        r = http.get(s, url)
        r.raise_for_status()
        data = r.json()
        jobs = data.get("jobs", [])
        for j in jobs:
            out.append(Job(cfg["name"], j.get("title", ""), urljoin("https://www.amazon.jobs", j.get("job_path", "")),
                           j.get("normalized_location", ""), j.get("posted_date", ""), "amazon",
                           description=j.get("basic_qualifications", "") or ""))
        if len(jobs) < 100:
            break
        offset += 100
    return out


# --------------------------------------------------------------------------- Workday (cxs)
def workday(cfg, s):
    """cfg: tenant, pod (wd1/wd3/...), site, optional host override, optional search_terms."""
    host = cfg.get("host") or f"https://{cfg['tenant']}.{cfg['pod']}.myworkdayjobs.com"
    site = cfg["site"]
    base = f"{host}/wday/cxs/{cfg['tenant']}/{site}/jobs"
    # a first GET sets cookies that the cxs endpoint expects
    try:
        http.get(s, f"{host}/{site}", timeout=20)
    except Exception:
        pass
    terms = cfg.get("search_terms") or ["analyst", "intern", "graduate", "associate", "trainee"]
    out, seen = [], set()
    for term in terms:
        offset = 0
        while offset < 300:
            body = {"appliedFacets": cfg.get("facets", {}), "limit": 20, "offset": offset, "searchText": term}
            r = http.post(s, base, json=body, headers={"Content-Type": "application/json",
                                                       "Accept": "application/json", "Origin": host})
            if r.status_code != 200:
                raise RuntimeError(f"workday {r.status_code}: {r.text[:200]}")
            data = r.json()
            posts = data.get("jobPostings", [])
            for p in posts:
                path = p.get("externalPath", "")
                url = f"{host}/en-US/{site}{path}" if path else ""
                if url in seen:
                    continue
                seen.add(url)
                out.append(Job(cfg["name"], p.get("title", ""), url, p.get("locationsText", ""),
                               p.get("postedOn", ""), "workday"))
            if len(posts) < 20:
                break
            offset += 20
    return out


# --------------------------------------------------------------------------- Eightfold
def eightfold(cfg, s):
    base = cfg["base"].rstrip("/")          # e.g. https://hsbc.eightfold.ai
    domain = cfg.get("domain", "")
    out, start = [], 0
    while start < 500:
        url = f"{base}/api/apply/v2/jobs?domain={domain}&location={cfg.get('location', 'India')}&num=100&start={start}&sort_by=timestamp"
        r = http.get(s, url, headers={"Accept": "application/json"})
        if r.status_code != 200:
            raise RuntimeError(f"eightfold {r.status_code}")
        data = r.json()
        pos = data.get("positions", [])
        for p in pos:
            out.append(Job(cfg["name"], p.get("name", ""), p.get("canonicalPositionUrl", ""),
                           p.get("location", ""), str(p.get("t_create", "")), "eightfold"))
        if len(pos) < 100:
            break
        start += 100
    return out


# --------------------------------------------------------------------------- Oracle Recruiting Cloud
def oracle(cfg, s):
    """cfg: host (https://xxx.fa.yyy.oraclecloud.com), site (CX_1001), location_id (optional)."""
    host, site = cfg["host"].rstrip("/"), cfg["site"]
    finder = f"findReqs;siteNumber={site},limit=200,sortBy=POSTING_DATES_DESC"
    if cfg.get("location_id"):
        finder += f",locationId={cfg['location_id']}"
    url = (f"{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions?onlyData=true"
           f"&expand=requisitionList.secondaryLocations&finder={finder}")
    r = http.get(s, url, headers={"Accept": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"oracle {r.status_code}")
    data = r.json()
    out = []
    for item in data.get("items", []):
        for q in item.get("requisitionList", []):
            rid = q.get("Id")
            url = f"{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{rid}"
            out.append(Job(cfg["name"], q.get("Title", ""), url, q.get("PrimaryLocation", ""),
                           q.get("PostedDate", ""), "oracle", description=q.get("ShortDescriptionStr", "") or ""))
    return out


# --------------------------------------------------------------------------- Radancy / TalentBrew
def radancy(cfg, s):
    """cfg: base (https://jobs.citi.com), location (India), optional list_path for HTML fallback."""
    base = cfg["base"].rstrip("/")
    out = []
    try:
        url = (f"{base}/search-jobs/results?ActiveFacetID=0&CurrentPage=1&RecordsPerPage=200&Distance=50"
               f"&RadiusUnitType=0&Keywords=&Location={cfg.get('location', 'India')}&ShowRadius=False"
               f"&IsPagination=False&SearchResultsModuleName=Search+Results&SearchFiltersModuleName=Search+Filters"
               f"&SortCriteria=5&SortDirection=1&SearchType=5&ResultsType=0")
        r = http.get(s, url, headers={"Accept": "application/json", "X-Requested-With": "XMLHttpRequest"})
        if r.status_code == 200:
            html = r.json().get("results", "")
            out = _parse_links(cfg["name"], html, base, "radancy", location_selector=True)
    except Exception:
        out = []
    if not out and cfg.get("list_path"):
        for page in range(1, 6):
            r = http.get(s, f"{base}{cfg['list_path']}".replace("{page}", str(page)))
            if r.status_code != 200:
                break
            found = _parse_links(cfg["name"], r.text, base, "radancy", location_selector=True)
            if not found:
                break
            out.extend(found)
    return out


# --------------------------------------------------------------------------- SAP SuccessFactors (RMK)
def successfactors(cfg, s):
    base = cfg["base"].rstrip("/")   # e.g. https://jobs.sap.com
    loc = cfg.get("location", "India")
    out = []
    for startrow in range(0, 250, 25):
        url = f"{base}/search/?q=&locationsearch={loc}&startrow={startrow}&sortColumn=referencedate&sortDirection=desc"
        r = http.get(s, url)
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "html.parser")
        rows = soup.select("tr.data-row, li.job-tile, .jobTitle-link")
        got = 0
        for a in soup.select("a.jobTitle-link"):
            row = a.find_parent("tr") or a.find_parent("li")
            loc_txt = ""
            if row:
                l = row.select_one(".jobLocation, .jobLocation-text, [class*=location]")
                loc_txt = l.get_text(" ", strip=True) if l else ""
            out.append(Job(cfg["name"], a.get_text(strip=True), urljoin(base, a.get("href", "")),
                           loc_txt, "", "successfactors"))
            got += 1
        if got < 25:
            break
    return out


# --------------------------------------------------------------------------- Generic HTML
def html(cfg, s):
    """Server-rendered pages: collect job-looking links. cfg: urls (list) or url, optional selector."""
    urls = cfg.get("urls") or [cfg["url"]]
    out = []
    for u in urls:
        r = http.get(s, u)
        if r.status_code != 200:
            raise RuntimeError(f"html {r.status_code} for {u}")
        out.extend(_parse_links(cfg["name"], r.text, u, "html", selector=cfg.get("selector")))
    return out


def _parse_links(company, html_text, base, source, selector=None, location_selector=False):
    soup = BeautifulSoup(html_text or "", "html.parser")
    scope = soup.select(selector) if selector else [soup]
    out, seen = [], set()
    for node in scope:
        for a in node.find_all("a", href=True):
            href = a["href"].strip()
            text = a.get_text(" ", strip=True)
            if not text or len(text) < 5 or len(text) > 140 or text.lower() in NAV_WORDS:
                continue
            if not JOBISH_HREF.search(href):
                continue
            full = urljoin(base, href)
            if full in seen:
                continue
            seen.add(full)
            loc = ""
            parent = a.find_parent(["li", "tr", "div", "article"])
            if parent:
                l = parent.select_one("[class*=location], [class*=Location], .job-location, span.location")
                if l and l is not a:
                    loc = l.get_text(" ", strip=True)[:80]
            out.append(Job(company, text, full, loc, "", source))
    return out


# --------------------------------------------------------------------------- Microsoft
def microsoft(cfg, s):
    out = []
    for pg in range(1, 11):
        url = (f"https://gcsservices.careers.microsoft.com/search/api/v1/search?lc=India&l=en_us"
               f"&pg={pg}&pgSz=20&o=Recent&flt=true")
        r = http.get(s, url, headers={"Accept": "application/json",
                                      "Referer": "https://jobs.careers.microsoft.com/"})
        if r.status_code != 200:
            raise RuntimeError(f"microsoft {r.status_code}")
        res = (r.json().get("operationResult") or {}).get("result") or {}
        jobs = res.get("jobs", [])
        for j in jobs:
            props = j.get("properties") or {}
            locs = props.get("locations") or []
            out.append(Job(cfg["name"], j.get("title", ""),
                           f"https://jobs.careers.microsoft.com/global/en/job/{j.get('jobId')}",
                           "; ".join(locs)[:120], j.get("postingDate", ""), "microsoft"))
        if len(jobs) < 20:
            break
    return out


# --------------------------------------------------------------------------- Browser (lazy)
def browser(cfg, s):
    from .browser import fetch_with_browser
    return fetch_with_browser(cfg)


REGISTRY = {
    "greenhouse": greenhouse, "lever": lever, "smartrecruiters": smartrecruiters, "amazon": amazon,
    "workday": workday, "eightfold": eightfold, "oracle": oracle, "radancy": radancy,
    "successfactors": successfactors, "html": html, "browser": browser, "microsoft": microsoft,
}
