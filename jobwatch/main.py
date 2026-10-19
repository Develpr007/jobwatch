"""Entry point: python -m jobwatch.main [--dry-run] [--only Name] [--no-browser] [--tier 1,2,3]"""
import argparse
import csv
import json
import os
import sys
import time
import datetime as dt
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from .adapters import REGISTRY
from .filters import is_relevant, collapse, qualifies
from .details import enrich
from .dates import parse_posted
from . import http, notify

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "companies.json"
STATE_DIR = ROOT / "state"
OUT_DIR = ROOT / "output"
SEEN = STATE_DIR / "seen.json"
HEALTH = STATE_DIR / "health.json"
LAST_RUN = STATE_DIR / "last_run.json"
NEW_CSV = OUT_DIR / "new_jobs.csv"
ALL_CSV = OUT_DIR / "all_relevant_open.csv"
IST = dt.timezone(dt.timedelta(hours=5, minutes=30))


def load_json(p, default):
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return default
    return default


def save_json(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def run_one(cfg):
    """Run the configured adapter; if it fails or finds nothing and a fallback_url is set, read that page in a browser."""
    fn = REGISTRY[cfg["adapter"]]
    s = http.session()
    t0 = time.time()
    err = None
    try:
        jobs = fn(cfg, s)
    except Exception as e:
        jobs, err = [], f"{type(e).__name__}: {str(e)[:160]}"
    if not jobs and cfg.get("fallback_url") and cfg["adapter"] != "browser":
        fb = dict(cfg); fb["adapter"] = "browser"; fb["url"] = cfg["fallback_url"]; fb.pop("urls", None)
        try:
            jobs = REGISTRY["browser"](fb, s)
            if jobs:
                err = None
                print(f"[fb]   {cfg['name']:<32} primary {'failed' if err else 'empty'}, browser fallback found {len(jobs)}")
        except Exception as e:
            err = err or f"{type(e).__name__}: {str(e)[:160]}"
    return cfg, jobs, err, time.time() - t0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="don't send alerts, don't update state")
    ap.add_argument("--only", help="run a single company (name substring)")
    ap.add_argument("--no-browser", action="store_true", help="skip browser-based sources")
    ap.add_argument("--tier", help="comma list of tiers to run, e.g. 1,2")
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args(argv)

    companies = json.loads(CONFIG.read_text(encoding="utf-8"))
    if args.only:
        companies = [c for c in companies if args.only.lower() in c["name"].lower()]
    if args.tier:
        tiers = {int(x) for x in args.tier.split(",")}
        companies = [c for c in companies if c.get("tier", 3) in tiers]
    if args.no_browser:
        companies = [c for c in companies if c["adapter"] != "browser"]
    companies = [c for c in companies if c.get("enabled", True)]

    seen = load_json(SEEN, {})
    first_run = not SEEN.exists()
    health = load_json(HEALTH, {})
    now = dt.datetime.now(IST)
    stamp = now.strftime("%Y-%m-%d %H:%M IST")

    results, errors, zero = [], [], []
    # browser jobs are heavier; run them with fewer threads
    light = [c for c in companies if c["adapter"] != "browser"]
    heavy = [c for c in companies if c["adapter"] == "browser"]
    for group, workers in ((light, args.workers), (heavy, 2)):
        if not group:
            continue
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(run_one, c) for c in group]
            for f in as_completed(futs):
                cfg, jobs, err, secs = f.result()
                h = health.setdefault(cfg["name"], {"fail_streak": 0, "zero_streak": 0, "last_ok": None, "last_error": None})
                if err:
                    errors.append((cfg["name"], err))
                    h["fail_streak"] += 1
                    h["last_error"] = f"{stamp}: {err}"
                    print(f"[FAIL] {cfg['name']:<32} {err}")
                    continue
                h["fail_streak"] = 0
                h["last_ok"] = stamp
                if not jobs:
                    zero.append(cfg["name"])
                    h["zero_streak"] += 1
                else:
                    h["zero_streak"] = 0
                print(f"[ok]   {cfg['name']:<32} {len(jobs):>4} jobs  {secs:4.1f}s")
                results.append((cfg, jobs))

    # ---- filter + diff
    relevant_all, new_jobs, rejected_sample = [], [], []
    for cfg, jobs in results:
        for j in jobs:
            ok, why = is_relevant(j, india_only=cfg.get("india_only", False), max_years=cfg.get("max_years", 2))
            if not ok:
                if len(rejected_sample) < 400:
                    rejected_sample.append({"company": j.company, "title": j.title, "location": j.location, "why": why})
                continue
            relevant_all.append(j)
            if j.key not in seen:
                j.extra["cfg"] = cfg
                new_jobs.append(j)

    # ---- second pass: read each new candidate's full description for experience / degree requirements
    cand = list(new_jobs)
    new_jobs, dropped_qual = [], []
    print(f"\nreading {len(cand)} job descriptions...")

    def check(j):
        s = http.session()
        enrich(j, j.extra["cfg"], s, allow_browser=not args.no_browser)
        return j, qualifies(j.description, max_years=j.extra["cfg"].get("max_years", 1))

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for j, (ok, why) in ex.map(check, cand):
            j.extra.pop("cfg", None)
            seen[j.key] = {"company": j.company, "title": j.title, "url": j.url, "location": j.location,
                           "first_seen": stamp, "verdict": why}
            if ok:
                j.extra["found"] = now.strftime("%Y-%m-%d")
                j.extra["posted"] = parse_posted(j.posted, now.date())
                j.extra["verdict"] = "" if why == "ok" else why
                new_jobs.append(j)
            else:
                dropped_qual.append({"company": j.company, "title": j.title, "url": j.url, "why": why})
    print(f"kept {len(new_jobs)}, dropped {len(dropped_qual)} after reading descriptions")
    if dropped_qual:
        from collections import Counter
        reasons = Counter(d["why"] for d in dropped_qual)
        print("drop reasons:", "; ".join(f"{k} ×{v}" for k, v in reasons.most_common()))
        for d in dropped_qual[:40]:
            print(f"   - {d['company']}: {d['title']}  [{d['why']}]")

    # ---- outputs
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with ALL_CSV.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["company", "title", "location", "url", "posted", "source"])
        for j in sorted(relevant_all, key=lambda x: (x.company, x.title)):
            w.writerow([j.company, j.title, j.location, j.url, j.posted, j.source])
    if new_jobs and not args.dry_run:
        new_file = not NEW_CSV.exists()
        with NEW_CSV.open("a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            if new_file:
                w.writerow(["first_seen", "company", "title", "location", "url", "source"])
            for j in new_jobs:
                w.writerow([stamp, j.company, j.title, j.location, j.url, j.source])
    save_json(LAST_RUN, {"when": stamp, "sources_ok": len(results), "sources_failed": errors,
                         "sources_zero": zero, "relevant_open": len(relevant_all),
                         "new": [{k: v for k, v in j.to_dict().items() if k != "description"} for j in new_jobs], "dropped_after_reading"
