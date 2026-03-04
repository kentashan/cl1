#!/usr/bin/env python3
"""
Japan Google Trends daily fetcher.
Fetches trending searches in Japan and saves results as JSON.
"""

import json
import os
from datetime import datetime, timezone

import requests

OUTPUT_FILE = "trends.json"
TRENDING_URL = "https://trends.google.com/trends/api/dailytrends"
NOTION_API_URL = "https://api.notion.com/v1/pages"
NOTION_VERSION = "2022-06-28"


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
        for rank, item in enumerate(day["trendingSearches"], start=1):
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
                    "rank": rank,
                    "query": title,
                    "traffic": traffic,
                    "articles": articles,
                }
            )

    return results


def push_to_notion(trends: list[dict], token: str, database_id: str) -> None:
    """Push today's trends to a Notion database."""
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    success = 0
    for item in trends:
        # Convert "20240301" -> "2024-03-01"
        date_iso = f"{item['date'][:4]}-{item['date'][4:6]}-{item['date'][6:]}"
        sources = [
            {"name": a["source"]}
            for a in item["articles"]
            if a.get("source")
        ]
        payload = {
            "parent": {"database_id": database_id},
            "properties": {
                "名前": {"title": [{"text": {"content": item["query"]}}]},
                "日付": {"date": {"start": date_iso}},
                "マルチセレクト": {"multi_select": sources},
                "ステータス": {"status": {"name": "未着手"}},
            },
        }
        resp = requests.post(NOTION_API_URL, json=payload, headers=headers, timeout=30)
        if resp.status_code == 200:
            success += 1
        else:
            print(f"  [WARN] Failed to push '{item['query']}': {resp.status_code} {resp.text[:100]}")
    print(f"Pushed {success}/{len(trends)} trends to Notion.")


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

    # Push to Notion if credentials are set
    notion_token = os.environ.get("NOTION_TOKEN")
    notion_db = os.environ.get("NOTION_DATABASE_ID")
    if notion_token and notion_db:
        today_trends = [t for t in trends if t["date"] == today.replace("-", "")]
        print(f"\nPushing {len(today_trends)} trends to Notion...")
        push_to_notion(today_trends, notion_token, notion_db)
    else:
        print("\nNOTION_TOKEN / NOTION_DATABASE_ID not set, skipping Notion push.")

    # Print top 10 to stdout for workflow logs
    print("\nTop 10 trends today:")
    for item in trends[:10]:
        print(f"  {item['rank']:2}. {item['query']}  ({item['traffic']})")


if __name__ == "__main__":
    main()
