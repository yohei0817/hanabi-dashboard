#!/usr/bin/env python3
"""Uレジを Playwright で探索し、利用可能なレポート種類を調査する。

実行: python3 scripts/explore_uregi.py
出力: logs/explore_<timestamp>/ にスクリーンショット + ページ情報
"""

from __future__ import annotations

import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"
LOGS.mkdir(exist_ok=True)


def load_env() -> dict:
    env = {}
    p = ROOT / ".env"
    if not p.exists():
        sys.exit("error: .env not found")
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z_0-9]*)\s*=\s*(.*)$", line)
        if m:
            env[m.group(1)] = m.group(2)
    return env


def main():
    env = load_env()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = LOGS / f"explore_{ts}"
    out.mkdir(parents=True, exist_ok=True)
    print(f"📂 logs → {out}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=350)
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="ja-JP",
            timezone_id="Asia/Tokyo",
        )
        page = ctx.new_page()

        # 1) Login page
        print("→ open login page")
        page.goto(env["URegi_LOGIN_URL"], wait_until="networkidle")
        page.screenshot(path=str(out / "01_login.png"), full_page=True)

        # 2) Inspect form fields
        print("→ inspect login form")
        inputs = page.evaluate("""
            () => Array.from(document.querySelectorAll('input')).map(el => ({
                name: el.name, id: el.id, type: el.type,
                placeholder: el.placeholder, label: el.closest('div,td,tr,label')?.innerText?.slice(0,80) || ''
            }))
        """)
        (out / "01_login_inputs.json").write_text(__import__("json").dumps(inputs, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"  found {len(inputs)} inputs")
        for i in inputs:
            print(f"    name={i['name']!r:<30} id={i['id']!r:<25} type={i['type']!r}")

        # 3) Login (Uレジ specific: company_code / user_id / password / input[name='login'])
        page.fill("[name='company_code']", env["URegi_COMPANY"])
        page.fill("[name='user_id']", env["URegi_USER"])
        page.fill("[name='password']", env["URegi_PW"])
        page.screenshot(path=str(out / "02_login_filled.png"), full_page=True)
        print("→ click Login button")
        # Login is input[type=button][name=login]
        with page.expect_navigation(wait_until="networkidle", timeout=20000):
            page.click("[name='login']")

        # 4) Wait for post-login page
        try:
            page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass
        time.sleep(2)
        page.screenshot(path=str(out / "03_after_login.png"), full_page=True)
        print(f"→ post-login URL: {page.url}")

        # 5) Inspect navigation menu items
        nav = page.evaluate("""
            () => Array.from(document.querySelectorAll('a, button, .menu li, [role=menuitem]'))
                .map(el => ({text: (el.innerText||'').trim().slice(0,80), href: el.href || '', cls: el.className?.slice(0,80)||''}))
                .filter(x => x.text && x.text.length > 1)
        """)
        # Dedupe + filter useful items
        seen = set()
        unique_nav = []
        for n in nav:
            key = n["text"]
            if key in seen: continue
            seen.add(key)
            unique_nav.append(n)
        (out / "03_nav_items.json").write_text(__import__("json").dumps(unique_nav, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"→ {len(unique_nav)} unique nav items found")
        for n in unique_nav[:60]:
            print(f"    [{n['text'][:50]:<50}] href={n['href'][:80]}")

        # 6) Try to navigate to 帳票照会
        candidates = ["帳票照会", "帳票", "売上分析"]
        clicked = False
        for label in candidates:
            try:
                el = page.get_by_text(label, exact=False).first
                if el.count() > 0:
                    el.click()
                    print(f"→ clicked: {label}")
                    clicked = True
                    break
            except Exception as e:
                print(f"  could not click {label}: {e}")
        if clicked:
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except Exception:
                pass
            time.sleep(1.5)
            page.screenshot(path=str(out / "04_chouhyou_menu.png"), full_page=True)
            # Inspect submenu
            submenu = page.evaluate("""
                () => Array.from(document.querySelectorAll('a, button, li, [role=menuitem]'))
                    .map(el => ({text: (el.innerText||'').trim().slice(0,80), href: el.href || ''}))
                    .filter(x => x.text && x.text.length > 1 && x.text.length < 60)
            """)
            seen = set(); items = []
            for s in submenu:
                if s["text"] in seen: continue
                seen.add(s["text"]); items.append(s)
            (out / "04_chouhyou_submenu.json").write_text(__import__("json").dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"→ {len(items)} chouhyou submenu items")
            for s in items[:80]:
                print(f"    {s['text'][:60]}")

        print(f"\n✅ exploration done. Inspect: open '{out}'")
        time.sleep(2)
        browser.close()


if __name__ == "__main__":
    main()
