#!/usr/bin/env python3
"""
ビジネスフォルダ内の .md ファイルを走査し、
dashboard.html の <!-- DOCS-START --> ... <!-- DOCS-END --> の間を更新する。
Claude Code の PostToolUse フックから自動実行される。
"""
import os
import re
from datetime import datetime

BUSINESS_DIR = os.path.dirname(os.path.abspath(__file__))
DASHBOARD    = os.path.join(BUSINESS_DIR, "dashboard.html")

LABELS = {
    "BUSINESS_PLAN":              "事業計画書",
    "REVENUE_MODEL":              "収益モデル",
    "ROADMAP":                    "ロードマップ",
    "COLLAB_STRATEGY":            "コラボ戦略",
    "COMPANY":                    "会社概要",
    "FRETBOARDQUEST_MARKET_ROADMAP": "フレクエ 市場分析 & ロードマップ",
}

# 公開URL
PRODUCT_URLS = {
    "battle": "https://nino-msip.github.io/gita-shiban/fret-board-quest/guitar-battle.html",
    "study":  "https://nino-msip.github.io/gita-shiban/fret-board-quest/",
}

def build_docs_html():
    items = []
    for fname in sorted(os.listdir(BUSINESS_DIR)):
        if not fname.endswith(".md"):
            continue
        stem = fname[:-3]
        path = os.path.join(BUSINESS_DIR, fname)
        mtime = datetime.fromtimestamp(os.path.getmtime(path))
        label = LABELS.get(stem, stem)
        date_str = mtime.strftime("%Y/%m/%d %H:%M")
        items.append(
            f'<div class="doc-item">'
            f'<a class="doc-link" href="{fname}" target="_blank">{label}</a>'
            f'<span class="doc-date">{date_str}</span>'
            f'</div>'
        )
    return "\n".join(items)

def update_dashboard():
    if not os.path.exists(DASHBOARD):
        print(f"[sync] dashboard.html not found: {DASHBOARD}")
        return

    with open(DASHBOARD, encoding="utf-8") as f:
        content = f.read()

    docs_html = build_docs_html()
    pattern   = r"<!-- DOCS-START -->.*?<!-- DOCS-END -->"
    replacement = f"<!-- DOCS-START -->\n{docs_html}\n<!-- DOCS-END -->"

    if not re.search(pattern, content, flags=re.DOTALL):
        print("[sync] marker not found in dashboard.html — skipping")
        return

    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)

    if new_content == content:
        return

    with open(DASHBOARD, "w", encoding="utf-8") as f:
        f.write(new_content)

    print(f"[sync] dashboard updated ({len(items_count(docs_html))} docs)")

def items_count(html):
    return re.findall(r'class="doc-item"', html)

if __name__ == "__main__":
    update_dashboard()
