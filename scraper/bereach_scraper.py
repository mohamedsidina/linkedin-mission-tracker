"""
scraper/bereach_scraper.py — BeReach API LinkedIn post scraper.

Calls POST /search/linkedin/posts on api.berea.ch with a fixed Boolean keyword
query, paginates while hasMore is True (up to max_posts_per_country), normalizes
results into RawPost dicts, applies a 24h safety filter, deduplicates by URL and
text hash, saves raw JSON to disk, and returns the final list.
"""

import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import requests

from config.config import AppConfig
from scraper.linkedin_scraper import (
    RawPost,
    _extract_contact_info,
    _is_within_24h,
    _save_raw_posts,
    _text_hash,
)

# BeReach API base URL and endpoint
_BASE_URL = "https://api.berea.ch"
_ENDPOINT = "/search/linkedin/posts"

# Fixed LinkedIn Boolean keyword query — covers freelance mission signals
_KEYWORDS = '("freelance" OR "mission" OR "tjm" OR "besoin" OR "#hiring")'

# Results per page (BeReach max is 50)
_PAGE_SIZE = 50

# HTTP timeout in seconds
_REQUEST_TIMEOUT = 30


def scrape_bereach(
    config: AppConfig,
    logger: logging.Logger,
    seen_urls: Optional[Set[str]] = None,
    seen_hashes: Optional[Set[str]] = None,
) -> List[RawPost]:
    """
    Fetch LinkedIn posts from the BeReach API and return deduplicated RawPost dicts.

    Sends a single fixed Boolean keyword query with datePosted=past-24h, paginates
    while hasMore is True or until max_posts_per_country is reached. Applies a 24h
    safety filter, deduplicates by URL and text hash (both within-run and cross-run),
    and saves raw results to data/raw_posts_{YYYY-MM-DD}.json.

    Args:
        config: Application configuration (provides bereach_api_token, max_posts_per_country).
        logger: Logger instance.
        seen_urls: Optional set of post URLs already written in previous runs.
        seen_hashes: Optional set of text hashes already written in previous runs.

    Returns:
        List of deduplicated RawPost dicts, all published within the last 24 hours.
    """
    seen_urls_global: Set[str] = seen_urls if seen_urls is not None else set()
    seen_hashes_global: Set[str] = seen_hashes if seen_hashes is not None else set()

    seen_urls_run: set = set()
    seen_text_hashes_run: set = set()
    all_posts: List[RawPost] = []
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    headers = {
        "Authorization": f"Bearer {config.bereach_api_token}",
        "Content-Type": "application/json",
    }

    start = 0
    page = 0

    while len(all_posts) < config.max_posts_per_country:
        if page > 0:
            time.sleep(random.uniform(0.5, 1.5))

        payload: Dict[str, Any] = {
            "keywords": _KEYWORDS,
            "sortBy": "relevance",
            "datePosted": "past-24h",
            "count": _PAGE_SIZE,
            "start": start,
        }

        try:
            logger.debug("[bereach] POST %s%s start=%d", _BASE_URL, _ENDPOINT, start)
            resp = requests.post(
                f"{_BASE_URL}{_ENDPOINT}",
                json=payload,
                headers=headers,
                timeout=_REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.HTTPError as exc:
            logger.error(
                "[bereach] HTTP %d error (start=%d): %s",
                exc.response.status_code if exc.response is not None else 0,
                start,
                exc,
            )
            break
        except Exception as exc:
            logger.error("[bereach] Request failed (start=%d): %s", start, exc)
            break

        items = data.get("items", [])
        has_more = data.get("hasMore", False)
        credits_used = data.get("creditsUsed", 0)

        logger.info(
            "[bereach] Fetched %d posts (start=%d, hasMore=%s, creditsUsed=%s)",
            len(items), start, has_more, credits_used,
        )

        batch_added = 0
        for item in items:
            post = _normalize_bereach_post(item)
            if post is None:
                continue
            if not _is_within_24h(post["post_date"], logger):
                continue
            if post["post_url"] in seen_urls_run:
                logger.debug("[bereach] duplicate URL skipped: %s", post["post_url"])
                continue
            text_hash = _text_hash(post["post_text"])
            if text_hash in seen_text_hashes_run:
                logger.debug("[bereach] near-duplicate text skipped: %s", post["post_url"])
                continue
            if post["post_url"] in seen_urls_global:
                logger.debug("[bereach] cross-run duplicate URL skipped: %s", post["post_url"])
                continue
            if text_hash in seen_hashes_global:
                logger.debug("[bereach] cross-run repost skipped: %s", post["post_url"])
                continue

            seen_urls_run.add(post["post_url"])
            seen_text_hashes_run.add(text_hash)
            all_posts.append(post)
            batch_added += 1

        logger.info("[bereach] %d new unique posts added this page.", batch_added)

        if not has_more or not items:
            break

        start += _PAGE_SIZE
        page += 1

    logger.info("[bereach] Total unique posts within 24h: %d", len(all_posts))
    _save_raw_posts(all_posts, date_str, logger)
    return all_posts


def _normalize_bereach_post(item: Dict[str, Any]) -> Optional[RawPost]:
    """
    Map a BeReach API response item to the canonical RawPost structure.

    Returns None if essential fields (postUrl, text) are missing.
    Converts the date field from milliseconds epoch to an ISO 8601 UTC string.
    Extracts contact_info via regex from post_text.

    Args:
        item: Single item from the BeReach /search/linkedin/posts response.

    Returns:
        Normalized RawPost or None if the item is malformed.
    """
    post_url = item.get("postUrl", "")
    post_text = item.get("text", "")

    if not post_url or not isinstance(post_text, str) or not post_text:
        return None

    # BeReach returns date as milliseconds since epoch (integer)
    raw_date = item.get("date")
    if raw_date and isinstance(raw_date, (int, float)):
        try:
            post_date = datetime.fromtimestamp(raw_date / 1000, tz=timezone.utc).isoformat()
        except (OSError, OverflowError, ValueError):
            post_date = datetime.now(timezone.utc).isoformat()
    else:
        post_date = datetime.now(timezone.utc).isoformat()

    author = item.get("author") or {}
    author_name = author.get("name", "")
    author_title = author.get("headline", "")
    author_profile_url = author.get("profileUrl", "")

    return RawPost(
        post_url=post_url,
        author_name=author_name,
        author_title=author_title,
        author_profile_url=author_profile_url,
        post_text=post_text,
        post_date=post_date,
        likes_count=int(item.get("likesCount") or 0),
        comments_count=int(item.get("commentsCount") or 0),
        contact_info=_extract_contact_info(post_text),
        country="",
        keyword=_KEYWORDS,
    )
