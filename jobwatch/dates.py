"""Turn the many 'posted on' formats job boards use into YYYY-MM-DD, or '' if unknown."""
import re
import datetime as dt

MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def parse_posted(raw, today: dt.date) -> str:
    if raw is None:
        return ""
    s = str(raw).strip()
    if not s:
        return ""
    low = s.lower()

    # epoch seconds or milliseconds (Lever createdAt, Eightfold t_create)
    if re.fullmatch(r"\d{10}(\.\d+)?", s):
        return dt.date.fromtimestamp(float(s)).isoformat()
    if re.fullmatch(r"\d{13}", s):
        return dt.date.fromtimestamp(int(s) / 1000).isoformat()

    # ISO-ish: 2026-10-15, 2026-10-15T08:00:00Z, 2026-10-15 08:00
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return ""

    # Workday relative text: "Posted Today", "Posted Yesterday", "Posted 3 Days Ago", "Posted 30+ Days Ago"
    if "today" in low:
        return today.isoformat()
    if "yesterday" in low:
        return (today - dt.timedelta(days=1)).isoformat()
    m = re.search(r"(\d+)\+?\s*days?\s*ago", low)
    if m:
        return (today - dt.timedelta(days=int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\+?\s*(?:hours?|hrs?|minutes?|mins?)\s*ago", low)
    if m:
        return today.isoformat()
    m = re.search(r"(\d+)\+?\s*weeks?\s*ago", low)
    if m:
        return (today - dt.timedelta(days=7 * int(m.group(1)))).isoformat()
    m = re.search(r"(\d+)\+?\s*months?\s*ago", low)
    if m:
        return (today - dt.timedelta(days=30 * int(m.group(1)))).isoformat()

    # "October 15, 2026", "15 Oct 2026", "Oct 15, 2026", "10/15/2026", "15/10/2026"
    m = re.search(r"([a-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", low)
    if m and m.group(1) in MONTHS:
        try:
            return dt.date(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2))).isoformat()
        except ValueError:
            return ""
    m = re.search(r"(\d{1,2})\s+([a-z]{3})[a-z]*\.?,?\s+(\d{4})", low)
    if m and m.group(2) in MONTHS:
        try:
            return dt.date(int(m.group(3)), MONTHS[m.group(2)], int(m.group(1))).isoformat()
        except ValueError:
            return ""
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        # US sites (Radancy/BlackRock) use MM/DD/YYYY; if first > 12 it must be DD/MM
        mo, d = (a, b) if a <= 12 else (b, a)
        try:
            return dt.date(y, mo, d).isoformat()
        except ValueError:
            return ""
    return ""
