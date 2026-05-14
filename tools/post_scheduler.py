#!/usr/bin/env python3
import os, re, sys
from datetime import date, datetime, timezone, timedelta

try:
    import tweepy
except ImportError:
    print("pip install tweepy が必要です")
    sys.exit(1)

JST = timezone(timedelta(hours=9))
YEAR = 2026


def extract_posts(filepath):
    posts = []
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # ブロックを --- で分割してパース
    blocks = content.split("\n---\n")
    meta = None

    for block in blocks:
        header = re.search(r"\[(\d+)/(\d+)\s+(\d+):(\d+)\s*/\s*([^\]]+)\]", block)
        status = re.search(r"\[ステータス:\s*([^\]]+)\]", block)

        if header and status:
            meta = {
                "month": int(header.group(1)),
                "day": int(header.group(2)),
                "hour": int(header.group(3)),
                "minute": int(header.group(4)),
                "platform": header.group(5).strip(),
                "status": status.group(1).strip(),
            }
        elif meta:
            lines = [l for l in block.strip().splitlines() if not l.startswith("添付画像")]
            text = "\n".join(lines).strip()
            if text:
                posts.append({**meta, "content": text})
            meta = None

    return posts


def load_all_posts(posts_dir="posts"):
    all_posts = []
    for fname in os.listdir(posts_dir):
        if fname.endswith(".md") and not fname.startswith("_"):
            all_posts.extend(extract_posts(os.path.join(posts_dir, fname)))
    return all_posts


def post_to_x(text, dry_run=False):
    if dry_run:
        print(f"  [DRY RUN] {text[:60]}...")
        return True
    client = tweepy.Client(
        consumer_key=os.environ["X_API_KEY"],
        consumer_secret=os.environ["X_API_SECRET"],
        access_token=os.environ["X_ACCESS_TOKEN"],
        access_token_secret=os.environ["X_ACCESS_TOKEN_SECRET"],
    )
    res = client.create_tweet(text=text)
    return bool(res.data)


def main():
    dry_run = "--dry-run" in sys.argv
    now_jst = datetime.now(JST)
    today = now_jst.date()
    current_hour = now_jst.hour

    posts = load_all_posts()

    targets = [
        p for p in posts
        if p["status"] == "確認済み"
        and date(YEAR, p["month"], p["day"]) == today
        and p["hour"] == current_hour
        and "X" in p["platform"]
    ]

    if not targets:
        print(f"{today} {current_hour}時: 投稿なし")
        return

    for p in targets:
        print(f"投稿中: {p['month']}/{p['day']} {p['hour']}:{p['minute']:02d} [{p['platform']}]")
        ok = post_to_x(p["content"], dry_run=dry_run)
        print(f"  X: {'✅' if ok else '❌'}")


if __name__ == "__main__":
    main()
