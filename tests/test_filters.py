from jobwatch.models import Job
from jobwatch.filters import is_relevant
from jobwatch.adapters import _parse_links


def J(title, loc="Bengaluru, India", desc=""):
    return Job("X", title, "https://x.com/jobs/1", loc, "", "t", description=desc)


def test_keep():
    for t in ["Business Analyst", "Data Analyst Intern", "Associate Product Manager", "Growth Associate",
              "Analyst - Risk Management", "Management Trainee", "Graduate Analyst, Financing & Advisory",
              "Operations Associate", "Product Analyst", "Junior Analyst, Risk", "Strategy Intern"]:
        ok, why = is_relevant(J(t))
        assert ok, (t, why)


def test_drop_title():
    for t in ["Senior Data Analyst", "Analyst II", "Lead Product Manager", "Software Development Engineer",
              "Data Engineer", "Vice President - Risk", "Area Sales Manager", "Product Manager",
              "Staff Analyst", "QA Analyst", "Principal Consultant", "Head of Growth"]:
        ok, why = is_relevant(J(t))
        assert not ok, t


def test_drop_location():
    assert not is_relevant(J("Business Analyst", "New York, United States"))[0]
    assert not is_relevant(J("Business Analyst", "Kuala Lumpur, Malaysia"))[0]
    assert is_relevant(J("Business Analyst", "Gurugram"))[0]
    assert is_relevant(J("Business Analyst", "Remote - India"))[0]
    assert is_relevant(J("Business Analyst", ""))[0] is False
    assert is_relevant(Job("X", "Business Analyst", "u", ""), india_only=True)[0]


def test_years():
    assert not is_relevant(J("Business Analyst", desc="Requires 5+ years of experience"))[0]
    assert is_relevant(J("Business Analyst", desc="0-2 years of experience"))[0]
    assert not is_relevant(J("Business Analyst (4-6 years)"))[0]


def test_parse_links():
    html = """<ul><li><a href="/jobs/123-business-analyst">Business Analyst</a><span class="job-location">Pune</span></li>
    <li><a href="/about">About us</a></li><li><a href="/careers">Careers</a></li>
    <li><a href="https://x.com/job/456">Growth Intern</a></li></ul>"""
    jobs = _parse_links("X", html, "https://x.com/careers/", "html")
    titles = sorted(j.title for j in jobs)
    assert titles == ["Business Analyst", "Growth Intern"], titles
    assert jobs[0].location == "Pune"
    assert jobs[0].url == "https://x.com/jobs/123-business-analyst"


def test_dedupe_key():
    a = Job("X", "A", "https://x.com/jobs/1?utm=abc")
    b = Job("X", "A", "https://x.com/jobs/1")
    assert a.key == b.key
