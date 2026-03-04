# cl1

GitHubのトレンドリポジトリを確認するツールです。

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
