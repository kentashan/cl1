# 記事自動投稿システム

Claude AIで記事を自動生成し、note.comに投稿するシステムです。

## 仕組み

1. `articles/topics.txt` にトピックを追加して `main` ブランチにpush
2. GitHub Actionsが自動起動
3. Claude AIがトピックからランダムに1つ選んで記事を生成
4. 生成した記事をnote.comに投稿

## セットアップ

### 1. GitHubシークレットの設定

GitHubリポジトリの **Settings > Secrets and variables > Actions** に以下を登録：

| シークレット名 | 説明 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic APIキー（[取得はこちら](https://console.anthropic.com/)） |
| `NOTE_EMAIL` | note.comのログインメールアドレス |
| `NOTE_PASSWORD` | note.comのパスワード |

### 2. トピックの追加

`articles/topics.txt` を編集してトピックを追加します（1行に1つ、`#` で始まる行はコメント）：

```
プログラミング初心者向けのPython入門
AIを使った業務効率化のコツ
エンジニアの勉強法について
```

### 3. 投稿のトリガー

- **自動**: `articles/topics.txt` を更新して `main` ブランチにpushすると自動で1記事投稿
- **手動**: GitHub Actions の「記事自動投稿」ワークフローから手動実行も可能

## ファイル構成

```
.
├── .github/
│   └── workflows/
│       └── post_article.yml   # GitHub Actionsワークフロー
├── articles/
│   └── topics.txt             # 投稿トピック一覧
├── scripts/
│   └── generate_and_post.py   # 記事生成・投稿スクリプト
├── requirements.txt
└── README.md
```
