#!/usr/bin/env python3
"""
Japan music and karaoke trends fetcher.
Queries Gemini, OpenAI (ChatGPT), and Anthropic Claude APIs for current
Japanese music trends, then saves the results to a Notion database.
"""

import os
import sys
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

GEMINI_MODEL = "gemini-2.0-flash"
OPENAI_MODEL = "gpt-4o-mini"
CLAUDE_MODEL = "claude-haiku-4-5-20251001"


def build_prompt(date_str: str) -> str:
    """Return the Japanese music trend query prompt for a given JST date."""
    return f"""あなたは日本の音楽トレンドの専門家です。
今日（{date_str}、日本時間）の以下のトピックについて、最新情報をまとめてください：

1. 現在人気の日本の音楽ジャンルやアーティスト（上位5〜10件）
2. カラオケランキングの上位曲（最新のJOYSOUND・DAMなどのランキングを参考に）
3. 最近リリースされた注目の日本の楽曲やアルバム
4. 音楽・カラオケに関する話題のニュースやトレンド
5. SNS（X/Twitter、TikTok、YouTube）での音楽トレンド

各項目について、具体的な曲名・アーティスト名・理由を含めてください。日本語で回答してください。"""


def query_gemini(prompt: str) -> dict | None:
    """Query Google Gemini API. Returns result dict or None on failure."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("WARNING: GEMINI_API_KEY not set, skipping Gemini.", file=sys.stderr)
        return None
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(GEMINI_MODEL)
        response = model.generate_content(prompt)
        return {
            "source": "gemini",
            "model": GEMINI_MODEL,
            "content": response.text,
        }
    except Exception as exc:
        print(f"WARNING: Gemini query failed: {exc}", file=sys.stderr)
        return None


def query_openai(prompt: str) -> dict | None:
    """Query OpenAI ChatGPT API. Returns result dict or None on failure."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("WARNING: OPENAI_API_KEY not set, skipping OpenAI.", file=sys.stderr)
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": "あなたは日本の音楽・カラオケトレンドの専門家です。"},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2048,
        )
        return {
            "source": "openai",
            "model": OPENAI_MODEL,
            "content": response.choices[0].message.content,
        }
    except Exception as exc:
        print(f"WARNING: OpenAI query failed: {exc}", file=sys.stderr)
        return None


def query_claude(prompt: str) -> dict | None:
    """Query Anthropic Claude API. Returns result dict or None on failure."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("WARNING: ANTHROPIC_API_KEY not set, skipping Claude.", file=sys.stderr)
        return None
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        return {
            "source": "claude",
            "model": CLAUDE_MODEL,
            "content": message.content[0].text,
        }
    except Exception as exc:
        print(f"WARNING: Claude query failed: {exc}", file=sys.stderr)
        return None


def create_notion_page(date_str: str, results: list[dict]) -> None:
    """Create a Notion database page with the day's music trend results."""
    from notion_client import Client

    notion = Client(auth=os.environ["NOTION_TOKEN"])
    database_id = os.environ["NOTION_DATABASE_ID"]

    source_labels = {
        "gemini": "Google Gemini",
        "openai": "OpenAI ChatGPT",
        "claude": "Anthropic Claude",
    }

    # Build page body blocks
    children = []
    for result in results:
        label = source_labels.get(result["source"], result["source"])
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"text": {"content": f"{label}（{result['model']}）の分析"}}]
            },
        })
        # Notion limits each paragraph block to 2000 chars; split as needed
        content = result["content"]
        for chunk in [content[i:i + 1999] for i in range(0, len(content), 1999)]:
            children.append({
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": chunk}}]},
            })
        children.append({"object": "block", "type": "divider", "divider": {}})

    succeeded = [r["source"] for r in results]
    if len(succeeded) == 3:
        status = "完了"
    elif succeeded:
        status = "一部失敗"
    else:
        status = "失敗"

    notion.pages.create(
        parent={"database_id": database_id},
        properties={
            "タイトル": {"title": [{"text": {"content": f"日本音楽トレンド {date_str}"}}]},
            "日付": {"date": {"start": date_str}},
            "成功ソース": {"multi_select": [{"name": s} for s in succeeded]},
            "ステータス": {"select": {"name": status}},
        },
        children=children,
    )
    print(f"Notion page created for {date_str} (status: {status})")


def main() -> None:
    today_jst = datetime.now(tz=JST).strftime("%Y-%m-%d")
    prompt = build_prompt(today_jst)

    print(f"Fetching Japan music & karaoke trends for {today_jst}...")

    raw_results = [
        query_gemini(prompt),
        query_openai(prompt),
        query_claude(prompt),
    ]
    results = [r for r in raw_results if r is not None]

    if not results:
        print("ERROR: All API queries failed. Exiting.", file=sys.stderr)
        sys.exit(1)

    succeeded = [r["source"] for r in results]
    print(f"Received responses from: {succeeded}")

    create_notion_page(today_jst, results)


if __name__ == "__main__":
    main()
