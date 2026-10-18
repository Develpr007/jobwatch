"""Decides whether a job is relevant: right kind of role, fresher-level, in India."""
import re
from .models import Job

# ---- Role keywords (edit freely) ------------------------------------------
INCLUDE = [
    r"\banalyst\b", r"\banalytics\b", r"\bdata\b", r"\bbusiness intelligence\b", r"\bbi\b",
    r"\bproduct\b", r"\bapm\b", r"\bgrowth\b", r"\bstrategy\b", r"\bstrateg", r"\bconsult",
    r"\boperations?\b", r"\bops\b", r"\bprogram\b", r"\bproject\b", r"\bcategory\b",
    r"\bmarketing\b", r"\bgtm\b", r"\bgo-to-market\b", r"\bfinance\b", r"\bfinancial\b",
    r"\brisk\b", r"\bresearch\b", r"\binsights?\b", r"\bplanning\b", r"\bsupply chain\b",
    r"\bintern", r"\btrainee\b", r"\bgraduate\b", r"\bfresher", r"\bcampus\b", r"\bearly career",
    r"\bassociate\b", r"\bjunior\b", r"\bentry\b", r"\bapprentice", r"\bmanagement trainee\b",
]

EXCLUDE = [
    r"\bsenior\b", r"\bsr\.?\b", r"\blead\b", r"\bprincipal\b", r"\bdirector\b", r"\bhead\b",
    r"\bvp\b", r"\bvice president\b", r"\bavp\b", r"\bstaff\b", r"\barchitect\b", r"\bchief\b",
    r"\bexecutive director\b", r"\bmanaging\b", r"\bpartner\b", r"\bspecialist iii\b",
    r"\b(ii|iii|iv|2|3|4)\b(?!\s*(?:intern|trainee))",   # "Analyst 2/II" etc. are usually 2-5 yrs
    # engineering-heavy roles the user is not targeting
    r"\bsoftware\b", r"\bsde\b", r"\bdeveloper\b", r"\bengineer(?!ing operations)", r"\bbackend\b",
    r"\bfrontend\b", r"\bfull ?stack\b", r"\bdevops\b", r"\bsre\b", r"\bqa\b", r"\btest(ing)?\b",
    r"\bandroid\b", r"\bios\b", r"\bmachine learning engineer\b", r"\bml engineer\b",
    # obviously-not-fresher functions
    r"\bsales manager\b", r"\barea sales\b", r"\bbranch\b", r"\bnurse\b", r"\bdriver\b",
    r"\bsecurity guard\b", r"\bchef\b", r"\bpharmacist\b", r"\bdoctor\b", r"\btax\b(?!.*analyst)",
]

# "manager" is excluded unless it is a fresher-ish product title
MANAGER_OK = [r"\bassociate product manager\b", r"\bapm\b", r"\bjunior product manager\b",
              r"\bproduct manager (?:i|1|intern|trainee)\b", r"\bmanagement trainee\b"]

# ---- Location --------------------------------------------------------------
INDIA = [
    "india", "bengaluru", "bangalore", "mumbai", "pune", "hyderabad", "chennai", "gurugram",
    "gurgaon", "noida", "delhi", "ncr", "kolkata", "ahmedabad", "jaipur", "lucknow", "indore",
    "bhubaneswar", "kochi", "cochin", "trivandrum", "thiruvananthapuram", "coimbatore",
    "chandigarh", "mohali", "nagpur", "vadodara", "surat", "mysuru", "mysore", "visakhapatnam",
    "vizag", "ranchi", "jamshedpur", "patna", "bhopal", "karnataka", "maharashtra", "telangana",
    "tamil nadu", "haryana", "uttar pradesh", "west bengal", "gujarat", "kerala", "remote - india",
    "remote, india", "india remote",
]
NON_INDIA_HINTS = ["united states", "usa", "u.s.", "united kingdom", "london", "new york",
                   "singapore", "dubai", "uae", "malaysia", "philippines", "poland", "canada",
                   "australia", "sydney", "germany", "france", "ireland", "japan", "china",
                   "hong kong", "mexico", "brazil", "spain", "italy", "netherlands", "israel"]

YEARS = re.compile(r"(\d{1,2})\s*\+?\s*(?:-|to|–)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)\b", re.I)


def _any(patterns, text):
    return any(re.search(p, text, re.I) for p in patterns)


def is_india(location: str, india_only: bool) -> bool:
    loc = (location or "").lower().strip()
    if not loc:
        return india_only
    if any(h in loc for h in NON_INDIA_HINTS) and not any(i in loc for i in INDIA):
        return False
    if india_only:
        return True
    return any(i in loc for i in INDIA)


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
        return False, "no role keyword"
    yrs = min_years(t + " " + (job.description or "")[:2000])
    if yrs is not None and yrs > max_years:
        return False, f"asks {yrs}+ years"
    return True, "ok"
