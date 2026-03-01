#!/usr/bin/env python3
"""GitHub Trending Repositories Checker"""

import urllib.request
import urllib.error
import json
import sys
from datetime import datetime


def fetch_github_trending(language="", since="daily"):
    """
    Fetch trending repositories from GitHub.

    Args:
        language: Programming language filter (e.g., "python", "javascript"). Empty for all.
        since: Time range - "daily", "weekly", or "monthly"

    Returns:
        List of trending repository info dicts
    """
    url = f"https://github.com/trending/{language}?since={since}"
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TrendChecker/1.0)",
        "Accept": "text/html",
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8")
    except urllib.error.URLError as e:
        print(f"Error fetching trends: {e}")
        return []

    return parse_trending(html)


def parse_trending(html):
    """Parse trending repositories from HTML."""
    repos = []

    # Split by article tags which contain each repo
    parts = html.split('<article class="Box-row">')
    for part in parts[1:]:
        repo = {}

        # Extract repo name (owner/name)
        if 'href="/' in part:
            start = part.find('href="/') + len('href="/')
            end = part.find('"', start)
            full_name = part[start:end]
            if "/" in full_name and len(full_name.split("/")) == 2:
                repo["full_name"] = full_name
                parts_name = full_name.split("/")
                repo["owner"] = parts_name[0]
                repo["name"] = parts_name[1]

        if not repo.get("full_name"):
            continue

        # Extract description
        if "<p " in part:
            desc_start = part.find("<p ")
            desc_end_tag = part.find("</p>", desc_start)
            desc_section = part[desc_start:desc_end_tag]
            # Remove HTML tags
            clean = ""
            in_tag = False
            for ch in desc_section:
                if ch == "<":
                    in_tag = True
                elif ch == ">":
                    in_tag = False
                elif not in_tag:
                    clean += ch
            repo["description"] = clean.strip()
        else:
            repo["description"] = ""

        # Extract star count from "stars today" or total stars
        if "star-icon" in part or "octicon-star" in part:
            # Try to find total stars
            star_idx = part.find("octicon-star")
            if star_idx != -1:
                after_star = part[star_idx:]
                # Find the number after the star icon
                num_start = after_star.find(">", after_star.find("</svg>")) + 1
                num_end = after_star.find("<", num_start)
                star_text = after_star[num_start:num_end].strip().replace(",", "")
                try:
                    repo["stars"] = int(star_text)
                except ValueError:
                    repo["stars"] = 0

        # Extract language
        if 'itemprop="programmingLanguage"' in part:
            lang_start = part.find('itemprop="programmingLanguage">')
            lang_start += len('itemprop="programmingLanguage">')
            lang_end = part.find("<", lang_start)
            repo["language"] = part[lang_start:lang_end].strip()
        else:
            repo["language"] = ""

        repos.append(repo)

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

    for i, repo in enumerate(repos[:20], 1):
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
