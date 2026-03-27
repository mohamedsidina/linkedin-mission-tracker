# LinkedIn Freelance Mission Tracker

Daily automation that scrapes LinkedIn for freelance mission posts, scores them against a consultant profile using Claude AI, and writes results to Google Sheets.

Runs automatically every day at **06:00 UTC** (08:00 CEST / 07:00 CET) via GitHub Actions.

---

## Architecture

```
run.py (orchestrator)
├── config/config.py          — load & validate AppConfig
├── sheets/sheets_writer.py   — read Paramètres tab (config override)
│                             — load Profils_Cache + Dedup_Index
├── scraper/bereach_scraper.py — BeReach API (primary scraper)
│   scraper/linkedin_scraper.py — Apify scraper (disabled, kept for fallback)
├── matcher/profile_matcher.py — Claude Haiku scoring + profile fetch
└── sheets/sheets_writer.py   — write results + update Dedup_Index
```

---

## Setup

### 1. Clone & install dependencies

```bash
git clone <repo-url>
cd <repo>
pip install -r requirements.txt
```

### 2. Configure environment variables

Copy `.env.example` to `.env` and fill in all values:

```bash
cp .env.example .env
```

| Variable | Description |
|---|---|
| `BEREACH_API_TOKEN` | BeReach API token (primary LinkedIn scraper) |
| `APIFY_API_TOKEN` | Apify token (LinkedIn profile fetch + fallback scraper) |
| `ANTHROPIC_API_KEY` | Claude API key for post scoring |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | Full service account JSON (one line, escaped) |
| `SPREADSHEET_ID` | Google Sheets spreadsheet ID |

### 3. Configure settings

Edit `config/settings.json` or use the **Paramètres** tab in the Google Sheet (takes precedence at runtime):

```json
{
  "LINKEDIN_PROFILES": [{"name": "Your Name", "url": "https://linkedin.com/in/yourprofile"}],
  "TARGET_COUNTRIES": ["France", "Morocco"],
  "SEARCH_KEYWORDS": ["mission freelance", "besoin freelance", "offre mission freelance"],
  "MIN_MATCH_SCORE": 40,
  "MAX_POSTS_PER_COUNTRY": 50
}
```

### 4. Google Sheets permissions

Grant the service account **Editor** access to your spreadsheet. The pipeline creates the following tabs automatically:

| Tab | Purpose |
|---|---|
| `Missions_{YYYY-MM}` | Monthly mission results |
| `Dedup_Index` | Cross-run deduplication index |
| `Profils_Cache` | LinkedIn profile vector cache |
| `Paramètres` | Editable config (overrides settings.json) |

---

## GitHub Actions (CI/CD)

Secrets to set in **Settings → Secrets and variables → Actions**:

`BEREACH_API_TOKEN`, `APIFY_API_TOKEN`, `ANTHROPIC_API_KEY`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `SPREADSHEET_ID`

To trigger a manual run: **Actions → daily_extract → Run workflow**.

Logs are uploaded as artifacts (retained 30 days).

---

## Running locally

```bash
python run.py
```

Logs are written to `logs/run_YYYY-MM-DD.log`.
