#!/usr/bin/env python3
"""Notionのタスクデータベースにタスクを追加するスクリプト"""
import os
import json
import urllib.request
import urllib.error

def notion_request(token, method, path, body=None):
    url = f"https://api.notion.com/v1{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Notion-Version", "2022-06-28")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"エラー {e.code}: {e.read().decode()}")
        return None

def find_tasks_db(token):
    result = notion_request(token, "POST", "/search", {
        "query": "タスク",
        "filter": {"value": "database", "property": "object"}
    })
    if result and result.get("results"):
        for db in result["results"]:
            title = db.get("title", [])
            if title and "タスク" in title[0].get("plain_text", ""):
                return db["id"]
    return None

def add_task(token, db_id, title, priority, category, due_date, notes):
    body = {
        "parent": {"database_id": db_id},
        "properties": {
            "タスク名": {"title": [{"text": {"content": title}}]},
            "優先度": {"select": {"name": priority}},
            "カテゴリ": {"select": {"name": category}},
            "ステータス": {"select": {"name": "📋 未着手"}},
            "期日": {"date": {"start": due_date}},
            "メモ": {"rich_text": [{"text": {"content": notes}}]}
        }
    }
    return notion_request(token, "POST", "/pages", body)

def main():
    token = os.environ.get("NOTION_TOKEN", "").strip()
    if not token:
        token = input("Notion Token: ").strip()

    print("タスクDBを検索中...")
    db_id = find_tasks_db(token)
    if not db_id:
        print("タスクDBが見つかりませんでした。DBのIDを直接入力してください:")
        db_id = input("DB ID: ").strip()

    print(f"DB ID: {db_id}")

    new_tasks = [
        {
            "title": "Bufferアカウント作成・XとInstagramを接続",
            "priority": "🔴 緊急",
            "category": "SNS",
            "due_date": "2026-05-20",
            "notes": "buffer.com で無料アカウント作成 → X (Twitter) と Instagram を接続 → SOCIAL_SETUP.md を参照"
        },
        {
            "title": "InstagramをCreatorアカウントに切り替え",
            "priority": "🔴 緊急",
            "category": "SNS",
            "due_date": "2026-05-15",
            "notes": "設定 → アカウント → プロアカウントに切り替え → クリエイター選択。Buffer接続の前提条件。"
        }
    ]

    for task in new_tasks:
        print(f"追加中: {task['title']}")
        result = add_task(token, db_id, task["title"], task["priority"], task["category"], task["due_date"], task["notes"])
        if result:
            print(f"  ✅ 追加完了")
        else:
            print(f"  ❌ 失敗")

    print("\n完了！Notionのタスクビューを確認してください。")

if __name__ == "__main__":
    main()
