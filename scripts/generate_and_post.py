#!/usr/bin/env python3
"""
note.com 記事自動投稿スクリプト
Claude AIで記事を生成し、note.comに投稿します。
"""

import os
import sys
import json
import random
import requests


TOPICS_FILE = os.path.join(os.path.dirname(__file__), '..', 'articles', 'topics.txt')
NOTE_API_BASE = 'https://note.com/api'


def load_topics() -> list[str]:
    """トピックファイルから投稿候補を読み込む"""
    if not os.path.exists(TOPICS_FILE):
        print(f"Error: topics file not found at {TOPICS_FILE}", file=sys.stderr)
        sys.exit(1)

    topics = []
    with open(TOPICS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                topics.append(line)

    if not topics:
        print("Error: no topics found in topics file", file=sys.stderr)
        sys.exit(1)

    return topics


def generate_article(topic: str, api_key: str) -> tuple[str, str]:
    """Claude APIを使って記事を生成し、(タイトル, 本文) を返す"""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""以下のトピックについて、note.comに投稿する記事を日本語で書いてください。

トピック: {topic}

以下のフォーマットで出力してください：
---TITLE---
[ここにタイトル（30〜50文字程度）]
---BODY---
[ここに本文（1000〜2000文字程度）。見出し（##）や箇条書きを使って読みやすく構成してください。]

注意：
- タイトルと本文は必ず上記フォーマットで出力すること
- 読者が具体的なアクションを取れるよう実用的な内容にすること
- 親しみやすい文体で書くこと
"""

    message = client.messages.create(
        model='claude-opus-4-6',
        max_tokens=4096,
        messages=[{'role': 'user', 'content': prompt}],
    )

    text = message.content[0].text

    # タイトルと本文をパース
    title = ''
    body = ''
    if '---TITLE---' in text and '---BODY---' in text:
        parts = text.split('---BODY---')
        title_part = parts[0].split('---TITLE---')[-1].strip()
        body_part = parts[1].strip()
        title = title_part
        body = body_part
    else:
        # フォールバック：最初の行をタイトル、残りを本文とする
        lines = text.strip().split('\n')
        title = lines[0].lstrip('#').strip()
        body = '\n'.join(lines[1:]).strip()

    return title, body


def login_to_note(email: str, password: str) -> requests.Session:
    """note.comにログインしてセッションを返す"""
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (compatible; ArticleBot/1.0)',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        'Referer': 'https://note.com/',
    })

    response = session.post(
        f'{NOTE_API_BASE}/v1/sessions',
        json={'login': email, 'password': password},
        timeout=30,
    )

    if response.status_code != 200:
        print(f"Error: login failed (status={response.status_code})", file=sys.stderr)
        print(f"Response: {response.text[:500]}", file=sys.stderr)
        sys.exit(1)

    data = response.json()
    print(f"Logged in as: {data.get('data', {}).get('nickname', email)}")
    return session


def post_article(session: requests.Session, title: str, body: str) -> dict:
    """note.comに記事を投稿する"""
    payload = {
        'name': title,
        'body': body,
        'status': 'published',
        'publish_at': None,
    }

    response = session.post(
        f'{NOTE_API_BASE}/v2/text_notes',
        json=payload,
        timeout=30,
    )

    if response.status_code not in (200, 201):
        print(f"Error: failed to post article (status={response.status_code})", file=sys.stderr)
        print(f"Response: {response.text[:500]}", file=sys.stderr)
        sys.exit(1)

    return response.json()


def main():
    # 環境変数から設定を読み込む
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
    note_email = os.environ.get('NOTE_EMAIL')
    note_password = os.environ.get('NOTE_PASSWORD')

    missing = [k for k, v in {
        'ANTHROPIC_API_KEY': anthropic_key,
        'NOTE_EMAIL': note_email,
        'NOTE_PASSWORD': note_password,
    }.items() if not v]

    if missing:
        print(f"Error: missing environment variables: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    # トピックをランダムに選択
    topics = load_topics()
    topic = random.choice(topics)
    print(f"Selected topic: {topic}")

    # Claude APIで記事を生成
    print("Generating article with Claude AI...")
    title, body = generate_article(topic, anthropic_key)
    print(f"Generated title: {title}")
    print(f"Body length: {len(body)} characters")

    # note.comにログイン
    print("Logging in to note.com...")
    session = login_to_note(note_email, note_password)

    # 記事を投稿
    print("Posting article to note.com...")
    result = post_article(session, title, body)

    note_key = result.get('data', {}).get('key', '')
    note_url = f"https://note.com/n/{note_key}" if note_key else "unknown"
    print(f"Successfully posted article!")
    print(f"URL: {note_url}")


if __name__ == '__main__':
    main()
