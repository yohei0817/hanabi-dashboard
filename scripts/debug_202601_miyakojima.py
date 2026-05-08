#!/usr/bin/env python3
"""202601/miyakojima/uriage が DL できない原因を調査"""
import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from auto_download import load_env, login

LOG = ROOT / "logs" / "debug_202601"
LOG.mkdir(parents=True, exist_ok=True)

env = load_env()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ja-JP", timezone_id="Asia/Tokyo", accept_downloads=True)
    page = ctx.new_page()
    login(page, env, LOG)
    page.goto("https://owner-beauty.u-regi.com/sales_results/C_sales_results/sales_results_list", wait_until="networkidle")
    time.sleep(2)
    # Configure: 202601 + 002
    page.select_option("#search_year", "2026")
    page.select_option("#search_month", "01")
    page.evaluate("""
        () => {
            document.querySelectorAll("input[type=checkbox][id^='store_search_check_']").forEach(cb => {
                cb.checked = (cb.value === '002');
            });
        }
    """)
    page.check("#tax_excluded")
    time.sleep(1)
    page.screenshot(path=str(LOG / "before_search.png"), full_page=True)
    page.evaluate("reload_data(false)")
    print("waiting for response...")
    time.sleep(8)  # Long wait
    page.screenshot(path=str(LOG / "after_search.png"), full_page=True)
    # Look for ANY data and any download icons
    info = page.evaluate("""
        () => ({
            url: location.href,
            disk_icon: document.querySelectorAll('.ui-icon-disk').length,
            doc_icon: document.querySelectorAll('.ui-icon-document').length,
            grid_rows: document.querySelectorAll('#salesList tbody tr').length,
            grid_visible: !!document.querySelector('#salesList'),
            error_text: (document.querySelector('.error,.alert,.message') || {}).innerText || '',
            page_title: document.title,
        })
    """)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    print("\nlook at logs/debug_202601/after_search.png")
    # Try clicking the disk icon
    print("trying disk click + download...")
    try:
        with page.expect_download(timeout=30000) as dl_info:
            page.click(".ui-icon-disk", force=True)
        d = dl_info.value
        out = ROOT / "data" / "daily_sales_202601_miyakojima.csv"
        d.save_as(str(out))
        print(f"  ✓ saved: {out}")
    except Exception as e:
        print(f"  ✗ {e}")
        # check for any modal/dialog appearing
        time.sleep(2)
        page.screenshot(path=str(LOG / "after_click.png"), full_page=True)
        # Inspect modal/dialog
        modal = page.evaluate("""
            () => {
                const dialogs = document.querySelectorAll('.modal, .dialog, [role=dialog], .ui-dialog');
                return Array.from(dialogs).map(d => ({
                    visible: d.offsetWidth > 0 && d.offsetHeight > 0,
                    text: d.innerText.slice(0, 200),
                }));
            }
        """)
        print(f"  modals/dialogs: {json.dumps(modal, ensure_ascii=False)}")
    time.sleep(3)
    browser.close()
