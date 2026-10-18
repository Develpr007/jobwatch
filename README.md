# Jobwatch

Checks the careers pages of 100+ companies every 4 hours and messages you (Telegram and/or email) the moment a new fresher-level analyst / product / growth / operations role in India appears.

No coding needed to run it. It runs for free on GitHub.

## One-time setup (about 20 minutes)

### 1. Put the code on GitHub
1. Create a free account at github.com if you don't have one.
2. Click the "+" at the top right → New repository → name it `jobwatch` → Private → Create.
3. On the new repo page, click "uploading an existing file" → drag the whole contents of this folder in (keep the folder structure: `jobwatch/`, `config/`, `.github/`) → Commit changes.

   If drag-and-drop skips the hidden `.github` folder: click Add file → Create new file → type the name `.github/workflows/jobwatch.yml` → paste the contents of that file → Commit.

### 2. Make a Telegram bot (5 minutes)
1. In Telegram, open **@BotFather** → send `/newbot` → give it a name → it replies with a **token** (looks like `123456:ABC-xyz`). Copy it.
2. Open your new bot's chat and press Start, send it any message.
3. Open **@userinfobot** in Telegram, press Start → it shows your **chat id** (a number). Copy it.

### 3. (Optional) Email alerts via Gmail
1. Google Account → Security → turn on 2-Step Verification.
2. Search "App passwords" in the account settings → create one named `jobwatch` → copy the 16-character password.

### 4. Add the secrets to GitHub
Repo → Settings → Secrets and variables → Actions → New repository secret. Add these (names exactly):

| Name | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | the token from BotFather |
| `TELEGRAM_CHAT_ID` | your chat id |
| `GMAIL_USER` | your gmail address (optional) |
| `GMAIL_APP_PASSWORD` | the app password (optional) |
| `NOTIFY_EMAIL` | where to send alerts, if different (optional) |

### 5. Turn it on
Repo → Actions tab → if asked, click "I understand my workflows, go ahead and enable them" → click **jobwatch** on the left → **Run workflow** → Run.

The first run takes 10–20 minutes. You'll get one message listing every relevant role currently open. After that it runs every 4 hours and only messages you about **new** roles.

## What you'll receive
- Telegram: one message per run with new roles, grouped by company, each a clickable link.
- `output/new_jobs.csv` in the repo: a running log of every new role ever found (open in Excel).
- `output/all_relevant_open.csv`: everything relevant open right now.
- If a company's page stops working for 3 runs in a row, the message ends with a warning line listing it.

## Adding or removing companies
Edit `config/companies.json`. Each company is one block. Three kinds:

```json
{"name": "Some Startup", "adapter": "greenhouse", "token": "somestartup"}
{"name": "Some Startup", "adapter": "lever", "slug": "somestartup"}
{"name": "Some Company", "adapter": "browser", "url": "https://company.com/careers", "india_only": true}
```

To find the right one: open the company's careers page, click a job, look at the address bar.
- `boards.greenhouse.io/XXX` or `job-boards.greenhouse.io/XXX` → greenhouse, token = XXX
- `jobs.lever.co/XXX` → lever, slug = XXX
- `careers.smartrecruiters.com/XXX` → smartrecruiters, company_id = XXX
- `XXX.wdN.myworkdayjobs.com/SITE` → workday, tenant = XXX, pod = wdN, site = SITE
- `XXX.eightfold.ai` → eightfold, base = https://XXX.eightfold.ai, domain = company website
- anything else → browser, url = the page that lists jobs

Set `"enabled": false` to pause a company without deleting it.

## Tuning what counts as "relevant"
`jobwatch/filters.py` has three plain lists at the top: `INCLUDE` (words that make a title interesting), `EXCLUDE` (words that rule it out, e.g. senior, lead, software), and `INDIA` (city names). Add or remove words there. After each run, `state/last_run.json` shows a sample of rejected titles and why, so you can see what the filter is dropping.

## If something breaks
Open the Actions tab → click the failed run → read the red lines. Paste them to Claude and ask for the fix. One company failing never stops the others.

## Running on your own laptop instead (optional)
```
pip install -r requirements.txt
python -m playwright install chromium
python -m jobwatch.main --dry-run --tier 1,2      # quick test without the browser sites
python -m jobwatch.main                            # full run
```
