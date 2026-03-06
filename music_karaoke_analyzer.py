#!/usr/bin/env python3
"""
音楽・カラオケ関連トレンド収集・分析スクリプト

Google Trendsから日本の音楽・カラオケ関連トレンドを収集し、
Claude APIで流行分析とWEB広告活用提案を生成します。
15分ごとにGitHub Actionsで自動実行されます。

Required environment variables:
  ANTHROPIC_API_KEY  - Anthropic API key
  NOTION_TOKEN       - Notion integration secret (optional: skip if not set)
  NOTION_DATABASE_ID - Target Notion database ID (optional: skip if not set)
"""

import json
import os
import sys
from datetime import datetime, timezone

import xml.etree.ElementTree as ET

import anthropic
import requests
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

# 音楽・カラオケ関連キーワード（日本語・英語）
MUSIC_KARAOKE_KEYWORDS = [
    # 音楽全般
    "音楽", "歌", "歌手", "アーティスト", "バンド", "シンガー",
    # カラオケ
    "カラオケ", "カラオケ曲", "カラオケランキング", "DAM", "JOYSOUND",
    # 楽曲・リリース
    "新曲", "シングル", "アルバム", "MV", "ミュージックビデオ", "リリース",
    # ライブ・イベント
    "ライブ", "コンサート", "フェス", "武道館", "紅白",
    # ジャンル
    "J-POP", "JPOP", "K-POP", "KPOP", "ボカロ", "ボーカロイド",
    "アニソン", "演歌", "歌謡曲", "ラップ", "ヒップホップ",
    # チャート・ランキング
    "ランキング", "チャート", "ヒット", "ヒット曲", "流行",
    # ストリーミング
    "Spotify", "Apple Music", "Amazon Music", "YouTube Music",
    "ストリーミング", "サブスク", "再生数",
    # SNS・バイラル
    "TikTok", "バイラル", "流行歌", "話題曲",
    # 特定アーティスト関連ワード（ジャンル名として）
    "アイドル", "ガールズグループ", "ボーイズグループ",
]

TRENDING_RSS_URL = "https://trends.google.com/trending/rss?geo=JP"
OUTPUT_FILE = "music_trends_analysis.json"

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


def fetch_all_japan_trends() -> list[dict] | None:
    """日本のGoogle Trends RSSから全件取得する。"""
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
            f"WARNING: Google Trends returned HTTP {status} after all retries.",
            file=sys.stderr,
        )
        return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        print(f"WARNING: Network error: {exc}", file=sys.stderr)
        return None

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        print(f"WARNING: Failed to parse RSS: {exc}", file=sys.stderr)
        return None

    results = []
    for rank, item in enumerate(root.findall(".//item"), start=1):
        title = item.findtext("title", "")
        pub_date = item.findtext("pubDate", "")
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
                "date": pub_date,
                "rank": rank,
                "query": title,
                "traffic": traffic,
                "articles": articles,
            }
        )

    return results


def filter_music_karaoke_trends(all_trends: list[dict]) -> list[dict]:
    """全トレンドから音楽・カラオケ関連のものを抽出する。"""
    music_trends = []
    keywords_lower = [k.lower() for k in MUSIC_KARAOKE_KEYWORDS]

    for trend in all_trends:
        query_lower = trend["query"].lower()
        # クエリ自体がキーワードを含む場合
        if any(kw in query_lower for kw in keywords_lower):
            music_trends.append(trend)
            continue
        # 関連記事のタイトルが音楽関連の場合
        article_text = " ".join(
            a.get("title", "").lower() for a in trend.get("articles", [])
        )
        if any(kw in article_text for kw in keywords_lower):
            music_trends.append(trend)

    return music_trends


def analyze_with_claude(
    music_trends: list[dict],
    all_trends: list[dict],
    fetched_at: str,
) -> dict:
    """Claude APIで音楽・カラオケトレンドを分析し、WEB広告提案を生成する。"""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set.", file=sys.stderr)
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    # 分析用プロンプトデータを整形
    if music_trends:
        trends_text = "\n".join(
            f"- {t['query']} (検索数: {t['traffic']}, ランク: {t['rank']})"
            for t in music_trends[:20]
        )
    else:
        # 音楽関連が見つからない場合は全トレンド上位を参考に提供
        trends_text = "※音楽・カラオケ関連の直接的なトレンドは検出されませんでしたが、以下の全体トレンドを参考にします:\n"
        trends_text += "\n".join(
            f"- {t['query']} (検索数: {t['traffic']})"
            for t in all_trends[:15]
        )

    prompt = f"""あなたは日本の音楽・カラオケ業界のマーケティング専門家です。
以下は {fetched_at} 時点の日本のGoogle Trendsデータです。

【音楽・カラオケ関連トレンド】
{trends_text}

以下の3つの観点で詳細に分析・提案してください：

## 1. 現在の流行分析
- 今どんな音楽・アーティスト・カラオケ曲が注目されているか
- トレンドの背景（ドラマ・アニメ・SNS起因など）
- 年代層・ユーザー層の推定

## 2. WEB広告活用提案
- Google広告・SNS広告で使うべきキーワード（具体的に5〜10個）
- ターゲティング設定の推奨（年齢・性別・興味関心）
- 広告コピー案（見出し3パターン）
- 最適な広告配信タイミング

## 3. カラオケビジネスへの具体的アクション
- 今すぐ投入すべき施策（優先度順）
- コンテンツマーケティングのアイデア
- 予算配分の考え方

回答は日本語で、実践的かつ具体的に記述してください。"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )

    analysis_text = message.content[0].text

    return {
        "analysis": analysis_text,
        "model": message.model,
        "input_tokens": message.usage.input_tokens,
        "output_tokens": message.usage.output_tokens,
    }


_NOTION_API_URL = "https://api.notion.com/v1"
_NOTION_VERSION = "2022-06-28"
_NOTION_BLOCK_LIMIT = 1900  # Notion per-block text limit (2000 with margin)


def _notion_headers() -> dict:
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise RuntimeError("NOTION_TOKEN not set")
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": _NOTION_VERSION,
    }


def _text_to_blocks(text: str) -> list[dict]:
    """Claude分析テキスト（Markdown見出し付き）をNotionブロックに変換する。"""
    blocks = []
    for line in text.splitlines():
        # ## 見出し → heading_2
        if line.startswith("## "):
            content = line[3:].strip()
            blocks.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": content[:_NOTION_BLOCK_LIMIT]}}]
                },
            })
        # - 箇条書き → bulleted_list_item
        elif line.startswith("- "):
            content = line[2:].strip()
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {"content": content[:_NOTION_BLOCK_LIMIT]}}]
                },
            })
        # 空行はスキップ
        elif not line.strip():
            continue
        # 通常テキスト → paragraph（2000文字超えは分割）
        else:
            for i in range(0, len(line), _NOTION_BLOCK_LIMIT):
                blocks.append({
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": line[i:i + _NOTION_BLOCK_LIMIT]}}]
                    },
                })
    return blocks


def push_music_analysis_to_notion(record: dict) -> None:
    """音楽・カラオケ分析結果をNotionの「日本トレンド抽出」データベースに1ページ追加する。"""
    notion_token = os.environ.get("NOTION_TOKEN")
    db_id = os.environ.get("NOTION_DATABASE_ID")
    if not notion_token or not db_id:
        print("NOTION_TOKEN / NOTION_DATABASE_ID が未設定のためNotion連携をスキップします。")
        return

    fetched_dt = datetime.fromisoformat(record["fetched_at"])
    from datetime import timedelta
    jst_dt = fetched_dt + timedelta(hours=9)
    jst_label = jst_dt.strftime("%Y-%m-%d %H:%M JST")
    page_title = f"音楽・カラオケトレンド分析 {jst_label}"
    iso_date = jst_dt.strftime("%Y-%m-%d")
    traffic_label = (
        f"音楽{record['music_trends_count']}件検出"
        if record["music_trends_count"] > 0
        else f"全体{record['total_trends_count']}件参照"
    )

    # ページプロパティ（既存DBスキーマに合わせる）
    properties = {
        "Query": {
            "title": [{"text": {"content": page_title}}]
        },
        "Date": {
            "date": {"start": iso_date}
        },
        "Rank": {
            "number": 0  # 分析サマリーページは 0 で識別
        },
        "Traffic": {
            "rich_text": [{"text": {"content": traffic_label}}]
        },
        "Fetched At": {
            "date": {"start": record["fetched_at"]}
        },
    }

    # ページ本文ブロック
    blocks: list[dict] = []

    # --- 更新日時 ---
    blocks.append({
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": [{"type": "text", "text": {
                "content": f"収集日時: {jst_label}  |  モデル: {record.get('model', 'claude-sonnet-4-6')}  |  トークン: {record.get('tokens', {}).get('input', 0)} in / {record.get('tokens', {}).get('output', 0)} out"
            }}],
            "icon": {"emoji": "📅"},
            "color": "gray_background",
        },
    })

    # --- 検出トレンド一覧 ---
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "検出された音楽・カラオケトレンド"}}]
        },
    })
    if record["music_trends"]:
        for t in record["music_trends"]:
            blocks.append({
                "object": "block",
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [{"type": "text", "text": {
                        "content": f"{t['query']}  （検索数: {t['traffic']}）"
                    }}]
                },
            })
    else:
        blocks.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {
                    "content": "※ 今回の収集では音楽・カラオケ関連トレンドは検出されませんでした。全体トレンドをもとに分析しています。"
                }}]
            },
        })

    # --- Claude分析レポート ---
    blocks.append({
        "object": "block",
        "type": "heading_2",
        "heading_2": {
            "rich_text": [{"type": "text", "text": {"content": "AI分析レポート（Claude）"}}]
        },
    })
    blocks.extend(_text_to_blocks(record["analysis"]))

    # Notionは1リクエスト100ブロックまでなのでページ作成時は最初の100ブロックのみ
    first_batch = blocks[:100]

    payload = {
        "parent": {"database_id": db_id},
        "properties": properties,
        "children": first_batch,
    }

    try:
        headers = _notion_headers()
        resp = requests.post(
            f"{_NOTION_API_URL}/pages",
            headers=headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        page_id = resp.json().get("id", "")
        print(f"Notionページ作成完了: {page_title} (id={page_id})")

        # 残りのブロックを追記
        remaining = blocks[100:]
        for i in range(0, len(remaining), 100):
            chunk = remaining[i:i + 100]
            append_resp = requests.patch(
                f"{_NOTION_API_URL}/blocks/{page_id}/children",
                headers=headers,
                json={"children": chunk},
                timeout=30,
            )
            append_resp.raise_for_status()

    except requests.exceptions.HTTPError as exc:
        body = exc.response.text if exc.response is not None else ""
        print(f"WARNING: Notionへの書き込みに失敗しました: {exc}\n{body}", file=sys.stderr)
    except RuntimeError as exc:
        print(f"WARNING: {exc}", file=sys.stderr)


def load_existing(path: str) -> dict:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": None, "history": []}


def save(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def main() -> None:
    fetched_at = datetime.now(tz=timezone.utc)
    fetched_at_str = fetched_at.strftime("%Y-%m-%d %H:%M UTC")
    fetched_at_jst = fetched_at.strftime("%Y-%m-%d %H:%M") + " JST(+9h)"

    print(f"[{fetched_at_str}] 音楽・カラオケトレンド収集を開始します...")

    # 全トレンド取得
    print("Google Trendsからデータを取得中...")
    all_trends = fetch_all_japan_trends()

    if all_trends is None:
        print(
            "WARNING: トレンドデータの取得に失敗しました。分析をスキップします。",
            file=sys.stderr,
        )
        # 失敗レコードを保存
        data = load_existing(OUTPUT_FILE)
        data["updated_at"] = fetched_at.isoformat()
        data.setdefault("history", []).append(
            {
                "fetched_at": fetched_at.isoformat(),
                "fetch_failed": True,
                "reason": "blocked_or_network_error",
            }
        )
        # 直近50件のみ保持
        data["history"] = data["history"][-50:]
        save(OUTPUT_FILE, data)
        sys.exit(0)

    print(f"全トレンド数: {len(all_trends)}件")

    # 音楽・カラオケ関連フィルタリング
    music_trends = filter_music_karaoke_trends(all_trends)
    print(f"音楽・カラオケ関連トレンド: {len(music_trends)}件")

    if music_trends:
        print("\n検出された音楽・カラオケトレンド TOP10:")
        for t in music_trends[:10]:
            print(f"  {t['rank']:2}. {t['query']}  ({t['traffic']})")
    else:
        print("音楽・カラオケ関連トレンドは直接検出されませんでした。全体トレンドで分析します。")

    # Claude APIで分析
    print("\nClaude APIで分析・広告提案を生成中...")
    result = analyze_with_claude(music_trends, all_trends, fetched_at_jst)
    print(f"分析完了 (使用トークン: {result['input_tokens']} in / {result['output_tokens']} out)")

    # 結果を保存
    record = {
        "fetched_at": fetched_at.isoformat(),
        "music_trends_count": len(music_trends),
        "music_trends": music_trends[:20],
        "total_trends_count": len(all_trends),
        "analysis": result["analysis"],
        "model": result["model"],
        "tokens": {
            "input": result["input_tokens"],
            "output": result["output_tokens"],
        },
    }

    data = load_existing(OUTPUT_FILE)
    data["updated_at"] = fetched_at.isoformat()
    data.setdefault("history", []).append(record)
    # 直近50件のみ保持（15分×50 = 約12.5時間分）
    data["history"] = data["history"][-50:]
    # 最新の分析をトップレベルにも保持（参照しやすくするため）
    data["latest"] = record

    save(OUTPUT_FILE, data)
    print(f"\n結果を {OUTPUT_FILE} に保存しました。")

    # Notionに分析ページを追加
    print("\nNotionに分析ページを追加中...")
    push_music_analysis_to_notion(record)

    # 分析内容をコンソールに出力
    print("\n" + "=" * 60)
    print("  音楽・カラオケトレンド分析レポート")
    print(f"  {fetched_at_jst}")
    print("=" * 60)
    print(result["analysis"])
    print("=" * 60)


if __name__ == "__main__":
    main()
