#!/usr/bin/env python3
"""伝票明細 (取引明細) のCSV出力可否を調査"""
import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from auto_download import load_env, login

LOG = ROOT / "logs" / "explore_denpyo"
LOG.mkdir(parents=True, exist_ok=True)

env = load_env()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ja-JP", timezone_id="Asia/Tokyo", accept_downloads=True)
    page = ctx.new_page()
    login(page, env, LOG)

    # 売上管理 → 伝票明細 への通常パスを試す
    print("→ click 売上管理")
    try:
        page.click("text=売上管理")
        time.sleep(1.5)
    except Exception as e:
        print(f"  warn: {e}")
    page.screenshot(path=str(LOG / "01_uriage_kanri.png"), full_page=True)

    print("→ click 伝票明細")
    try:
        page.click("text=伝票明細", timeout=5000)
    except Exception as e:
        print(f"  fallback: {e}")
        # try direct URL guesses
        for url in [
            "https://owner-beauty.u-regi.com/sales_manage/c_sales_manage/denpyo_meisai",
            "https://owner-beauty.u-regi.com/denpyo_meisai/c_denpyo_meisai/index",
            "https://owner-beauty.u-regi.com/uriage_manage/c_uriage_manage/denpyo_meisai",
        ]:
            print(f"  try: {url}")
            try:
                page.goto(url, timeout=10000)
                if page.locator("text=伝票").count() > 0:
                    print(f"  ✓ found at {url}")
                    break
            except Exception:
                pass
    time.sleep(3)
    page.screenshot(path=str(LOG / "02_denpyo_page.png"), full_page=True)
    (LOG / "02_denpyo_page.html").write_text(page.content(), encoding="utf-8")
    print(f"  URL: {page.url}")

    # Inspect form/buttons
    info = page.evaluate("""
        () => ({
            url: location.href,
            title: document.title,
            disk_icon: document.querySelectorAll('.ui-icon-disk').length,
            doc_icon: document.querySelectorAll('.ui-icon-document').length,
            csv_buttons: Array.from(document.querySelectorAll('button, a')).filter(b => /csv|出力|ダウンロード|ＣＳＶ/i.test(b.innerText || '')).map(b => ({text: b.innerText, id: b.id, cls: b.className})),
            search_form: !!document.querySelector('form, [class*=search]'),
            grid: !!document.querySelector('table, .grid, .jqgrid, #salesList, #denpyo'),
            search_btn: Array.from(document.querySelectorAll('button')).filter(b => /検索/i.test(b.innerText || '')).map(b => ({text: b.innerText, id: b.id})),
        })
    """)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    time.sleep(2)
    browser.close()
