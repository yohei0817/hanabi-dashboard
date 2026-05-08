#!/usr/bin/env python3
"""情報分析 メニュー全体を探索"""
import sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from auto_download import load_env, login

LOG = ROOT / "logs" / "explore_jouhou"
LOG.mkdir(parents=True, exist_ok=True)

env = load_env()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=False, slow_mo=300)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900}, locale="ja-JP", timezone_id="Asia/Tokyo", accept_downloads=True)
    page = ctx.new_page()
    login(page, env, LOG)

    # 情報分析メニュー探索
    print("→ click 情報分析")
    try:
        page.click("text=情報分析")
        time.sleep(1.5)
    except Exception as e:
        print(f"  warn: {e}")
    page.screenshot(path=str(LOG / "01_jouhou_menu.png"), full_page=True)

    # Save submenu items
    items = page.evaluate("""
        () => Array.from(document.querySelectorAll('button.btn-submenu, a.btn-submenu, [id^=btn_smenu]'))
            .map(b => ({id: b.id, text: b.innerText.trim(), onclick: b.getAttribute('onclick')||''}))
            .filter(x => x.text)
    """)
    (LOG / "01_jouhou_items.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  items: {len(items)}")
    for it in items:
        print(f"    [{it['id']}] {it['text'][:40]}")
        # Extract URL from onclick if present
        oc = it.get('onclick', '')
        m = oc.find("'/")
        if m >= 0:
            url_end = oc.find("'", m+1)
            print(f"      → path: {oc[m:url_end+1]}")
    time.sleep(2)
    browser.close()
