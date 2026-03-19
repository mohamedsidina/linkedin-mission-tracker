"""
scripts/fix_profile_cache.py — One-off script to overwrite the Profils_Cache
tab with Mohamed's correct profile vector, built from his CV.

Usage:
    python scripts/fix_profile_cache.py

Requires GOOGLE_SERVICE_ACCOUNT_JSON and SPREADSHEET_ID to be set in the
environment (or in a local .env file loaded via python-dotenv).
"""

import json
import os
import sys
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from google.oauth2 import service_account
from googleapiclient.discovery import build

# ── Correct profile vector built from CV ─────────────────────────────────────
PROFILE_NAME = "Mohamed"
PROFILE_URL  = "https://www.linkedin.com/in/mohamed-sid-ahmed/"
PROFILE_VECTOR = (
    "Mohamed SID AHMED | Service Delivery Manager - PMO | Bois d'Arcy, France | "
    "14 ans d'expertise en service delivery, gestion de projet et business intelligence. "
    "Excellence opérationnelle et transformation de la donnée en insight décisionnel. "
    "Disponible immédiatement. International. | "
    "Service Delivery Manager at L'OREAL | "
    "PMO Data at L'OREAL | "
    "PMO Data at Umanis | "
    "Chef de Projet Lean at Sealed Air | "
    "Chef de Projet at PSA Groupe | "
    "Skills: ServiceNow, Anaplan, Power BI, Python, SQL, DAX, VBA, Power Automate, "
    "Tableau, Dataiku, Machine Learning, Confluence, GitHub, Elasticsearch, Minitab, "
    "Lean Six Sigma, Gestion de projet, Agile, ITSM, Run Management, "
    "Amélioration continue, Gestion des stakeholders, Data-driven | "
    "Certifications: ITIL 4 Foundation, PSPO I (Scrum.org), Lean Six Sigma Green Belt, "
    "Power BI Data Analyst Associate, ML Practitioner Dataiku, Tableau Desktop Specialist | "
    "Formation: Data Scientist CentraleSupélec (2022), Mastère Excellence Opérationnelle INSA Rennes (2015), "
    "Ingénieur Génie Industriel EIGSI La Rochelle (2013)"
)
# ─────────────────────────────────────────────────────────────────────────────

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_PROFILES_CACHE_TAB = "Profils_Cache"
_HEADERS = ["profile_name", "url", "vector", "fetched_at"]


def main() -> None:
    service_account_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    spreadsheet_id = os.getenv("SPREADSHEET_ID")

    if not service_account_json or not spreadsheet_id:
        print("ERROR: GOOGLE_SERVICE_ACCOUNT_JSON and SPREADSHEET_ID must be set.")
        sys.exit(1)

    info = json.loads(service_account_json)
    credentials = service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)

    # Ensure tab exists
    spreadsheet = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    existing = {s["properties"]["title"] for s in spreadsheet.get("sheets", [])}

    if _PROFILES_CACHE_TAB not in existing:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": _PROFILES_CACHE_TAB}}}]},
        ).execute()
        print(f"Created '{_PROFILES_CACHE_TAB}' tab.")

    fetched_at = datetime.now(timezone.utc).isoformat()
    rows = [
        _HEADERS,
        [PROFILE_NAME, PROFILE_URL, PROFILE_VECTOR, fetched_at],
    ]

    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"'{_PROFILES_CACHE_TAB}'!A1",
        valueInputOption="RAW",
        body={"values": rows},
    ).execute()

    # Clear any leftover rows below row 2
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id,
        range=f"'{_PROFILES_CACHE_TAB}'!A3:D1000",
    ).execute()

    print(f"Done. Profile vector written ({len(PROFILE_VECTOR)} chars).")
    print(f"Vector preview: {PROFILE_VECTOR[:120]}...")


if __name__ == "__main__":
    main()
