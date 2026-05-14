#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MoritaSaki Entertainment — Notion ワークスペース自動構築スクリプト
実行方法: python3 setup_notion.py
"""

import json
import urllib.request
import urllib.error
import sys
import time
import os

# ─── 設定（環境変数 or 対話入力）──────────────────────────────────────────────
def load_config():
    token   = os.environ.get("NOTION_TOKEN", "").strip()
    page_id = os.environ.get("NOTION_PAGE_ID", "").strip()

    if not token:
        print("Notion Integration Token を入力してください（secret_ または ntn_ で始まる文字列）:")
        token = input("> ").strip()
    if not page_id:
        print("親ページの ID を入力してください（32桁の英数字）:")
        page_id = input("> ").strip()

    return token, page_id

NOTION_VER  = "2022-06-28"
BASE_URL    = "https://api.notion.com/v1"
TOKEN       = ""
PARENT_PAGE = ""

# ─── API ヘルパー ───────────────────────────────────────────────────────────────
def api(method, path, data=None):
    url = BASE_URL + path
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Notion-Version": NOTION_VER,
        "Content-Type": "application/json",
    }
    body = json.dumps(data, ensure_ascii=False).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        msg = e.read().decode("utf-8")
        print(f"\n❌ APIエラー {e.code} ({method} {path})")
        try:
            err = json.loads(msg)
            print(f"   {err.get('message', msg)}")
        except Exception:
            print(f"   {msg[:300]}")
        sys.exit(1)

def txt(content):
    return [{"type": "text", "text": {"content": content}}]

def bold_txt(content):
    return [{"type": "text", "text": {"content": content}, "annotations": {"bold": True}}]

def heading(level, content):
    t = f"heading_{level}"
    return {"object": "block", "type": t, t: {"rich_text": txt(content)}}

def para(content):
    return {"object": "block", "type": "paragraph", "paragraph": {"rich_text": txt(content)}}

def bullet(content):
    return {"object": "block", "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": txt(content)}}

def divider():
    return {"object": "block", "type": "divider", "divider": {}}

def callout(content, emoji="📌"):
    return {"object": "block", "type": "callout", "callout": {
        "rich_text": txt(content),
        "icon": {"type": "emoji", "emoji": emoji},
    }}

def table_row(*cells):
    return {"object": "block", "type": "table_row",
            "table_row": {"cells": [txt(c) for c in cells]}}

def table(width, has_header, rows):
    return {"object": "block", "type": "table", "table": {
        "table_width": width,
        "has_column_header": has_header,
        "has_row_header": False,
        "children": rows,
    }}

def append_blocks(page_id, blocks):
    for i in range(0, len(blocks), 100):
        api("PATCH", f"/blocks/{page_id}/children", {"children": blocks[i:i+100]})
        time.sleep(0.3)

# ─── ① タスクDB ────────────────────────────────────────────────────────────────
def create_tasks_db():
    print("  ✅ タスクDB を作成中...")
    db = api("POST", "/databases", {
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
        "icon": {"type": "emoji", "emoji": "✅"},
        "title": txt("✅ タスクDB"),
        "properties": {
            "タスク名": {"title": {}},
            "ステータス": {"select": {"options": [
                {"name": "未着手",  "color": "gray"},
                {"name": "進行中",  "color": "blue"},
                {"name": "完了",    "color": "green"},
            ]}},
            "優先度": {"select": {"options": [
                {"name": "🔴 緊急", "color": "red"},
                {"name": "🟡 今週", "color": "yellow"},
                {"name": "🟢 月内", "color": "green"},
            ]}},
            "カテゴリ": {"select": {"options": [
                {"name": "SNS",      "color": "blue"},
                {"name": "ライブ",   "color": "purple"},
                {"name": "ビジネス", "color": "orange"},
                {"name": "プレス",   "color": "pink"},
                {"name": "物販",     "color": "yellow"},
            ]}},
            "期日":  {"date": {}},
            "担当":  {"rich_text": {}},
            "メモ":  {"rich_text": {}},
        },
    })
    db_id = db["id"]

    tasks = [
        # (タスク名, ステータス, 優先度, カテゴリ, 期日, メモ)
        ("Bufferアカウント作成・XとInstagramを接続",
         "未着手", "🔴 緊急", "SNS", None, "SOCIAL_SETUP.mdを参照"),
        ("大阪チケット会社へ状況確認の連絡",
         "未着手", "🔴 緊急", "ライブ", None, "現在約50枚。状況不明のため要確認"),
        ("全SNSプロフィールのリンクをチケットURLに変更",
         "未着手", "🔴 緊急", "SNS", None, "X・Instagram 両方のプロフィール"),
        ("InstagramをクリエイターアカウントへSW",
         "未着手", "🟡 今週", "SNS", None, "SOCIAL_SETUP.md ステップ1参照"),
        ("posts/2026-05-week3.md の草稿を確認・承認",
         "未着手", "🟡 今週", "SNS", "2026-05-19", "コンテンツカレンダーDBでも確認可能"),
        ("草稿の（チケットURL）箇所にURLを入力",
         "未着手", "🟡 今週", "SNS", "2026-05-19", "全3ファイル分（5月・6月前半・6月後半）"),
        ("英語プレスキット（バイオ+写真）の作成",
         "未着手", "🟢 月内", "プレス", "2026-05-31", "英語バイオ300語 + アーティスト写真3〜5枚"),
        ("Bandcamp Daily へのピッチ（英語メール）",
         "未着手", "🟢 月内", "プレス", "2026-05-31", "プレスキット完成後に送付"),
        ("Time Out Tokyo にライブ情報を掲載申請",
         "未着手", "🟢 月内", "ライブ", "2026-06-07", "6/27東京公演の英語告知"),
        ("Spotify for Artists — 週次リスナー数を確認",
         "未着手", "🟢 月内", "SNS", None, "毎週月曜に確認・KPIページに記録"),
        ("大阪公演の投稿草稿を確認・Buffer登録",
         "未着手", "🟢 月内", "SNS", "2026-06-07", "posts/2026-06-week1-2.md"),
        ("6月ツアー後の振り返りミーティング設定",
         "未着手", "🟢 月内", "ビジネス", "2026-07-01", "チケット・物販・SNS数値を整理"),
    ]

    print(f"     タスク {len(tasks)} 件を追加中...")
    for name, status, priority, category, due, memo in tasks:
        props = {
            "タスク名":   {"title": txt(name)},
            "ステータス": {"select": {"name": status}},
            "優先度":     {"select": {"name": priority}},
            "カテゴリ":   {"select": {"name": category}},
        }
        if due:  props["期日"] = {"date": {"start": due}}
        if memo: props["メモ"] = {"rich_text": txt(memo)}
        api("POST", "/pages", {
            "parent": {"type": "database_id", "database_id": db_id},
            "properties": props,
        })
        time.sleep(0.2)

    return db_id

# ─── ② コンテンツカレンダーDB ────────────────────────────────────────────────────
def create_calendar_db():
    print("  📅 コンテンツカレンダーDB を作成中...")
    db = api("POST", "/databases", {
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
        "icon": {"type": "emoji", "emoji": "📅"},
        "title": txt("📅 コンテンツカレンダーDB"),
        "properties": {
            "投稿タイトル":     {"title": {}},
            "投稿本文":         {"rich_text": {}},
            "プラットフォーム": {"multi_select": {"options": [
                {"name": "X",         "color": "gray"},
                {"name": "Instagram", "color": "pink"},
                {"name": "両方",      "color": "purple"},
            ]}},
            "投稿予定日時": {"date": {}},
            "ステータス": {"select": {"options": [
                {"name": "草稿",     "color": "gray"},
                {"name": "確認待ち", "color": "yellow"},
                {"name": "承認済み", "color": "blue"},
                {"name": "投稿済み", "color": "green"},
            ]}},
            "添付画像メモ": {"rich_text": {}},
            "言語": {"select": {"options": [
                {"name": "日本語",   "color": "red"},
                {"name": "英語",     "color": "blue"},
                {"name": "日英混在", "color": "purple"},
            ]}},
        },
    })
    db_id = db["id"]

    # (タイトル, 本文, プラットフォーム[], 日付, 言語, 画像メモ)
    posts = [
        ("5/20 リリース告知",
         '2nd album "KIDCORE SCULPTURE" out now.\n聴いてください。そして6月、ライブで会いましょう。\n6/14 Osaka CONPASS / 6/27 Tokyo GARRET udagawa\nTickets → [URL]',
         ["両方"], "2026-05-20", "日英混在", "アルバムジャケット"),
        ("5/21 Reels① Instagram",
         "Recording sessions for KIDCORE SCULPTURE.\nThis album took us somewhere different.\nOut now on all platforms.",
         ["Instagram"], "2026-05-21", "英語", "スタジオ録音風景 or 機材写真"),
        ("5/21 X投稿",
         "アルバムの中で一番ライブで鳴らすのが楽しみな曲がある。\n6月に聴きに来てほしい。",
         ["X"], "2026-05-21", "日本語", "なし"),
        ("5/22 チケット誘導",
         "「この曲をライブで聴きたい人へ」\n6/27 東京 GARRET udagawa → [URL]",
         ["X"], "2026-05-22", "日本語", "なし"),
        ("5/24 カウントダウン開始",
         "「東京まで◯日」カウントダウン開始\nTickets → [URL]",
         ["X"], "2026-05-24", "日本語", "なし"),
        ("5/26 残席案内",
         "6/27 東京のチケット、まだ間に合います。\nKIDCORE SCULPTUREを出したばかりの今、ライブで聴けるのは6月だけ。→ [URL]",
         ["X"], "2026-05-26", "日本語", "なし"),
        ("5/28 英語告知（海外向け）",
         'If you\'re in Tokyo on June 27, come hear KIDCORE SCULPTURE live.\nWe\'ve been building toward this for a while.\nGARRET udagawa, Shibuya → [URL]\n#shoegaze #tokyomusic #livemusic #japaneseband',
         ["両方"], "2026-05-28", "英語", "ライブ写真（過去公演可）"),
        ("5/30 Reels②",
         "Osaka, June 14. Tokyo, June 27.\nTwo shows. New album. Come find us.\nTickets → link in bio\n#MoritaSakiinthepool #KIDCORESCULPTURE #shoegaze",
         ["Instagram"], "2026-05-30", "英語", "演奏映像（縦型）"),
        ("5/31 1週まとめ",
         "KIDCORE SCULPTUREを出してから1週間。\n聴いてくれた人、ありがとう。\n6月のライブで、この音を生で鳴らします。→ [URL]",
         ["X"], "2026-05-31", "日本語", "なし"),
        ("6/2 大阪2週前 X",
         "大阪まで2週間を切った。\nLIVE SPACE CONPASS、久しぶりに行く。楽しみにしてる。",
         ["X"], "2026-06-02", "日本語", "なし"),
        ("6/2 大阪2週前 Instagram",
         "2 weeks until Osaka.\n1 month until Tokyo.\nKIDCORE SCULPTURE — out now.\nTickets → link in bio\n#shoegaze #osakagig #tokyomusic",
         ["Instagram"], "2026-06-02", "英語", "アルバムジャケット or ライブ写真"),
        ("6/4 機材Reels",
         "The sounds on KIDCORE SCULPTURE, live.",
         ["Instagram"], "2026-06-04", "英語", "ペダルボード・エフェクター映像（縦型）★音楽マニア層に刺さる"),
        ("6/6 残席・両公演告知",
         "6/14 Osaka LIVE SPACE CONPASS\n6/27 Tokyo GARRET udagawa\nチケットの残りが少なくなってきています。→ [URL]\nLast tickets available.",
         ["両方"], "2026-06-06", "日英混在", "ライブ告知画像"),
        ("6/9 大阪5日前 X",
         "大阪まで5日。\n今年の6月で一番いい夜にする。",
         ["X"], "2026-06-09", "日本語", "なし"),
        ("6/9 大阪5日前 Instagram",
         "5 days until Osaka.\nIf you've been listening to KIDCORE SCULPTURE —\nthis is where it becomes real.\nTickets at link in bio.\n#shoegaze #osakajapan #livemusic",
         ["Instagram"], "2026-06-09", "英語", "リハーサル or サウンドチェック風景"),
        ("6/11 大阪ラスト告知",
         "大阪公演 6/14（日）LIVE SPACE CONPASS\n残りわずかです。→ [URL]\nOsaka, this Sunday. Last few tickets.",
         ["両方"], "2026-06-11", "日英混在", "会場写真 or 過去大阪公演写真"),
        ("6/13 大阪前日",
         "明日、大阪。",
         ["両方"], "2026-06-13", "日本語", "移動・荷造り・準備の写真（自然な雰囲気）"),
        ("6/15 大阪翌日★重要",
         "大阪、最高だった。ありがとう。\n次は東京。6/27 GARRET udagawa。残席あとわずか。→ [URL]\nOsaka was something else. Thank you.\nTokyo, June 27. Very few tickets left.",
         ["両方"], "2026-06-15", "日英混在", "大阪公演写真★必ず撮っておく"),
        ("6/17 東京10日前 Reels",
         "Tokyo in 10 days. GARRET udagawa, Shibuya.\nTickets → link in bio\n#shoegaze #tokyomusic #livemusic",
         ["Instagram"], "2026-06-17", "英語", "大阪公演の演奏映像切り抜き（縦型）★最重要コンテンツ"),
        ("6/20 東京残席最終",
         "6/27 東京、残りわずかです。\nKIDCORE SCULPTUREを出したばかりの今しか聴けないセットリストをやります。→ [URL]\nTokyo, June 27. Last few tickets.\nGARRET udagawa, Shibuya — doors open 18:30.",
         ["両方"], "2026-06-20", "日英混在", "ライブ写真（臨場感のあるもの）"),
        ("6/22 東京5日前",
         "5 days.\nIf you're still thinking about it —\nthis is the moment.\nTokyo June 27, GARRET udagawa.\nTickets at link in bio.",
         ["Instagram"], "2026-06-22", "英語", "アーティスト写真（引き気味）"),
        ("6/25 前々日",
         "もう2日。\nTwo days.\n#MoritaSakiinthepool #627tokyo",
         ["両方"], "2026-06-25", "日英混在", "カウントダウン画像（シンプルでOK）"),
        ("6/27 公演当日",
         "今日です。\nGARRET udagawa\nOPEN 18:30 / START 19:00",
         ["両方"], "2026-06-27", "日英混在", "サウンドチェック・会場入りの写真（リアルタイム感）"),
    ]

    print(f"     投稿 {len(posts)} 件を追加中...")
    for title, body, platforms, date, lang, image_note in posts:
        props = {
            "投稿タイトル":     {"title": txt(title)},
            "投稿本文":         {"rich_text": txt(body)},
            "プラットフォーム": {"multi_select": [{"name": pl} for pl in platforms]},
            "投稿予定日時":     {"date": {"start": date}},
            "ステータス":       {"select": {"name": "確認待ち"}},
            "言語":             {"select": {"name": lang}},
            "添付画像メモ":     {"rich_text": txt(image_note)},
        }
        api("POST", "/pages", {
            "parent": {"type": "database_id", "database_id": db_id},
            "properties": props,
        })
        time.sleep(0.2)

    return db_id

# ─── ③ KPI・チケット管理ページ ─────────────────────────────────────────────────
def create_kpi_page():
    print("  📊 KPI・チケット管理ページを作成中...")
    page = api("POST", "/pages", {
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
        "icon": {"type": "emoji", "emoji": "📊"},
        "properties": {"title": {"title": txt("📊 KPI・チケット管理")}},
    })
    pid = page["id"]

    blocks = [
        callout("毎週月曜にチケット枚数を更新 / 毎月末にKPI数値を記録", "📌"),
        divider(),
        heading(2, "🎟 チケット進捗（毎週更新）"),
        table(6, True, [
            table_row("公演",      "販売済",  "目標",  "残り",   "残日数", "状況"),
            table_row("大阪 6/14", "50",      "150",   "100",    "33日",   "🟡 要加速"),
            table_row("東京 6/27", "104",     "200",   "96",     "46日",   "🟢 順調"),
        ]),
        para("※ 毎週月曜に「販売済」「残り」「残日数」「状況」を書き換えてください"),
        divider(),
        heading(2, "📈 月次KPI（毎月末に記録）"),
        table(6, True, [
            table_row("月",          "Spotify月間",  "X",     "Instagram", "TikTok",  "メモ"),
            table_row("2026/04",     "—",            "4,036", "1,953",     "未開設",  ""),
            table_row("2026/05",     "22,500",       "",      "",          "",        "アルバムリリース月"),
            table_row("2026/06",     "",             "",      "",          "",        "ツアー月"),
            table_row("2026/07",     "",             "",      "",          "",        ""),
            table_row("目標（9月末）","50,000",       "12,000","6,000",     "1,000",   ""),
        ]),
        divider(),
        heading(2, "💰 収益メモ"),
        table(4, True, [
            table_row("日付",   "種別",         "金額（税込）", "メモ"),
            table_row("6/14",   "大阪チケット", "",             ""),
            table_row("6/14",   "大阪物販",     "",             ""),
            table_row("6/27",   "東京チケット", "",             ""),
            table_row("6/27",   "東京物販",     "",             ""),
            table_row("6月計",  "合計",         "",             ""),
        ]),
    ]

    append_blocks(pid, blocks)
    return pid

# ─── ④ ホームページ ────────────────────────────────────────────────────────────
def create_home_page():
    print("  🏠 ホームページを作成中...")
    page = api("POST", "/pages", {
        "parent": {"type": "page_id", "page_id": PARENT_PAGE},
        "icon": {"type": "emoji", "emoji": "🏠"},
        "properties": {"title": {"title": txt("🏠 ホーム")}},
    })
    pid = page["id"]

    blocks = [
        callout("毎朝ここを開いて今日のタスクと次の投稿を確認する", "☀️"),
        divider(),
        heading(2, "📌 クイックリンク"),
        bullet("チケット LivePocket → [URLをここに貼る]"),
        bullet("チケット e+ → [URLをここに貼る]"),
        bullet("Buffer（SNSスケジューラー）→ buffer.com"),
        bullet("Spotify for Artists → [URLをここに貼る]"),
        bullet("バンドInstagram → instagram.com/moritasaki_in_the_pool"),
        bullet("バンドX → x.com/mosakiinthepool"),
        divider(),
        heading(2, "🎟 今週のチケット状況"),
        table(4, True, [
            table_row("公演",      "販売済", "目標", "残り"),
            table_row("大阪 6/14", "50",     "150",  "100"),
            table_row("東京 6/27", "104",    "200",  "96"),
        ]),
        para("→ 詳細は「📊 KPI・チケット管理」を開いて更新してください"),
        divider(),
        heading(2, "✅ 今週のタスク"),
        para("→ 「✅ タスクDB」を開く（優先度でフィルターして確認）"),
        divider(),
        heading(2, "📅 次の投稿"),
        para("→ 「📅 コンテンツカレンダーDB」を開く（カレンダービューを追加すると見やすい）"),
        divider(),
        heading(2, "📋 週次確認リスト（月曜の習慣）"),
        {"object": "block", "type": "to_do", "to_do": {"rich_text": txt("チケット枚数を更新（KPIページ）"), "checked": False}},
        {"object": "block", "type": "to_do", "to_do": {"rich_text": txt("今週の投稿草稿を確認・承認（コンテンツカレンダーDB）"), "checked": False}},
        {"object": "block", "type": "to_do", "to_do": {"rich_text": txt("Bufferに承認済み投稿をスケジュール登録"), "checked": False}},
        {"object": "block", "type": "to_do", "to_do": {"rich_text": txt("Spotify for Artistsで数値確認"), "checked": False}},
    ]

    append_blocks(pid, blocks)
    return pid

# ─── メイン ────────────────────────────────────────────────────────────────────
def main():
    global TOKEN, PARENT_PAGE
    TOKEN, PARENT_PAGE = load_config()
    print("\n🚀 MoritaSaki Entertainment — Notion ワークスペース構築開始\n")

    tasks_db_id    = create_tasks_db();    time.sleep(0.5)
    calendar_db_id = create_calendar_db(); time.sleep(0.5)
    kpi_page_id    = create_kpi_page();    time.sleep(0.5)
    home_page_id   = create_home_page()

    print("\n" + "─" * 55)
    print("✅ セットアップ完了！")
    print("─" * 55)
    print("Notionを開いて「MoritaSaki Entertainment」ページを確認してください。")
    print()
    print("作成されたもの：")
    print("  🏠 ホーム（週次チェックリスト付き）")
    print("  ✅ タスクDB（タスク12件入力済み）")
    print("  📅 コンテンツカレンダーDB（投稿23件入力済み）")
    print("  📊 KPI・チケット管理（進捗表・収益メモ付き）")
    print()
    print("次にやること：")
    print("  1. ホームページにチケットURLとBuffer URLを貼る")
    print("  2. タスクDBに「ボードビュー」を追加（+ビューを追加 → ボード）")
    print("  3. コンテンツカレンダーDBに「カレンダービュー」を追加")
    print("─" * 55)

if __name__ == "__main__":
    main()
