#!/usr/bin/env python3
"""外部メディア (HotPepper Beauty / Instagram) からの指標をスクレイプ。

実行:
  python3 scripts/scrape_external.py hotpepper       # 全店舗 HotPepper評価
  python3 scripts/scrape_external.py instagram       # 全店舗 IG フォロワー数
  python3 scripts/scrape_external.py all             # 両方

設定:
  data/external_targets.json (店舗別 URL を管理):
  {
    "tsunashima": {
      "hotpepper": "https://beauty.hotpepper.jp/...",
      "instagram": "https://www.instagram.com/hanabi_tsunashima/"
    },
    "miyakojima": {
      "hotpepper": "https://beauty.hotpepper.jp/...",
      "instagram": "https://www.instagram.com/elle_by_hanabi/"
    }
  }

出力: data/external_<source>_<YYYYMMDD>.json
  履歴を残すことで時系列推移を取れる。
"""
from __future__ import annotations

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)


def load_targets() -> dict:
    p = DATA / "external_targets.json"
    if not p.exists():
        # Create template
        template = {
            "_comment": "店舗別の外部メディア URL を管理。 URL未設定の店舗は scrape スキップ。",
            "tsunashima": {
                "hotpepper": "",
                "instagram": ""
            },
            "miyakojima": {
                "hotpepper": "",
                "instagram": ""
            }
        }
        p.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"⚠️ created template at {p} — URL を手動入力後に再実行してください")
        sys.exit(0)
    return json.loads(p.read_text(encoding="utf-8"))


def scrape_hotpepper(page, url: str) -> dict:
    """HotPepper Beauty の店舗ページから 評価 + 口コミ件数 + 直近口コミ を取得。"""
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(2)
    result = page.evaluate(r"""
        () => {
            const out = {};
            // 評価点 (例: 4.7)
            const rateEl = document.querySelector('.point') || document.querySelector('[class*="rating"]') || document.querySelector('.s_rate');
            if (rateEl) {
                const m = rateEl.textContent.match(/[\d.]+/);
                if (m) out.rating = parseFloat(m[0]);
            }
            // 口コミ件数 - 複数パターン対応
            const fullText = document.body.innerText;
            // Pattern 1: '（366件）' (HPB main: rating 横の小カウント、 全角カッコ)
            let m1 = fullText.match(/[（(]\s*([0-9,]+)\s*件\s*[)）]/);
            if (!m1) {
              // Pattern 2: 'X件のお客様の声'
              m1 = fullText.match(/([0-9,]+)\s*件\s*の\s*お客様の声/);
            }
            if (!m1) {
              // Pattern 3: '口コミ X件'
              m1 = fullText.match(/口コミ[\s]*([0-9,]+)\s*件/);
            }
            if (m1) out.review_count = parseInt(m1[1].replace(/,/g, ''));
            // ブログ件数 (参考)
            const m2 = fullText.match(/ブログ\s*([0-9,]+)\s*件/);
            if (m2) out.blog_count = parseInt(m2[1].replace(/,/g, ''));
            // セレクタ直接アクセス (rating-count class や slnHeaderKuchikomiCount)
            if (!out.review_count) {
              const cntEl = document.querySelector('.rating-count, .slnHeaderKuchikomiCount, [class*="kuchikomi"][class*="ount"]');
              if (cntEl) {
                const m = cntEl.textContent.match(/([0-9,]+)/);
                if (m) out.review_count = parseInt(m[1].replace(/,/g, ''));
              }
            }
            // 店舗名
            const nameEl = document.querySelector('h1, .salon-name, [class*="salonName"]');
            if (nameEl) out.salon_name = nameEl.textContent.trim().slice(0, 50);
            return out;
        }
    """)
    # 口コミタブへ移動して最新口コミ N件取得 (URL末尾に /review/ を付ければレビュータブ)
    try:
        review_url = url.rstrip("/") + "/review/"
        page.goto(review_url, wait_until="domcontentloaded", timeout=15000)
        time.sleep(2)
        reviews = page.evaluate(r"""
            () => {
                // 口コミブロック (HotPepperのHTML構造に依存)
                const blocks = document.querySelectorAll('[class*="review"], .reviewBlock, .cFix > section');
                const out = [];
                for (const b of blocks) {
                    const textEl = b.querySelector('p, .reviewBody, [class*="reviewText"]');
                    const dateEl = b.querySelector('time, [class*="date"], .reviewDate');
                    const ratingEl = b.querySelector('[class*="rating"], .reviewRate');
                    if (!textEl) continue;
                    const text = textEl.textContent.trim().slice(0, 200);
                    if (!text || text.length < 10) continue;
                    out.push({
                        text,
                        date: dateEl ? dateEl.textContent.trim().slice(0, 20) : "",
                        rating: ratingEl ? parseFloat((ratingEl.textContent.match(/[\d.]+/) || [""])[0]) || null : null,
                    });
                    if (out.length >= 10) break;
                }
                return out;
            }
        """)
        result["recent_reviews"] = reviews
    except Exception as e:
        print(f"    warn: reviews fetch failed: {e}")
        result["recent_reviews"] = []
    return result


def scrape_instagram(page, url: str) -> dict:
    """Instagram の公開プロフィールページから フォロワー数 / 投稿数 を取得。
    Note: Instagram は React + login modal で bot 検出が厳しい。
    複数の方法で取得を試みる:
      1. ページ全体のテキストから '投稿 X件' 'フォロワー X' 'フォロー中 X' を正規表現で
      2. meta description の英語/日本語パターン
      3. JSON-LD / __NEXT_DATA__ から構造化データ取得
    """
    page.goto(url, wait_until="domcontentloaded")
    time.sleep(5)  # React render 待ち
    # 登録モーダルを Esc で閉じる試み (ボディテキストが隠れる対策)
    try:
        page.keyboard.press("Escape")
        time.sleep(1)
    except Exception:
        pass
    return page.evaluate(r"""
        () => {
            const out = {};
            const url = location.pathname;
            const um = url.match(/^\/([^\/]+)/);
            if (um) out.username = um[1];

            const parseNum = s => {
                if (s == null) return null;
                s = String(s).replace(/[,，]/g, '').trim();
                let mult = 1;
                if (/k$/i.test(s)) { mult = 1000; s = s.replace(/k$/i, ''); }
                else if (/m$/i.test(s)) { mult = 1000000; s = s.replace(/m$/i, ''); }
                else if (s.endsWith('万')) { mult = 10000; s = s.replace('万', ''); }
                else if (s.endsWith('千')) { mult = 1000; s = s.replace('千', ''); }
                const n = parseFloat(s);
                return isNaN(n) ? null : Math.round(n * mult);
            };

            // === Method 1: ページ全体のテキストから検索 ===
            // 日本語UI例: '投稿 675件' 'フォロワー 1,442人' 'フォロー中 939人'
            // 数値は連続したスペース/カンマ含む '1,442' などをマッチ
            const fullText = document.body.innerText || '';
            // 投稿数: '投稿 数' / '数 件の投稿' / 'Posts 数'
            let m;
            if ((m = fullText.match(/(?:^|\s|\n)投稿[\s　]+([\d,\.]+[万千KMkm]?)/))) out.posts = parseNum(m[1]);
            else if ((m = fullText.match(/([\d,\.]+[万千]?)\s*件の投稿/))) out.posts = parseNum(m[1]);
            else if ((m = fullText.match(/([\d,\.]+[KMkm]?)\s*posts?/i))) out.posts = parseNum(m[1]);
            // フォロワー
            if ((m = fullText.match(/フォロワー[\s　]+([\d,\.]+[万千KMkm]?)/))) out.followers = parseNum(m[1]);
            else if ((m = fullText.match(/([\d,\.]+[KMkm]?)\s*followers?/i))) out.followers = parseNum(m[1]);
            // フォロー中
            if ((m = fullText.match(/フォロー中[\s　]+([\d,\.]+[万千KMkm]?)/))) out.following = parseNum(m[1]);
            else if ((m = fullText.match(/([\d,\.]+[KMkm]?)\s*following/i))) out.following = parseNum(m[1]);

            // === Method 2: meta description (og:description が最も確実) ===
            // 例: 'フォロワー1,443人、フォロー中948人、投稿671件 ― ...'
            const metas = document.querySelectorAll('meta[name="description"], meta[property="og:description"]');
            for (const meta of metas) {
                const c = meta.getAttribute('content') || '';
                // 日本語: 'フォロワー1,443人' '投稿671件' (カンマOK)
                const folJa = c.match(/フォロワー([\d,\.]+[万千KMkm]?)/);
                const fwgJa = c.match(/フォロー中([\d,\.]+[万千KMkm]?)/);
                const postJa = c.match(/投稿([\d,\.]+[万千KMkm]?)\s*件/);
                // 英語: 'X Followers'
                const folEn = c.match(/([\d,\.]+[KMkm]?)\s*Followers?/i);
                const fwgEn = c.match(/([\d,\.]+[KMkm]?)\s*Following/i);
                const postEn = c.match(/([\d,\.]+[KMkm]?)\s*Posts?/i);
                if (!out.followers && (folJa || folEn)) out.followers = parseNum((folJa || folEn)[1]);
                if (!out.following && (fwgJa || fwgEn)) out.following = parseNum((fwgJa || fwgEn)[1]);
                if (!out.posts && (postJa || postEn)) out.posts = parseNum((postJa || postEn)[1]);
                if (out.followers) break;
            }
            // === Method 2b: title attribute (IG はホバー時の正確な数値を title 属性に持つ) ===
            if (!out.followers) {
                // 要素のテキストかaria-labelに 'フォロワー' or 'followers' が含まれる近接要素を探す
                const allEls = document.querySelectorAll('[title]');
                const stats = [];
                for (const el of allEls) {
                    const t = el.getAttribute('title') || '';
                    if (/^[\d,]+$/.test(t)) {
                        const parent = el.closest('a, span, li');
                        const ctx = (parent ? parent.innerText : el.innerText) || '';
                        stats.push({ value: parseInt(t.replace(/,/g, '')), context: ctx });
                    }
                }
                // 一番目の数値を followers と仮定 (IG headerの並び: 投稿 / フォロワー / フォロー中)
                // ただし context に 'フォロワー' があれば優先
                const followerStat = stats.find(s => /フォロワー|followers?/i.test(s.context));
                if (followerStat) out.followers = followerStat.value;
            }

            // === Method 3: __NEXT_DATA__ / JSON データから ===
            if (!out.followers) {
                try {
                    const nextEl = document.getElementById('__NEXT_DATA__');
                    if (nextEl) {
                        const data = JSON.parse(nextEl.textContent || '{}');
                        const sjson = JSON.stringify(data);
                        const fol = sjson.match(/"edge_followed_by":{"count":(\d+)}/);
                        const fwg = sjson.match(/"edge_follow":{"count":(\d+)}/);
                        const post = sjson.match(/"edge_owner_to_timeline_media":{"count":(\d+)/);
                        if (fol) out.followers = parseInt(fol[1]);
                        if (fwg) out.following = parseInt(fwg[1]);
                        if (post) out.posts = parseInt(post[1]);
                    }
                } catch (e) {}
            }
            return out;
        }
    """)


def main():
    if len(sys.argv) < 2:
        print("usage: scrape_external.py <hotpepper|instagram|all>")
        sys.exit(1)
    target = sys.argv[1]
    if target not in ("hotpepper", "instagram", "all"):
        sys.exit(f"unknown target: {target}")

    targets = load_targets()
    sources = ["hotpepper", "instagram"] if target == "all" else [target]

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_str = datetime.now().strftime("%Y%m%d")
    log_dir = LOGS / f"external_{ts}"
    log_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)  # 公開ページなので headless OK
        ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="ja-JP",
                                  user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36")
        page = ctx.new_page()

        for source in sources:
            print(f"\n📅 scraping {source}")
            result = {"source": source, "scraped_at": datetime.now().isoformat(timespec="seconds"), "stores": {}}
            for store_id, urls in targets.items():
                if store_id.startswith("_"):
                    continue
                url_field = urls.get(source, "")
                # 形式: 文字列 / 文字列配列 / オブジェクト配列 [{url, category}] のいずれかをサポート
                entries = []  # [{url, category}]
                if isinstance(url_field, list):
                    for item in url_field:
                        if isinstance(item, dict) and item.get("url"):
                            entries.append({"url": item["url"].strip(), "category": item.get("category", "")})
                        elif isinstance(item, str) and item.strip():
                            entries.append({"url": item.strip(), "category": ""})
                elif isinstance(url_field, str) and url_field.strip():
                    entries.append({"url": url_field.strip(), "category": ""})
                if not entries:
                    print(f"  {store_id}: skip (URL未設定)")
                    continue
                # 1店舗で複数URL ある場合は全件 scrape
                listings = []
                for i, e in enumerate(entries):
                    url = e["url"]
                    print(f"  {store_id}[{i}] {e.get('category') or '(no cat)'}: {url}")
                    try:
                        if source == "hotpepper":
                            data = scrape_hotpepper(page, url)
                        elif source == "instagram":
                            data = scrape_instagram(page, url)
                        else:
                            data = {}
                        data["url"] = url
                        if e.get("category"):
                            data["category"] = e["category"]
                        print(f"    → rating={data.get('rating')}, reviews={data.get('review_count')}, reviews_fetched={len(data.get('recent_reviews',[]))}" if source == "hotpepper" else f"    → {data}")
                        listings.append(data)
                        page.screenshot(path=str(log_dir / f"{source}_{store_id}_{i}.png"), full_page=False)
                    except Exception as e2:
                        print(f"    ⚠️ failed: {e2}")
                        listings.append({"url": url, "category": e.get("category", ""), "error": str(e2)})
                # 後方互換: 1件なら dict, 複数なら 1件目をベース + listings 配列
                if len(listings) == 1:
                    result["stores"][store_id] = listings[0]
                else:
                    primary = dict(listings[0])  # 1件目をコピー (循環参照回避)
                    primary["listings"] = listings  # 全件 (配列)
                    primary["total_review_count"] = sum((l.get("review_count") or 0) for l in listings)
                    # ratings の単純平均 (重み付け改善余地あり)
                    rating_vals = [l.get("rating") for l in listings if l.get("rating") is not None]
                    if rating_vals:
                        primary["avg_rating"] = sum(rating_vals) / len(rating_vals)
                    result["stores"][store_id] = primary
            out_path = DATA / f"external_{source}_{date_str}.json"
            out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"  saved → {out_path.name}")

        time.sleep(1)
        browser.close()
    print("\n✅ done")


if __name__ == "__main__":
    main()
