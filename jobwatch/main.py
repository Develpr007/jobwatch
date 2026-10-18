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
from .filters import is_relevant, collapse
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
    fn = REGISTRY[cfg["adapter"]]
    s = http.session()
    t0 = time.time()
    try:
        jobs = fn(cfg, s)
        return cfg, jobs, None, time.time() - t0
    except Exception as e:
        return cfg, [], f"{type(e).__name__}: {str(e)[:160]}", time.time() - t0


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
                j.extra["found"] = now.strftime("%d-%b-%Y")
                new_jobs.append(j)
                seen[j.key] = {"company": j.company, "title": j.title, "url": j.url,
                               "location": j.location, "first_seen": stamp}

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
                         "new": [j.to_dict() for j in new_jobs], "rejected_sample": rejected_sample})

    # ---- notify (identical postings merged; message capped per company so every company is visible)
    new_merged = sorted(collapse(list(new_jobs)), key=lambda x: (x.company, x.title))
    failing = [n for n, h in health.items() if h["fail_streak"] >= 3]
    lines = []
    if first_run:
        header = (f"Jobwatch set up ✅ {len(new_merged)} relevant roles open right now across "
                  f"{len({j.company for j in new_merged})} companies (full list in your sheet)")
        lines = notify.format_jobs(new_merged, header, per_company=6)
    elif new_merged:
        header = f"{len(new_merged)} new role{'s' if len(new_merged) != 1 else ''} — {stamp}"
        lines = notify.format_jobs(new_merged, header, per_company=15)
    new_jobs = new_merged
    if errors and (failing or now.weekday() == 0 and now.hour < 12):
        lines.append(f"\n⚠️ {len(errors)} sources failed this run; {len(failing)} failing 3+ runs: "
                     + ", ".join(failing[:12]))
    if new_jobs and not args.dry_run:
        try:
            print("sheet:", notify.sheet(sorted(new_jobs, key=lambda x: (x.company, x.title))))
        except Exception as e:
            print("sheet error:", e)
    if lines and not args.dry_run:
        sent_tg = notify.telegram(lines)
        sent_mail = False
        if new_jobs or first_run:
            try:
                sent_mail = notify.email(f"Jobwatch: {len(new_jobs)} new roles ({stamp})", lines,
                                         notify.format_jobs_html(new_jobs, lines[0]))
            except Exception as e:
                print("email error:", e)
        print(f"notified: telegram={sent_tg} email={sent_mail}")

    if not args.dry_run:
        save_json(SEEN, seen)
        save_json(HEALTH, health)

    print(f"\n{stamp}: {len(results)} ok, {len(errors)} failed, {len(zero)} empty, "
          f"{len(relevant_all)} relevant open, {len(new_jobs)} new")
    if errors:
        print("failed:", "; ".join(f"{n} ({e})" for n, e in errors))
    return 0


if __name__ == "__main__":
    sys.exit(main())
