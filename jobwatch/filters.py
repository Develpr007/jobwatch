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
    yrs = min_years(t)
    if yrs is not None and yrs > max_years:
        return False, f"title says {yrs}+ years"
    return True, "ok"


# ---- Second pass: read the job description ---------------------------------------------
# Strong fresher signals: these override a years figure (a JD saying "0-2 years" or "campus hire" wins).
FRESHER_STRONG = [
    r"\bfreshers?\b", r"\b0\s*(?:-|to|–)\s*[123]\s*(?:\+\s*)?(?:years?|yrs?)\b", r"\bno (?:prior )?(?:work )?experience (?:required|needed|necessary)\b",
    r"\bentry[ -]level\b", r"\bcampus (?:hire|hiring|recruit|programme|program|placement)\b", r"\bgraduate (?:program|programme|trainee|hire|scheme|analyst)\b",
    r"\bnew grad", r"\brecent graduates?\b", r"\bfinal[ -]year\b", r"\b202[67] (?:batch|pass ?outs?|graduates?|grads?)\b",
    r"\bmanagement trainee\b", r"\bearly[ -]careers?\b", r"\banalyst program(?:me)?\b",
]
# Weak signals: accepted only when nothing contradicts them.
FRESHER_WEAK = [r"\bintern(?:ship)?s?\b", r"\btrainee\b", r"\bapprentice"]

# Years of experience, counted only when the sentence is about experience.
EXP_PATTERNS = [
    r"\b(\d{1,2})\s*\+?\s*(?:-|to|–)\s*(\d{1,2})\s*\+?\s*(?:years?|yrs?)(?:[^.;]{0,60}?)(?:experience|exp\b|work|background|track record)",
    r"\b(\d{1,2})\s*\+\s*(?:years?|yrs?)(?:[^.;]{0,60}?)(?:experience|exp\b|work|background)",
    r"(?:minimum|min\.?|at least|atleast|more than|over)\s*(?:of\s*)?(\d{1,2})\s*\+?\s*(?:years?|yrs?)(?:[^.;]{0,60}?)(?:experience|exp\b|work|background)",
    r"\b(\d{1,2})\s*\+?\s*(?:years?|yrs?)(?:'|’)?\s*(?:of\s*)?(?:relevant |prior |work |professional |hands[- ]on |industry |total |overall |post[- ]qualification |pqe )?(?:experience|exp\b)",
    r"experience\s*(?:required|needed|level)?\s*[:\-–]\s*(\d{1,2})\s*\+?",
    r"years? of experience\s*(?:required|needed)?\s*[:\-–]?\s*(\d{1,2})\s*\+?",
    r"(?:experience|exp)\s*(?:of|:)?\s*(\d{1,2})\s*\+?\s*(?:-|to|–)?\s*(\d{1,2})?\s*\+?\s*(?:years?|yrs?)",
]
# Company boilerplate that also mentions years; matches near these words are ignored.
BOILERPLATE = r"(history|heritage|legacy|founded|established|in business|serving|clients? for|track record of|innovation|old\b|company|firm has|we have|our|celebrat)"

DEGREE_HARD = [
    r"\bmba\b", r"\bpgdm\b", r"\bpgdbm\b", r"\bpgp\b", r"\bchartered accountant", r"\bca\b(?!\s*freshers?)(?=[^.;]{0,40}\b(?:qualified|required|must|mandatory|degree|final|inter)\b)",
    r"\bcfa\b(?=[^.;]{0,40}\b(?:required|must|mandatory|charter|level)\b)", r"\bfrm\b(?=[^.;]{0,40}\b(?:required|must|mandatory)\b)",
    r"\bcompany secretary\b", r"\bicwa\b", r"\bcma\b", r"\bacca\b", r"\bactuar",
    r"\bph\.?d\b", r"\bdoctorate\b", r"\bmaster(?:'|’)?s? (?:degree|of|in)\b", r"\bpost[- ]?graduat(?:e|ion)\b", r"\bm\.?sc\b", r"\bm\.?com\b", r"\bm\.?tech\b", r"\bm\.?e\.\b",
    r"\bb\.?des\b", r"\bm\.?des\b", r"\bbachelor of design\b", r"\bmaster of design\b", r"\bllb\b", r"\bll\.m\b", r"\bmaster of laws\b",
    r"\bmbbs\b", r"\bbds\b", r"\bb\.?pharm", r"\bm\.?pharm",
]
# If the same sentence says any of these, the degree is optional (or a B.Tech is listed as an alternative).
SOFT_WORDS = (r"(preferred|preferably|plus\b|advantage|nice to have|good to have|desirable|bonus|ideally|or equivalent|optional|would be|"
              r"b\.?tech|b\.?e\b|bachelor|engineering|any graduate|graduate in any|any discipline|any stream|graduates? (?:or|/)|undergraduate)")
LATERAL = [r"\bexperienced hires? only\b", r"\blateral hir", r"\bexperienced professionals? only\b", r"\bnot (?:open|suitable) (?:to|for) freshers\b"]

REQ_HEADS = re.compile(
    r"(basic qualifications|minimum qualifications|preferred qualifications|qualifications|requirements|required skills|"
    r"what you(?:'|’)ll need|what we(?:'|’)re looking for|what we look for|who you are|about you|skills and experience|"
    r"skills & experience|experience required|eligibility|your profile|must have|to qualify|desired profile|candidate profile|"
    r"required experience|key skills|what you bring|ideal candidate|job requirements|educational qualification|education qualification|"
    r"years of experience|experience level|what you(?:'|’)ll bring|you have|we(?:'|’)re looking for|education|degree|"
    r"skills required|skill ?sets?|profile)", re.I)
END_HEADS = re.compile(
    r"(about (?:us|the company|the team|the firm)|why join|benefits|what we offer|perks|equal opportunity|eeo\b|we are an equal|"
    r"diversity|inclusion statement|similar jobs|related jobs|recommended jobs|jobs you may|people also viewed|share this job|"
    r"privacy|cookie|apply now|job id|requisition id|posting date)", re.I)


def requirements_section(text: str) -> str:
    """The part of the page most likely to hold the requirements. Falls back to the whole text, trimmed."""
    t = text or ""
    m = REQ_HEADS.search(t)
    if m:
        seg = t[max(0, m.start() - 200): m.start() + 5000]
        e = END_HEADS.search(seg, 200)
        if e:
            seg = seg[: e.start()]
        return seg
    e = END_HEADS.search(t, 500)
    return t[: e.start()] if e else t[:6000]


def min_experience(text: str):
    """Smallest minimum-years figure asked for, ignoring company-history sentences. None if never stated."""
    t = (text or "").lower()
    vals = []
    for pat in EXP_PATTERNS:
        for m in re.finditer(pat, t):
            window = t[max(0, m.start() - 80): m.start()]
            if re.search(BOILERPLATE, window):
                continue
            try:
                v = int(m.group(1))
            except (ValueError, IndexError, TypeError):
                continue
            if 0 <= v <= 15:          # "50+ years of heritage", "100 years" etc. are not job requirements
                vals.append(v)
    return min(vals) if vals else None


def hard_degree(text: str):
    """First degree that is required (not merely preferred, and not offered alongside a bachelor's), or None."""
    t = (text or "").lower()
    for sent in re.split(r"(?<=[.;!?•·])\s+|\s[-–•]\s|\n", t):
        for pat in DEGREE_HARD:
            m = re.search(pat, sent)
            if m and not re.search(SOFT_WORDS, sent):
                return m.group(0)
    return None


def qualifies(description: str, max_years: int = 1) -> tuple[bool, str]:
    """Second-pass check on the full description. Unknown (no description) -> keep, flagged."""
    if not description or len(description) < 120:
        return True, "description not readable (unverified)"
    req = requirements_section(description).lower()
    full = description.lower()
    if _any(LATERAL, req) or _any(LATERAL, full):
        return False, "experienced hires only"
    deg = hard_degree(req)
    if deg:
        return False, f"requires {deg.upper()}"
    if _any(FRESHER_STRONG, req):
        return True, "fresher-friendly"
    yrs = min_experience(req)
    if yrs is None:
        yrs = min_experience(full)          # requirements may sit outside the section we found
    if yrs is not None and yrs > max_years:
        return False, f"asks {yrs}+ years"
    if _any(FRESHER_STRONG, full):
        return True, "fresher-friendly"
    if _any(FRESHER_WEAK, req):
        return True, "fresher-friendly"
    return True, "ok" if yrs is not None else "no experience stated"


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
