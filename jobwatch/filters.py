"""Decides whether a job is relevant: right kind of role, fresher-level, in India.

Tuning: edit the three lists INCLUDE / EXCLUDE / INDIA. A title must match at least one INCLUDE
phrase and none of the EXCLUDE ones. state/last_run.json shows a sample of what was rejected and why.
"""
import re
from .models import Job

# ---- Role phrases: the title must contain one of these -------------------------------
INCLUDE = [
    # analytics / data
    r"\banalyst\b", r"\banalytics\b", r"\bbusiness intelligence\b", r"\bdata scien(ce|tist)\b",
    r"\bdata (associate|intern|trainee|analytics)\b", r"\binsights?\b", r"\bresearch (analyst|associate|intern|trainee)\b",
    # product
    r"\bproduct (analyst|manager|associate|operations|intern|trainee|specialist)\b", r"\bassociate product\b", r"\bapm\b",
    # growth / strategy / consulting / business
    r"\bgrowth\b", r"\bstrateg(y|ic|ist)\b", r"\bconsult(ant|ing)\b", r"\bbusiness (associate|intern|trainee|operations)\b",
    r"\bcategory (associate|analyst|intern|management)\b", r"\bmarketing (analyst|associate|intern)\b",
    r"\bprogram(me)? (analyst|associate|intern)\b", r"\bproject (analyst|associate|intern)\b",
    r"\bfinanc(e|ial) (analyst|associate|intern)\b", r"\brisk (analyst|associate|intern)\b",
    r"\bsupply chain (analyst|associate|intern)\b", r"\boperations (analyst|intern|trainee)\b",
    r"\bplanning (analyst|associate|intern)\b", r"\bpricing (analyst|associate)\b", r"\bgtm\b", r"\bgo-to-market\b",
    # fresher programmes
    r"\bintern(ship|s)?\b", r"\btrainee\b", r"\bgraduate\b", r"\bfresher", r"\bcampus\b", r"\bearly[ -]careers?\b",
    r"\bapprentice", r"\bmanagement trainee\b", r"\banalyst program(me)?\b", r"\bnew grad\b", r"\bentry[ -]level\b",
]

# ---- Rule-outs: any of these in the title rejects it ------------------------------------
EXCLUDE = [
    # seniority
    r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bprincipal\b", r"\bdirector\b", r"\bhead\b", r"\bchief\b",
    r"\bvp\b", r"\bvice president\b", r"\bavp\b", r"\bstaff\b", r"\barchitect\b", r"\bmanaging\b", r"\bpartner\b",
    r"\bexpert\b", r"\bspecialist\b", r"\b(ii|iii|iv|v|2|3|4|5)\b(?!\s*(?:intern|trainee))",
    # engineering / tech
    r"\bsoftware\b", r"\bsde\b", r"\bdeveloper\b", r"\bengineer(ing)?\b", r"\bbackend\b", r"\bfrontend\b",
    r"\bfull ?stack\b", r"\bdevops\b", r"\bsre\b", r"\bqa\b", r"\btest(ing|er)?\b", r"\bandroid\b", r"\bios\b",
    r"\bscientist\b", r"\btechnician\b", r"\btech\b", r"\bsap\b", r"\bsalesforce (admin|developer)\b",
    r"\bcyber", r"\bsecurity\b", r"\bnetwork\b", r"\bcloud\b", r"\binfra", r"\bdatabase\b", r"\bdba\b",
    r"\bml data\b", r"\bannotation\b", r"\blabel(l)?ing\b", r"\btranscription\b",
    # ops / support / field roles that share words with analyst titles
    r"\b(customer|technical|tech|it|application|desktop|product) support\b", r"\bsupport (executive|associate|specialist|engineer|agent|representative|analyst)\b", r"\bescalation\b", r"\bwarehouse\b", r"\bfulfil(l)?ment\b", r"\blogistics (specialist|associate|executive)\b",
    r"\bdata cent(er|re)\b", r"\bmaintenance\b", r"\bdevice associate\b", r"\bdigital associate\b", r"\bsvc associate\b",
    r"\bcustomer (service|support|care|success)\b", r"\bcall cent", r"\bcontact cent", r"\bcollections?\b",
    r"\baccount manag", r"\bmerchandiser\b", r"\bcoach\b", r"\bexecutive\b", r"\bofficer\b", r"\badvocacy\b",
    r"\bmoderat", r"\bquality (associate|analyst|auditor)\b", r"\bprocess associate\b", r"\btransaction", r"\bprocessing\b",
    r"\bsales (associate|executive|manager|officer)\b", r"\barea sales\b", r"\bbranch\b", r"\btelecall", r"\bfield\b",
    r"\bhr\b", r"\bhuman resources\b", r"\brecruit", r"\btalent acquisition\b", r"\bpayroll\b", r"\badmin\b",
    r"\blegal\b", r"\bcompliance officer\b", r"\btax\b", r"\baudit(or)?\b", r"\baccountant\b", r"\baccounting\b",
    r"\bnurse\b", r"\bdoctor\b", r"\bpharmac", r"\bchef\b", r"\bdriver\b", r"\bguard\b", r"\bcontent writer\b",
    r"\bdesigner\b", r"\bvideo\b", r"\bcopywriter\b", r"\bsocial media\b",
    # language-specific roles
    r"\b(german|french|spanish|japanese|italian|portuguese|mandarin|korean|arabic|dutch)\b", r"\blanguage\b",
]

# "manager" is excluded unless it is a fresher-ish product title
MANAGER_OK = [r"\bassociate product manager\b", r"\bapm\b", r"\bjunior product manager\b",
              r"\bproduct manager (?:i|1|intern|trainee)\b", r"\bmanagement trainee\b", r"\bmanager trainee\b"]

# ---- Location ---------------------------------------------------------------------------
INDIA = [
    "india", "ind", "bengaluru", "bangalore", "mumbai", "pune", "hyderabad", "chennai", "gurugram",
    "gurgaon", "noida", "delhi", "ncr", "kolkata", "ahmedabad", "jaipur", "lucknow", "indore",
    "bhubaneswar", "kochi", "cochin", "trivandrum", "thiruvananthapuram", "coimbatore",
    "chandigarh", "mohali", "nagpur", "vadodara", "surat", "mysuru", "mysore", "visakhapatnam",
    "vizag", "ranchi", "jamshedpur", "patna", "bhopal", "karnataka", "maharashtra", "telangana",
    "tamil nadu", "haryana", "uttar pradesh", "west bengal", "gujarat", "kerala",
]
NON_INDIA_HINTS = ["united states", "usa", "u.s.", "united kingdom", "london", "new york",
                   "singapore", "dubai", "uae", "malaysia", "philippines", "poland", "canada",
                   "australia", "sydney", "germany", "france", "ireland", "japan", "china",
                   "hong kong", "mexico", "brazil", "spain", "italy", "netherlands", "israel", "indonesia"]

YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|to|–)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b", re.I)


def _any(patterns, text):
    return any(re.search(p, text, re.I) for p in patterns)


def is_india(location: str, india_only: bool) -> bool:
    loc = (location or "").lower().strip()
    if not loc:
        return india_only
    words = re.findall(r"[a-z.]+", loc)
    if any(h in loc for h in NON_INDIA_HINTS) and not any(i in words or i in loc for i in INDIA if len(i) > 3):
        return False
    if india_only:
        return True
    return any((i in words) if len(i) <= 3 else (i in loc) for i in INDIA)


def min_years(text: str):
    """Smallest 'N years' figure mentioned, or None."""
    vals = []
    for m in YEARS.finditer(text or ""):
        try:
            vals.append(int(m.group(1)))
        except ValueError:
            pass
    return min(vals) if vals else None


def is_relevant(job: Job, india_only: bool = False, max_years: int = 2) -> tuple[bool, str]:
    t = (job.title or "").strip()
    tl = t.lower()
    if len(tl) < 4:
        return False, "no title"
    if not is_india(job.location, india_only):
        return False, f"location '{job.location}' not India"
    if "manager" in tl and not _any(MANAGER_OK, tl):
        return False, "manager-level"
    if _any(EXCLUDE, tl):
        return False, "excluded keyword"
    if not _any(INCLUDE, tl):
        return False, "no role phrase"
    yrs = min_years(t + " " + (job.description or "")[:3000])
    if yrs is not None and yrs > max_years:
        return False, f"asks {yrs}+ years"
    return True, "ok"


def collapse(jobs):
    """Merge postings that are the same company + title + location (Amazon posts one per seat)."""
    groups = {}
    for j in jobs:
        k = (j.company, re.sub(r"\s+", " ", j.title.strip().lower()), j.location.strip().lower())
        if k in groups:
            groups[k].extra["count"] = groups[k].extra.get("count", 1) + 1
        else:
            j.extra.setdefault("count", 1)
            groups[k] = j
    return list(groups.values())
