#!/usr/bin/env python3
"""
Japan Google Trends daily fetcher.
Fetches trending searches in Japan and saves results as JSON.
"""

import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

OUTPUT_FILE = "trends.json"
TRENDING_RSS_URL = "https://trends.google.com/trending/rss?geo=JP"

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_RSS_NS = {"ht": "https://trends.google.com/trending/rss"}


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, requests.exceptions.ConnectionError):
        return True
    if isinstance(exc, requests.exceptions.Timeout):
        return True
    if isinstance(exc, requests.exceptions.HTTPError):
        return exc.response is not None and exc.response.status_code in _RETRYABLE_STATUS
    return False


@retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    stop=stop_after_attempt(4),
    reraise=True,
)
def _get_with_retry(url: str, headers: dict) -> requests.Response:
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response


def fetch_japan_trends() -> list[dict] | None:
    """
    Fetch trending searches for Japan via RSS feed (geo=JP).

    Returns a list of trend dicts on success, or None on failure.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = _get_with_retry(TRENDING_RSS_URL, headers)
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(
            f"WARNING: Google Trends RSS returned HTTP {status} after all retries.",
            file=sys.stderr,
        )
        return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        print(f"WARNING: Network error fetching Google Trends RSS: {exc}", file=sys.stderr)
        return None

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        print(f"WARNING: Failed to parse RSS: {exc}", file=sys.stderr)
        return None

    today = datetime.now(tz=timezone.utc).strftime("%Y%m%d")
    results = []
    for rank, item in enumerate(root.findall(".//item"), start=1):
        title = item.findtext("title", "")
        traffic = item.findtext("ht:approx_traffic", "", _RSS_NS)
        news_items = item.findall("ht:news_item", _RSS_NS)
        articles = [
            {
                "title": n.findtext("ht:news_item_title", "", _RSS_NS),
                "url": n.findtext("ht:news_item_url", "", _RSS_NS),
                "source": n.findtext("ht:news_item_source", "", _RSS_NS),
            }
            for n in news_items[:3]
        ]
        results.append(
            {
                "date": today,
                "rank": rank,
                "query": title,
                "traffic": traffic,
                "articles": articles,
            }
        )

    return results


def load_existing(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": None, "history": {}}


def save(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    print("Fetching Japan trending searches...")
    trends = fetch_japan_trends()

    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")
    data = load_existing(OUTPUT_FILE)
    data["updated_at"] = datetime.now(tz=timezone.utc).isoformat()

    history: dict = data.setdefault("history", {})

    if trends is None:
        print(
            f"WARNING: No trends fetched for {today}. "
            "Recording fetch_failed sentinel in trends.json.",
            file=sys.stderr,
        )
        history[today] = {"fetch_failed": True, "reason": "blocked_or_network_error"}
    else:
        history[today] = trends

        # Keep only the last 30 days to avoid unbounded growth
        if len(history) > 30:
            oldest_keys = sorted(history.keys())[: len(history) - 30]
            for k in oldest_keys:
                del history[k]

        print(f"Saved {len(trends)} trends for {today} -> {OUTPUT_FILE}")

        # Print top 10 to stdout for workflow logs
        print("\nTop 10 trends today:")
        for item in trends[:10]:
            print(f"  {item['rank']:2}. {item['query']}  ({item['traffic']})")

    save(OUTPUT_FILE, data)


if __name__ == "__main__":
    main()
