#!/usr/bin/env python3
"""GitHub Trending Repositories Checker"""

import urllib.request
import urllib.error
import json
import sys
from datetime import datetime, timedelta


def fetch_github_trending(language="", since="daily"):
    """
    Fetch trending repositories using GitHub Search API.

    Args:
        language: Programming language filter (e.g., "python", "javascript"). Empty for all.
        since: Time range - "daily", "weekly", or "monthly"

    Returns:
        List of trending repository info dicts
    """
    days = {"daily": 1, "weekly": 7, "monthly": 30}.get(since, 1)
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    query = f"created:>{date_from}"
    if language:
        query += f"+language:{language}"

    url = (
        f"https://api.github.com/search/repositories"
        f"?q={query}&sort=stars&order=desc&per_page=20"
    )
    headers = {
        "User-Agent": "TrendChecker/1.0",
        "Accept": "application/vnd.github.v3+json",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
    except urllib.error.URLError as e:
        print(f"Error fetching trends: {e}")
        return []

    repos = []
    for item in data.get("items", []):
        repos.append({
            "full_name": item["full_name"],
            "description": item.get("description") or "",
            "language": item.get("language") or "",
            "stars": item.get("stargazers_count", 0),
        })
    return repos


def display_trends(repos, since="daily"):
    """Display trending repositories in a formatted way."""
    if not repos:
        print("No trending repositories found.")
        return

    since_label = {"daily": "Today", "weekly": "This Week", "monthly": "This Month"}.get(
        since, since
    )

    print(f"\n{'='*60}")
    print(f"  GitHub Trending Repositories - {since_label}")
    print(f"  Fetched at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

    for i, repo in enumerate(repos, 1):
        print(f"{i:2}. {repo.get('full_name', 'Unknown')}")
        if repo.get("description"):
            desc = repo["description"]
            if len(desc) > 80:
                desc = desc[:77] + "..."
            print(f"    {desc}")
        info_parts = []
        if repo.get("language"):
            info_parts.append(f"Language: {repo['language']}")
        if repo.get("stars"):
            info_parts.append(f"Stars: {repo['stars']:,}")
        if info_parts:
            print(f"    {' | '.join(info_parts)}")
        print(f"    https://github.com/{repo.get('full_name', '')}")
        print()


def main():
    """Main entry point."""
    language = ""
    since = "daily"

    args = sys.argv[1:]
    for arg in args:
        if arg in ("--daily", "--weekly", "--monthly"):
            since = arg.lstrip("-")
        elif arg.startswith("--lang="):
            language = arg.split("=", 1)[1]
        elif arg in ("-h", "--help"):
            print("Usage: python trend_checker.py [OPTIONS]")
            print("")
            print("Options:")
            print("  --daily      Show daily trends (default)")
            print("  --weekly     Show weekly trends")
            print("  --monthly    Show monthly trends")
            print("  --lang=LANG  Filter by programming language (e.g., --lang=python)")
            print("  -h, --help   Show this help message")
            print("")
            print("Examples:")
            print("  python trend_checker.py")
            print("  python trend_checker.py --weekly")
            print("  python trend_checker.py --lang=python --daily")
            return

    print(f"Fetching GitHub trending repositories...")
    repos = fetch_github_trending(language=language, since=since)
    display_trends(repos, since=since)


if __name__ == "__main__":
    main()
