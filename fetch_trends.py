#!/usr/bin/env python3
"""
Japan Google Trends daily fetcher.
Fetches trending searches in Japan and saves results as JSON.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

JST = timezone.utc  # stored as UTC, displayed note says JST+9

OUTPUT_FILE = "trends.json"
TRENDING_URL = "https://trends.google.com/trends/api/dailytrends"

# HTTP status codes that are worth retrying (rate-limited or server-side flap)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# Matches any variant of Google's XSSI protection prefix up to the first newline
_XSSI_PREFIX_RE = re.compile(r"^\)\]\}'[^\n]*\n")


def _is_retryable(exc: BaseException) -> bool:
    """Return True for network errors or retryable HTTP status codes."""
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
def _get_with_retry(url: str, params: dict, headers: dict) -> requests.Response:
    """Perform a GET request; retries on network errors and 429/5xx responses."""
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response


def _strip_xssi(raw: str) -> str:
    """
    Strip Google's XSSI prefix from the response body.

    Google Trends prepends )]}',\n to prevent JSON hijacking.
    This strips that prefix robustly regardless of exact whitespace variant.
    Falls back to a newline-based split for backwards compatibility.
    """
    stripped = _XSSI_PREFIX_RE.sub("", raw, count=1)
    if stripped != raw:
        return stripped
    # Fallback: find first newline (original approach, but safe with find())
    newline_pos = raw.find("\n")
    if newline_pos != -1:
        return raw[newline_pos + 1:]
    # No prefix found at all - return as-is and let json.loads surface the error
    return raw


def fetch_japan_trends() -> list[dict] | None:
    """
    Fetch daily trending searches for Japan (geo=JP).

    Returns a list of trend dicts on success, or None if Google is
    blocking requests (403/429 after all retries exhausted).
    """
    params = {
        "hl": "ja",
        "tz": "-540",  # JST = UTC+9
        "geo": "JP",
        "ns": "15",
    }
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = _get_with_retry(TRENDING_URL, params, headers)
    except requests.exceptions.HTTPError as exc:
        status = exc.response.status_code if exc.response is not None else "unknown"
        print(
            f"WARNING: Google Trends returned HTTP {status} after all retries. "
            "This is expected when running from GitHub Actions IPs. Skipping fetch.",
            file=sys.stderr,
        )
        return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        print(
            f"WARNING: Network error fetching Google Trends after all retries: {exc}",
            file=sys.stderr,
        )
        return None

    try:
        json_body = _strip_xssi(response.text)
        data = json.loads(json_body)
    except (ValueError, json.JSONDecodeError) as exc:
        print(
            f"WARNING: Failed to parse Google Trends response: {exc}\n"
            f"Response preview: {response.text[:200]!r}",
            file=sys.stderr,
        )
        return None

    try:
        trending_searches = data["default"]["trendingSearchesDays"]
    except (KeyError, TypeError) as exc:
        print(
            f"WARNING: Unexpected JSON structure from Google Trends: {exc}\n"
            f"Top-level keys: {list(data.keys()) if isinstance(data, dict) else type(data)}",
            file=sys.stderr,
        )
        return None

    results = []
    for day in trending_searches:
        date_str = day["date"]  # e.g. "20240301"
        for item in day["trendingSearches"]:
            title = item["title"]["query"]
            traffic = item.get("formattedTraffic", "N/A")
            articles = [
                {
                    "title": a.get("title", ""),
                    "url": a.get("url", ""),
                    "source": a.get("source", ""),
                }
                for a in item.get("articles", [])[:3]
            ]
            results.append(
                {
                    "date": date_str,
                    "rank": len(results) + 1,
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
