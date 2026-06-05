#!/usr/bin/env python3
"""
ジャンクエフェクター リサーチツール
メルカリ / ラクマ / ヤフオク / ハードオフ から販売中品を収集して report.md を生成する

使い方:
    pip install -r requirements_junk_search.txt
    playwright install chromium          # Playwright 利用時
    python junk_effector_search.py
"""

from __future__ import annotations

import asyncio
import logging
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

try:
    from playwright.async_api import async_playwright, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ── 設定 ─────────────────────────────────────────────────────────────────────

KEYWORD = "ジャンク エフェクター"
REQUEST_TIMEOUT = 20        # seconds
PW_TIMEOUT      = 40_000    # ms (Playwright ページ読み込み)
PW_IDLE_WAIT    = 4_000     # ms (JavaScript 描画待ち)
RETRY_DELAYS    = [2, 5]    # seconds between retries

# ブラウザになりすますヘッダー
BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}

# 売り切れ判定正規表現
SOLD_RE = re.compile(
    r"\bSOLD\b|売[り切]?れ?|落札済み?|販売終了|sold[_\s]out",
    re.IGNORECASE,
)

# ── ロギング ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


# ── データモデル ───────────────────────────────────────────────────────────────

@dataclass
class Item:
    title: str
    price: str
    site: str
    condition: str
    link: str
    fetched_at: str = field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M")
    )

    def is_sold(self) -> bool:
        return bool(SOLD_RE.search(self.title) or SOLD_RE.search(self.condition))


def _filter_sold(items: list[Item], site: str) -> list[Item]:
    before = len(items)
    active = [i for i in items if not i.is_sold()]
    removed = before - len(active)
    if removed:
        logger.info(f"  └─ {site}: {removed} 件を SOLD 除外 → 残 {len(active)} 件")
    return active


# ── requests ヘルパー ─────────────────────────────────────────────────────────

def _new_session(referer: str = "") -> requests.Session:
    s = requests.Session()
    headers = dict(BASE_HEADERS)
    if referer:
        headers["Referer"] = referer
    s.headers.update(headers)
    return s


def _get_with_retry(
    session: requests.Session,
    url: str,
    max_retries: int = 2,
) -> requests.Response | None:
    for attempt in range(max_retries + 1):
        try:
            resp = session.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            if attempt < max_retries and e.response is not None and e.response.status_code in (429, 503):
                wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                logger.warning(f"  リトライ {attempt + 1}/{max_retries}（{wait}s 待機）: {e}")
                time.sleep(wait)
            else:
                raise
        except requests.exceptions.RequestException:
            if attempt < max_retries:
                wait = RETRY_DELAYS[min(attempt, len(RETRY_DELAYS) - 1)]
                time.sleep(wait)
            else:
                raise
    return None


# ── ヤフオク（requests） ──────────────────────────────────────────────────────

def scrape_yahoo_auctions(keyword: str) -> list[Item]:
    site = "ヤフオク"
    items: list[Item] = []

    try:
        encoded = urllib.parse.quote(keyword)
        # 先にトップページを訪問してセッション Cookie を取得
        session = _new_session()
        _get_with_retry(session, "https://auctions.yahoo.co.jp/")
        time.sleep(1)

        # status=1: 出品中のみ / n=100: 1ページ最大100件
        url = (
            f"https://auctions.yahoo.co.jp/search/search"
            f"?p={encoded}&status=1&n=100&s1=cbids&o1=d"
        )
        session.headers.update({"Referer": "https://auctions.yahoo.co.jp/"})
        resp = _get_with_retry(session, url)
        if resp is None:
            return items

        soup = BeautifulSoup(resp.text, "html.parser")
        for el in soup.select("li.Product"):
            title_el = el.select_one(".Product__title a, .Product__titleLink")
            price_el = el.select_one(".Product__priceValue")
            link_el  = el.select_one("a.Product__titleLink") or el.select_one(".Product__title a")
            label_el = el.select_one(".Product__label, .Product__status")

            title  = (title_el.get_text(strip=True) if title_el else "").strip()
            price  = (price_el.get_text(strip=True) if price_el else "").strip()
            href   = (link_el.get("href", "") if link_el else "").strip()
            status = (label_el.get_text(strip=True) if label_el else "").strip()

            if not title:
                continue
            items.append(Item(title=title, price=price, site=site,
                              condition=status, link=href))

        logger.info(f"{site}: {len(items)} 件取得（フィルタ前）")
        items = _filter_sold(items, site)

    except Exception as exc:
        logger.error(f"{site} scraping 失敗: {exc}")

    return items


# ── ハードオフ（requests） ────────────────────────────────────────────────────

def scrape_hard_off(keyword: str) -> list[Item]:
    site = "ハードオフ"
    items: list[Item] = []

    try:
        encoded = urllib.parse.quote(keyword)
        session = _new_session()
        _get_with_retry(session, "https://www.hardoff.co.jp/")
        time.sleep(1)

        url = f"https://www.hardoff.co.jp/search/?keyword={encoded}"
        session.headers.update({"Referer": "https://www.hardoff.co.jp/"})
        resp = _get_with_retry(session, url)
        if resp is None:
            return items

        soup = BeautifulSoup(resp.text, "html.parser")

        # 複数セレクタを順に試す（サイトリニューアル対応）
        candidates = (
            soup.select(".p-item-list__item")
            or soup.select(".item-list__item")
            or soup.select("article.item")
            or soup.select("[class*='product-list'] li")
            or soup.select("[class*='item-list'] > li")
        )

        for el in candidates:
            title_el = (
                el.select_one(".p-item-list__item-name")
                or el.select_one(".item-name")
                or el.select_one("h3") or el.select_one("h2")
            )
            price_el = (
                el.select_one(".p-item-list__item-price")
                or el.select_one(".item-price")
                or el.select_one("[class*='price']")
            )
            link_el   = el.select_one("a")
            status_el = (
                el.select_one(".p-item-list__item-status")
                or el.select_one(".item-status")
                or el.select_one("[class*='status']")
            )

            title  = (title_el.get_text(strip=True) if title_el else "").strip()
            price  = (price_el.get_text(strip=True) if price_el else "").strip()
            href   = (link_el.get("href", "") if link_el else "").strip()
            if href and not href.startswith("http"):
                href = f"https://www.hardoff.co.jp{href}"
            status = (status_el.get_text(strip=True) if status_el else "").strip()

            if not title:
                continue
            items.append(Item(title=title, price=price, site=site,
                              condition=status, link=href))

        logger.info(f"{site}: {len(items)} 件取得（フィルタ前）")
        items = _filter_sold(items, site)

    except Exception as exc:
        logger.error(f"{site} scraping 失敗: {exc}")

    return items


# ── メルカリ（Playwright） ────────────────────────────────────────────────────

async def scrape_mercari(keyword: str, ctx: BrowserContext) -> list[Item]:
    site = "メルカリ"
    items: list[Item] = []
    encoded = urllib.parse.quote(keyword)
    url = f"https://jp.mercari.com/search?keyword={encoded}&status=on_sale"

    try:
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=PW_TIMEOUT)
        await page.wait_for_timeout(PW_IDLE_WAIT)

        # 商品グリッドの読み込み待ち（タイムアウトは無視して続行）
        try:
            await page.wait_for_selector(
                '[data-testid="item-cell"], li.merItemThumbnail',
                timeout=10_000,
            )
        except Exception:
            pass

        els = (
            await page.query_selector_all('[data-testid="item-cell"]')
            or await page.query_selector_all("li.merItemThumbnail")
            or await page.query_selector_all('[class*="Items__item"]')
        )
        logger.info(f"  └─ {site}: {len(els)} 要素検出")

        for el in els:
            try:
                title_el = (
                    await el.query_selector('[data-testid="item-name"]')
                    or await el.query_selector('[class*="ItemName"]')
                    or await el.query_selector("p")
                )
                price_el = (
                    await el.query_selector('[data-testid="price"]')
                    or await el.query_selector('[class*="Price__value"]')
                    or await el.query_selector('[class*="price"]')
                )
                link_el = await el.query_selector("a")

                title = (await title_el.inner_text() if title_el else "").strip()
                price = (await price_el.inner_text() if price_el else "").strip()
                href  = ((await link_el.get_attribute("href")) or "") if link_el else ""
                if href and not href.startswith("http"):
                    href = f"https://jp.mercari.com{href}"

                if not title:
                    continue
                items.append(Item(title=title, price=price, site=site,
                                  condition="", link=href))
            except Exception as exc:
                logger.debug(f"{site} 要素パースエラー: {exc}")

        await page.close()
        logger.info(f"{site}: {len(items)} 件取得（フィルタ前）")
        items = _filter_sold(items, site)

    except Exception as exc:
        logger.error(f"{site} scraping 失敗: {exc}")

    return items


# ── ラクマ（Playwright） ──────────────────────────────────────────────────────

async def scrape_rakuma(keyword: str, ctx: BrowserContext) -> list[Item]:
    site = "ラクマ"
    items: list[Item] = []
    encoded = urllib.parse.quote(keyword)
    # fril.jp は楽天ラクマへリダイレクト
    url = f"https://fril.jp/s?query={encoded}&status=selling"

    try:
        page = await ctx.new_page()
        await page.goto(url, wait_until="domcontentloaded", timeout=PW_TIMEOUT)
        await page.wait_for_timeout(PW_IDLE_WAIT)

        content = await page.content()
        await page.close()

        soup = BeautifulSoup(content, "html.parser")
        candidates = (
            soup.select(".item-box")
            or soup.select("[class*='ItemBox']")
            or soup.select("li.item")
            or soup.select("[class*='item-cell']")
        )

        for el in candidates:
            title_el = (
                el.select_one(".item-box__item-name")
                or el.select_one("[class*='itemName']")
                or el.select_one("h3")
            )
            price_el = (
                el.select_one(".item-box__item-price")
                or el.select_one("[class*='price']")
            )
            link_el   = el.select_one("a")
            status_el = el.select_one(
                ".item-box__sold-out-label, [class*='sold'], [class*='status']"
            )

            title  = (title_el.get_text(strip=True) if title_el else "").strip()
            price  = (price_el.get_text(strip=True) if price_el else "").strip()
            href   = (link_el.get("href", "") if link_el else "").strip()
            if href and not href.startswith("http"):
                href = f"https://fril.jp{href}"
            status = (status_el.get_text(strip=True) if status_el else "").strip()

            if not title:
                continue
            items.append(Item(title=title, price=price, site=site,
                              condition=status, link=href))

        logger.info(f"{site}: {len(items)} 件取得（フィルタ前）")
        items = _filter_sold(items, site)

    except Exception as exc:
        logger.error(f"{site} scraping 失敗: {exc}")

    return items


# ── レポート生成 ──────────────────────────────────────────────────────────────

def build_report(results: dict[str, list[Item]]) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        "# ジャンクエフェクター リサーチレポート",
        "",
        f"**検索キーワード:** {KEYWORD}",
        f"**生成日時:** {now}",
        "",
        "---",
        "",
    ]

    for site_name, items in results.items():
        lines.append(f"## {site_name}（{len(items)} 件）")
        lines.append("")
        if not items:
            lines.append("_取得件数 0 件（エラー、対象なし、またはアクセス制限）_")
            lines.append("")
            continue
        for item in items:
            lines.append(f"### {item.title}")
            lines.append(f"- 価格: {item.price}")
            lines.append(f"- サイト: {item.site}")
            if item.condition:
                lines.append(f"- 状態: {item.condition}")
            lines.append(f"- リンク: {item.link}")
            lines.append(f"- 取得日時: {item.fetched_at}")
            lines.append("")

    total = sum(len(v) for v in results.values())
    lines += [
        "---",
        "",
        "## サイト別取得件数サマリー",
        "",
        "| サイト | 販売中の取得件数 |",
        "|--------|----------------|",
    ]
    for site_name, items in results.items():
        lines.append(f"| {site_name} | {len(items)} 件 |")
    lines.append(f"| **合計** | **{total} 件** |")
    lines.append("")

    return "\n".join(lines)


# ── メイン ────────────────────────────────────────────────────────────────────

async def main() -> None:
    t0 = time.time()
    results: dict[str, list[Item]] = {}

    logger.info("=== ヤフオク 検索開始 ===")
    results["ヤフオク"] = scrape_yahoo_auctions(KEYWORD)

    logger.info("=== ハードオフ 検索開始 ===")
    results["ハードオフ"] = scrape_hard_off(KEYWORD)

    if PLAYWRIGHT_AVAILABLE:
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                ctx = await browser.new_context(
                    user_agent=BASE_HEADERS["User-Agent"],
                    locale="ja-JP",
                    extra_http_headers={"Accept-Language": "ja-JP,ja;q=0.9"},
                )
                logger.info("=== メルカリ・ラクマ 同時検索開始 ===")
                mercari_items, rakuma_items = await asyncio.gather(
                    scrape_mercari(KEYWORD, ctx),
                    scrape_rakuma(KEYWORD, ctx),
                )
                results["メルカリ"] = mercari_items
                results["ラクマ"]   = rakuma_items
                await browser.close()
        except Exception as exc:
            logger.error(f"Playwright 起動失敗: {exc}")
            results.setdefault("メルカリ", [])
            results.setdefault("ラクマ", [])
    else:
        logger.warning(
            "Playwright が未インストールのため、メルカリ・ラクマをスキップします。\n"
            "  インストール: pip install playwright && playwright install chromium"
        )
        results["メルカリ"] = []
        results["ラクマ"]   = []

    # レポート生成
    report_path = Path(__file__).parent / "report.md"
    report_path.write_text(build_report(results), encoding="utf-8")

    elapsed = time.time() - t0
    total   = sum(len(v) for v in results.values())

    logger.info("=" * 52)
    logger.info(f"完了（{elapsed:.1f}秒）→ report.md を生成しました")
    logger.info("サイト別取得件数（販売中のみ）:")
    for site, items in results.items():
        logger.info(f"  {site}: {len(items)} 件")
    logger.info(f"  ─────────────")
    logger.info(f"  合計: {total} 件")
    logger.info("=" * 52)


if __name__ == "__main__":
    asyncio.run(main())
