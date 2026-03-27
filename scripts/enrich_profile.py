"""
enrich_profile.py — Monthly profile vector enrichment script.

Reads all user feedback from Google Sheets, aggregates it by domain,
and appends a [LEARNED PREFERENCES] section to the profile vector
stored in Profils_Cache. This section is loaded at scoring time as
part of the profile — zero additional tokens at runtime.

Usage:
    python scripts/enrich_profile.py

Run manually or via GitHub Actions workflow_dispatch once a month.
Requires the same environment variables as run.py.
"""

import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.config import load_config
from matcher.profile_matcher import _build_calibration_table, _DOMAIN_CLUSTERS, _classify_polarity
from sheets import load_feedback_examples, load_profile_vectors, save_profile_vectors

# Regex to strip a previously written [LEARNED PREFERENCES] block
_PREFS_BLOCK_RE = re.compile(
    r"\n*\[LEARNED PREFERENCES[^\]]*\][^\[]*",
    re.DOTALL,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("enrich_profile")


def _build_preferences_text(feedback_examples: list) -> str:
    """
    Derive a human-readable [LEARNED PREFERENCES] block from feedback stats.

    Identifies domains with strong positive signal (score 70+),
    strong negative signal (score <25), and borderline (40-60).

    Args:
        feedback_examples: Sorted list of feedback dicts.

    Returns:
        Formatted preference block string.
    """
    from collections import defaultdict
    stats: dict = {d: {"pos": 0, "neg": 0, "cau": 0} for d in _DOMAIN_CLUSTERS}

    for ex in feedback_examples:
        text = (ex.get("mission_title", "") + " " + ex.get("required_skills", "")).lower()
        key = _classify_polarity(ex.get("feedback", ""))[:3]
        for domain, keywords in _DOMAIN_CLUSTERS.items():
            if any(kw in text for kw in keywords):
                stats[domain][key] += 1
                break

    high, low, borderline = [], [], []
    for domain, s in stats.items():
        total = s["pos"] + s["neg"] + s["cau"]
        if total == 0:
            continue
        if s["pos"] > s["neg"] * 2:
            high.append(domain)
        elif s["neg"] > s["pos"] * 2:
            low.append(domain)
        else:
            borderline.append(domain)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total_fb = len(feedback_examples)
    lines = [
        f"\n[LEARNED PREFERENCES — updated {today} from {total_fb} feedbacks:]",
    ]
    if high:
        lines.append(f"Missions à cibler (score 70+)    : {', '.join(high)}")
    if low:
        lines.append(f"Missions hors scope (score <25)  : {', '.join(low)}")
    if borderline:
        lines.append(f"Missions borderline (score 40-60): {', '.join(borderline)}")
    return "\n".join(lines)


def main() -> None:
    """Load feedback, enrich profile vector, save back to Profils_Cache."""
    logger.info("=== enrich_profile — start ===")

    config = load_config()

    # 1 — Load all feedback examples
    feedback_examples = load_feedback_examples(config, logger)
    if not feedback_examples:
        logger.warning("No feedback found — nothing to enrich. Exiting.")
        return
    logger.info("%d feedback example(s) loaded.", len(feedback_examples))

    # 2 — Load current profile vectors from cache
    # load_profile_vectors returns Dict[url -> vector_text]
    # Profile names come from config.linkedin_profiles
    cached = load_profile_vectors(config, logger)
    if not cached:
        logger.warning("No cached profile vectors found. Run run.py first to populate the cache.")
        return

    # Build url -> name map from config
    name_by_url = {p["url"]: p["name"] for p in config.linkedin_profiles}

    # 3 — Build preferences text block
    prefs_text = _build_preferences_text(feedback_examples)
    logger.info("Preferences block:\n%s", prefs_text)

    # 4 — Enrich each profile vector
    enriched_vectors: dict = {}
    for url, vector in cached.items():
        name = name_by_url.get(url, "unknown")

        # Strip any previous [LEARNED PREFERENCES] block
        vector_clean = _PREFS_BLOCK_RE.sub("", vector).rstrip()

        # Append updated block
        enriched_vectors[url] = {
            "name": name,
            "vector": vector_clean + prefs_text,
        }
        logger.info("Profile '%s' enriched (%d chars → %d chars).",
                    name, len(vector), len(enriched_vectors[url]["vector"]))

    # 5 — Save enriched vectors back to Profils_Cache
    save_profile_vectors(enriched_vectors, config, logger)
    logger.info("=== enrich_profile — done. Run run.py to use the enriched profile. ===")


if __name__ == "__main__":
    main()
