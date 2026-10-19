"""Sends alerts. Telegram if TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are set; email if
GMAIL_USER + GMAIL_APP_PASSWORD are set. Both optional; the run still logs to CSV."""
import os
import smtplib
import html as htmlmod
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests


def _chunks(lines, limit=3800):
    buf, size = [], 0
    for ln in lines:
        if size + len(ln) + 1 > limit and buf:
            yield "\n".join(buf)
            buf, size = [], 0
        buf.append(ln)
        size += len(ln) + 1
    if buf:
        yield "\n".join(buf)


def telegram(text_lines):
    tok, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if not tok or not chat:
        return False
    for chunk in _chunks(text_lines):
        r = requests.post(f"https://api.telegram.org/bot{tok}/sendMessage",
                          json={"chat_id": chat, "text": chunk, "parse_mode": "HTML",
                                "disable_web_page_preview": True}, timeout=30)
        if r.status_code != 200:
            print("telegram error:", r.text[:200])
    return True


def email(subject, text_lines, html_body=None):
    user, pwd = os.getenv("GMAIL_USER"), os.getenv("GMAIL_APP_PASSWORD")
    to = os.getenv("NOTIFY_EMAIL", user)
    if not user or not pwd:
        return False
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText("\n".join(text_lines), "plain"))
    if html_body:
        msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
        srv.login(user, pwd)
        srv.sendmail(user, [to], msg.as_string())
    return True


def sheet(jobs):
    """Append new roles to the user's Google Sheet via its Apps Script web app (SHEETS_WEBHOOK_URL)."""
    url = os.getenv("SHEETS_WEBHOOK_URL")
    if not url or not jobs:
        return False
    rows = [[j.extra.get("found", ""), j.extra.get("posted", ""), j.company, j.title, j.location, j.url,
             j.extra.get("verdict", "")] for j in jobs]
    r = requests.post(url, json={"rows": rows}, timeout=60, allow_redirects=True)
    if r.status_code != 200 or "ok" not in r.text[:200].lower():
        print("sheet error:", r.status_code, r.text[:200])
        return False
    return True


def format_jobs(jobs, header, per_company=None):
    """Telegram-HTML lines, one per job, grouped by company, optionally capped per company."""
    lines = [f"<b>{htmlmod.escape(header)}</b>"]
    by_company = {}
    for j in jobs:
        by_company.setdefault(j.company, []).append(j)
    for company in sorted(by_company):
        items = by_company[company]
        lines.append(f"\n<b>{htmlmod.escape(company)}</b> ({len(items)})")
        shown = items[:per_company] if per_company else items
        for j in shown:
            loc = f" — {htmlmod.escape(j.location)}" if j.location else ""
            n = j.extra.get("count", 1)
            cnt = f" ×{n}" if n > 1 else ""
            v = j.extra.get("verdict", "")
            flag = " ⚠️" if "unverified" in v else ""
            lines.append(f"• <a href=\"{htmlmod.escape(j.url)}\">{htmlmod.escape(j.title)}</a>{cnt}{loc}{flag}")
        if per_company and len(items) > per_company:
            lines.append(f"  …+{len(items) - per_company} more in
