# LinkedIn Mission Tracker

Daily automation that scrapes LinkedIn for freelance mission posts, scores them against your consultant profile using Claude AI, and writes results to Google Sheets.

Runs automatically every day at **06:00 UTC** (08:00 CEST / 07:00 CET) via GitHub Actions.

---

## How it works

```
1. Read config from Paramètres tab (your profile, countries, keywords)
2. Scrape LinkedIn posts via BeReach API for each country × keyword pair
3. Score each post with Claude Haiku against your profile vector
4. Write scored results to Missions tab — deduplicated across runs
```

Posts below your score threshold are discarded. Everything else lands in your sheet with match score, extracted skills, TJM, location, and top 3 match reasons.

---

## Setup (~15 minutes)

### Step 1 — Copy the Google Sheets template

**[Open the template →](https://docs.google.com/spreadsheets/d/e/2PACX-1vS4MfF5gNZ0lBo2PbGi2pvntAXCfv2mc11JpB5OsYUK7kjWiVSfH3JSU2BoYxx4Q-gYz7TwG23QoxGf/pubhtml)**

1. Click **File → Make a copy**
2. From the URL of your copy, note the spreadsheet **ID** (`/spreadsheets/d/**ID**/edit`) — you'll need it in Step 5

The template includes all required tabs. The pipeline fills them automatically on first run — you only need to fill `Paramètres`.

---

### Step 2 — Fill in the Paramètres tab

Open `Paramètres` in your copy and fill in your information:

| Row key | What to enter | Example |
|---------|--------------|---------|
| `profil` | Your LinkedIn **public** profile URL | `https://linkedin.com/in/john-doe/` |
| `pays` | One target country per row | `France`, `Belgium` |
| `keyword` | Boolean search queries (one per row) | `"mission" AND "freelance" AND "PMO"` |
| `remote_keyword` | Same format for full-remote jobs | `"full remote" AND "PMO"` |
| `score_minimum` | Min relevance score to keep (0–100) | `50` |
| `posts_max_par_pays` | Max posts per country per run | `50` |

> **Tip**: Use LinkedIn boolean syntax — `AND`, `OR`, quoted phrases. Start broad, tune later directly in this tab without touching code.

---

### Step 3 — Get your API tokens

| Token | Service | Where to get it |
|-------|---------|----------------|
| `BEREACH_API_TOKEN` | BeReach — post scraping + profile fetch | [bereach.co](https://bereach.co) → dashboard |
| `ANTHROPIC_API_KEY` | Claude AI — post scoring | [console.anthropic.com](https://console.anthropic.com) → API Keys |

> BeReach handles both LinkedIn post scraping and LinkedIn profile fetching. A paid plan is recommended for daily use — free tier has volume limits. Claude Haiku is extremely cheap (~$1–5/month).

---

### Step 4 — Google Service Account (Sheets access)

1. Go to [console.cloud.google.com](https://console.cloud.google.com) — create or select a project
2. Enable the **Google Sheets API**: *APIs & Services → Library → "Google Sheets API" → Enable*
3. Create a **Service Account**: *IAM & Admin → Service Accounts → Create* (name it anything, e.g. `sheets-writer`)
4. Generate a **JSON key**: click the service account → *Keys → Add Key → JSON* → file downloads
5. Convert it to a single escaped line (required for GitHub secret):

```bash
python -c "import json,sys; d=json.load(open(sys.argv[1])); print(json.dumps(d))" service_account.json
```

Copy the output — it starts with `{"type":"service_account",...}`.

6. **Share your Google Sheet** with the `client_email` from the JSON as **Editor**

---

### Step 5 — Fork the repo and set GitHub secrets

1. **Fork** this repository on GitHub
2. Go to your fork: *Settings → Secrets and variables → Actions → New repository secret*
3. Add all 4 secrets:

| Secret | Value |
|--------|-------|
| `BEREACH_API_TOKEN` | From Step 3 |
| `ANTHROPIC_API_KEY` | From Step 3 |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Single-line JSON output from Step 4 |
| `SPREADSHEET_ID` | Spreadsheet ID from Step 1 |

---

### Step 6 — Trigger your first run

1. In your fork: **Actions → daily_extract → Run workflow**
2. Wait 3–5 minutes
3. Open your Google Sheet — check the **Missions** tab for results

> If it fails, download the log artifact from the Actions run page and check the error.

---

## What happens on first run

```
Paramètres tab read         → your config loaded (profile, countries, keywords)
Profils_Cache checked       → empty → cache miss
BeReach called              → your LinkedIn profile fetched and cached
Posts scraped (BeReach)     → for each country × keyword pair
Posts scored (Claude)       → each post matched against your profile
Results written             → Missions tab populated
Dedup_Index updated         → no duplicates on future runs
```

## Subsequent runs (daily, 06:00 UTC)

```
Profils_Cache hit           → no profile API call → fast startup
Dedup_Index checked         → only new posts processed
New results appended        → Missions tab grows daily
```

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `Placeholder values detected` | Paramètres tab not filled | Complete Step 2 |
| `KeyError: BEREACH_API_TOKEN` | Missing env variable | Check all 4 secrets are set in Step 5 |
| `APIError: 403` on Sheets | Sheet not shared | Share with service account `client_email` as Editor (Step 4.6) |
| `json.JSONDecodeError` on startup | Malformed `GOOGLE_SERVICE_ACCOUNT_JSON` | Re-run the Python one-liner in Step 4.5 |
| 0 posts returned | Keywords too narrow or API issue | Check `logs/run_YYYY-MM-DD.log` artifact; try broader keywords |
| Score always 0 | Profile URL not reachable | Verify `profil` URL in Paramètres is a public LinkedIn profile |

---

## Cost estimate

| Service | Free tier | Paid |
|---------|-----------|------|
| BeReach | Limited | ~$30–100/month |
| Anthropic Claude | $5 credit | ~$1–5/month (Haiku) |
| Google Sheets API | Always free | Free |
| GitHub Actions | 2,000 min/month | Free for this use case |

---

## Architecture

```
run.py (orchestrator)
├── config/config.py           — load & validate AppConfig
├── sheets/sheets_writer.py    — read Paramètres (config override)
│                              — load Profils_Cache + Dedup_Index
├── scraper/bereach_scraper.py — BeReach API: post scraping
├── matcher/profile_matcher.py — BeReach API: profile fetch + Claude Haiku scoring
└── sheets/sheets_writer.py    — write results + update Dedup_Index
```

Config priority: `Paramètres` tab (runtime) → `config/settings.json` (bootstrap defaults)

Two pipelines run daily:
- `daily_extract.yml` — 06:00 UTC — freelance missions → `Missions` tab
- `daily_remote.yml` — 06:30 UTC — remote jobs → `Remote` tab

---

## Customizing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidance on adapting keywords, scoring logic, and adding new countries.
