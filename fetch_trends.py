#!/usr/bin/env python3
"""
Japan Google Trends daily fetcher.
Fetches trending searches in Japan and saves results as JSON.
"""

import json
import os
from datetime import datetime, timezone

import requests

JST = timezone.utc  # stored as UTC, displayed note says JST+9

OUTPUT_FILE = "trends.json"
TRENDING_URL = "https://trends.google.com/trends/api/dailytrends"


def fetch_japan_trends() -> list[dict]:
    """Fetch daily trending searches for Japan (geo=JP)."""
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
    response = requests.get(TRENDING_URL, params=params, headers=headers, timeout=30)
    response.raise_for_status()

    # Google Trends prepends ")]}',\n" to the JSON body
    raw = response.text
    json_start = raw.index("\n") + 1
    data = json.loads(raw[json_start:])

    trending_searches = data["default"]["trendingSearchesDays"]
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
    history[today] = trends

    # Keep only the last 30 days to avoid unbounded growth
    if len(history) > 30:
        oldest_keys = sorted(history.keys())[: len(history) - 30]
        for k in oldest_keys:
            del history[k]

    save(OUTPUT_FILE, data)
    print(f"Saved {len(trends)} trends for {today} -> {OUTPUT_FILE}")

    # Print top 10 to stdout for workflow logs
    print("\nTop 10 trends today:")
    for item in trends[:10]:
        print(f"  {item['rank']:2}. {item['query']}  ({item['traffic']})")


if __name__ == "__main__":
    main()
