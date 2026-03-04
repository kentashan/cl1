# cl1 — Japan Google Trends Daily Fetcher

日本のGoogle トレンド（急上昇ワード）を毎日自動取得して JSON で保存するリポジトリです。

## 概要

GitHub Actions によって毎日 JST 09:00 (UTC 00:00) に自動実行され、その日の急上昇ワードを `trends.json` に追記します。直近 30 日分のデータを保持します。

## ファイル構成

```
.
├── fetch_trends.py              # メインスクリプト
├── requirements.txt             # Python 依存関係
├── trends.json                  # 取得結果（自動生成）
└── .github/workflows/
    └── daily_trends.yml         # GitHub Actions ワークフロー
```

## セットアップ（ローカル実行）

```bash
pip install -r requirements.txt
python fetch_trends.py
```

## 出力形式（trends.json）

```json
{
  "updated_at": "2024-03-01T00:00:00+00:00",
  "history": {
    "20240301": [
      {
        "date": "20240301",
        "rank": 1,
        "query": "トレンドワード",
        "traffic": "500K+",
        "articles": [
          {
            "title": "関連記事タイトル",
            "url": "https://...",
            "source": "メディア名"
          }
        ]
      }
    ]
  }
}
```

## ワークフロー

- **スケジュール**: 毎日 JST 09:00 (UTC 00:00) に自動実行
- **手動実行**: GitHub の Actions タブから `workflow_dispatch` で実行可能
- **コミット**: 変更があれば `chore: update Japan trends YYYY-MM-DD` というメッセージで自動コミット
