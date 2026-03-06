#!/usr/bin/env python3
"""
音楽・カラオケ関連トレンド収集・分析スクリプト

Google Trendsから日本の音楽・カラオケ関連トレンドを収集し、
Claude APIで流行分析とWEB広告活用提案を生成します。
15分ごとにGitHub Actionsで自動実行されます。

Required environment variable:
  ANTHROPIC_API_KEY - Anthropic API key
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

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

TRENDING_URL = "https://trends.google.com/trends/api/dailytrends"
OUTPUT_FILE = "music_trends_analysis.json"

_XSSI_PREFIX_RE = re.compile(r"^\)\]\}'[^\n]*\n")
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


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
def _get_with_retry(url: str, params: dict, headers: dict) -> requests.Response:
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response


def _strip_xssi(raw: str) -> str:
    stripped = _XSSI_PREFIX_RE.sub("", raw, count=1)
    if stripped != raw:
        return stripped
    newline_pos = raw.find("\n")
    if newline_pos != -1:
        return raw[newline_pos + 1:]
    return raw


def fetch_all_japan_trends() -> list[dict] | None:
    """日本のGoogle Trendsを全件取得する。"""
    params = {
        "hl": "ja",
        "tz": "-540",
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
            f"WARNING: Google Trends returned HTTP {status} after all retries.",
            file=sys.stderr,
        )
        return None
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
        print(f"WARNING: Network error: {exc}", file=sys.stderr)
        return None

    try:
        json_body = _strip_xssi(response.text)
        data = json.loads(json_body)
    except (ValueError, json.JSONDecodeError) as exc:
        print(f"WARNING: Failed to parse response: {exc}", file=sys.stderr)
        return None

    try:
        trending_searches = data["default"]["trendingSearchesDays"]
    except (KeyError, TypeError) as exc:
        print(f"WARNING: Unexpected JSON structure: {exc}", file=sys.stderr)
        return None

    results = []
    for day in trending_searches:
        date_str = day["date"]
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

    # 分析内容をコンソールに出力
    print("\n" + "=" * 60)
    print("  音楽・カラオケトレンド分析レポート")
    print(f"  {fetched_at_jst}")
    print("=" * 60)
    print(result["analysis"])
    print("=" * 60)


if __name__ == "__main__":
    main()
