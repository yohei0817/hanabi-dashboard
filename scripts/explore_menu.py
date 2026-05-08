#!/usr/bin/env python3
"""技術の実績 (メニュー別) を直接探索 - CSV取得可否"""
import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from auto_download import load_env, login

LOG = ROOT / "logs" / "explore_menu"
LOG.mkdir(parents=True, exist_ok=True)

env = load_env()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=200)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ja-JP", timezone_id="Asia/Tokyo", accept_downloads=True)
    page = ctx.new_page()
    login(page, env, LOG)

    page.goto("https://owner-beauty.u-regi.com/tech_sales_result/c_tech_sales_result/view", wait_until="networkidle")
    time.sleep(2)
    page.screenshot(path=str(LOG / "01_tech_form.png"), full_page=True)
    (LOG / "01_tech_form.html").write_text(page.content(), encoding="utf-8")

    # Switch to 期間指定 tab + select 5月 range
    try:
        page.click("text=期間指定")
        time.sleep(1)
    except Exception as e:
        print(f"  period tab: {e}")
    # Find date inputs and set 2026/05/01 - 2026/05/31
    page.evaluate("""
        () => {
            const dateInputs = document.querySelectorAll('input.datepicker, input[type=number][maxlength=\"8\"], input[id*=\"date_from\"], input[id*=\"date_to\"]');
            console.log('date inputs:', dateInputs.length);
            if (dateInputs.length >= 2) {
                dateInputs[0].value = '20260501';
                dateInputs[1].value = '20260531';
            }
        }
    """)
    page.screenshot(path=str(LOG / "01a_period_selected.png"), full_page=True)
    try:
        page.click("button:has-text('表示')", force=True)
        time.sleep(8)
    except Exception as e:
        print(f"  display click: {e}")

    page.screenshot(path=str(LOG / "02_tech_results.png"), full_page=True)
    info = page.evaluate("""
        () => ({
            url: location.href,
            title: document.title,
            disk_icon: document.querySelectorAll('.ui-icon-disk').length,
            doc_icon: document.querySelectorAll('.ui-icon-document').length,
            grid_rows: document.querySelectorAll('table tbody tr').length,
            page_text: document.body.innerText.slice(0, 600),
        })
    """)
    print(json.dumps(info, ensure_ascii=False, indent=2))
    time.sleep(2)
    browser.close()
