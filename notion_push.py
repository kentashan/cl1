#!/usr/bin/env python3
"""
Push Japan Google Trends data to a Notion database.

Required environment variables:
  NOTION_TOKEN       - Notion integration secret token
  NOTION_DATABASE_ID - Target Notion database ID
"""

import json
import os
import sys
from datetime import datetime, timezone

import requests

NOTION_API_URL = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def _notion_headers() -> dict:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        print("ERROR: NOTION_TOKEN environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": NOTION_VERSION,
    }


def _database_id() -> str:
    db_id = os.environ.get("NOTION_DATABASE_ID")
    if not db_id:
        print("ERROR: NOTION_DATABASE_ID environment variable not set.", file=sys.stderr)
        sys.exit(1)
    return db_id


def query_existing_entries(date_str: str) -> set[str]:
    """Return set of queries already in Notion for the given date."""
    db_id = _database_id()
    url = f"{NOTION_API_URL}/databases/{db_id}/query"
    payload = {
        "filter": {
            "property": "Date",
            "date": {"equals": f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"},
        }
    }
    resp = requests.post(url, headers=_notion_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    results = resp.json().get("results", [])
    existing = set()
    for page in results:
        props = page.get("properties", {})
        title_prop = props.get("Query", {}).get("title", [])
        if title_prop:
            existing.add(title_prop[0].get("plain_text", ""))
    return existing


def create_notion_page(trend: dict) -> None:
    """Create a single Notion page for a trend entry."""
    db_id = _database_id()
    date_str = trend["date"]
    iso_date = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"

    articles_text = "\n".join(
        f"- [{a['title']}]({a['url']}) ({a['source']})"
        for a in trend.get("articles", [])
        if a.get("title") and a.get("url")
    )

    payload = {
        "parent": {"database_id": db_id},
        "properties": {
            "Query": {
                "title": [{"text": {"content": trend["query"]}}]
            },
            "Date": {
                "date": {"start": iso_date}
            },
            "Rank": {
                "number": trend["rank"]
            },
            "Traffic": {
                "rich_text": [{"text": {"content": trend.get("traffic", "N/A")}}]
            },
            "Fetched At": {
                "date": {"start": datetime.now(tz=timezone.utc).isoformat()}
            },
        },
        "children": (
            [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": articles_text}}]
                    },
                }
            ]
            if articles_text
            else []
        ),
    }

    url = f"{NOTION_API_URL}/pages"
    resp = requests.post(url, headers=_notion_headers(), json=payload, timeout=30)
    resp.raise_for_status()


def push_trends_to_notion(trends: list[dict]) -> None:
    """Push a list of trend dicts to Notion, skipping already-existing entries."""
    if not trends:
        print("No trends to push.")
        return

    # Group by date to batch duplicate checks
    by_date: dict[str, list[dict]] = {}
    for t in trends:
        by_date.setdefault(t["date"], []).append(t)

    total_added = 0
    total_skipped = 0

    for date_str, day_trends in by_date.items():
        try:
            existing = query_existing_entries(date_str)
        except requests.exceptions.HTTPError as exc:
            print(f"WARNING: Could not query existing entries for {date_str}: {exc}", file=sys.stderr)
            existing = set()

        for trend in day_trends:
            if trend["query"] in existing:
                total_skipped += 1
                continue
            try:
                create_notion_page(trend)
                total_added += 1
                print(f"  Added: [{trend['rank']:2}] {trend['query']} ({trend.get('traffic', 'N/A')})")
            except requests.exceptions.HTTPError as exc:
                print(f"WARNING: Failed to add '{trend['query']}': {exc}", file=sys.stderr)

    print(f"\nNotion sync done. Added: {total_added}, Skipped (already exists): {total_skipped}")


def main() -> None:
    trends_file = os.environ.get("TRENDS_FILE", "trends.json")
    if not os.path.exists(trends_file):
        print(f"ERROR: {trends_file} not found. Run fetch_trends.py first.", file=sys.stderr)
        sys.exit(1)

    with open(trends_file, encoding="utf-8") as f:
        data = json.load(f)

    history = data.get("history", {})
    if not history:
        print("No trend history found in trends.json.")
        return

    # Use the most recent date's data
    latest_date = max(history.keys())
    trends = history[latest_date]

    if isinstance(trends, dict) and trends.get("fetch_failed"):
        print(f"Trends for {latest_date} failed to fetch. Nothing to push.")
        return

    print(f"Pushing {len(trends)} trends for {latest_date} to Notion...")
    push_trends_to_notion(trends)


if __name__ == "__main__":
    main()
