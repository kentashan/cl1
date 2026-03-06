# cl1

GitHubのトレンドリポジトリを確認するツールと、音楽・カラオケトレンドをClaudeで分析してWEB広告提案を生成するツールです。

## 音楽・カラオケトレンド分析（メイン機能）

`music_karaoke_analyzer.py` を使って、Google Trendsから日本の音楽・カラオケ関連トレンドを収集し、Claude AIで分析・WEB広告活用提案を自動生成します。

**GitHub Actionsで15分ごとに自動実行されます。**

### 必要な環境変数（GitHub Secrets）

| シークレット名 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API キー |

### 手動実行

```bash
export ANTHROPIC_API_KEY=your_api_key_here
python music_karaoke_analyzer.py
```

### 出力ファイル

`music_trends_analysis.json` に以下の情報が保存されます：

- 収集した音楽・カラオケ関連トレンド一覧
- Claudeによる流行分析（背景・ユーザー層）
- WEB広告キーワード・ターゲティング・コピー案
- カラオケビジネスへの具体的アクション提案

---

## トレンドの確認方法

`trend_checker.py` を使ってGitHubのトレンドを確認できます。

### 基本的な使い方

```bash
python trend_checker.py
```

### オプション

| オプション | 説明 |
|---|---|
| `--daily` | 今日のトレンド（デフォルト） |
| `--weekly` | 今週のトレンド |
| `--monthly` | 今月のトレンド |
| `--lang=LANG` | プログラミング言語でフィルタ |
| `-h`, `--help` | ヘルプを表示 |

### 使用例

```bash
# 今日のトレンド（全言語）
python trend_checker.py

# 今週のトレンド
python trend_checker.py --weekly

# 今月のPythonトレンド
python trend_checker.py --monthly --lang=python

# JavaScriptの日次トレンド
python trend_checker.py --daily --lang=javascript
```

### 出力例

```
Fetching GitHub trending repositories...

============================================================
  GitHub Trending Repositories - Today
  Fetched at: 2026-03-01 12:00:00
============================================================

 1. owner/repo-name
    This is a description of the trending repository.
    Language: Python | Stars: 1,234
    https://github.com/owner/repo-name
```

## 必要な環境

- Python 3.6以上
- 外部ライブラリ不要（標準ライブラリのみ使用）
