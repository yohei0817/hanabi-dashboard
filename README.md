# HANABI Dashboard

サロン事業部とは完全独立した HANABI グループ用ダッシュボード。  
毎朝3分で経営の全体像を把握する CEO ビュー。

## 起動

```bash
cd ~/hanabi-dashboard
python3 scripts/generate.py     # CSV → docs/data.json 集計
# プレビュー (Claude Code preview tool 経由が推奨)
python3 -m http.server 8767 --directory docs
```

ブラウザで http://localhost:8767/ → アカウント選択 (本部/店長/スタッフ)

## ファイル構成

```
~/hanabi-dashboard/
├── data/
│   ├── budgets.json                       # FY26 予算 (HABABI_FY26予実管理表.xlsx 由来)
│   ├── staff_profiles.json                # スタッフ写真メタデータ
│   ├── daily_sales_YYYYMM_<store>.csv     # 日別×店舗 (Shift-JIS)
│   └── staff_ranking_YYYYMM_<store>.csv   # 月別×店舗×スタッフ (Shift-JIS)
├── scripts/
│   └── generate.py                        # CSV → JSON 集計
└── docs/
    ├── index.html                         # ダッシュボード本体
    ├── data.json                          # generate.py の出力
    └── assets/staff/                      # スタッフ写真置き場
```

## 店舗ID

- `tsunashima` = Hanabi綱島店 (ヘア専門)
- `miyakojima` = ELLE by Hanabi 宮古島店 (ヘア / アイ / ネイル)

## 月次運用

1. Uレジで4ファイル DL:
   - 売上実績 (日別×店舗) × 2店舗
   - スタッフ別売上実績 (月別×店舗×スタッフ) × 2店舗
2. ファイル名を規約に合わせて `data/` に配置
   - `daily_sales_YYYYMM_<store>.csv`
   - `staff_ranking_YYYYMM_<store>.csv`
3. `python3 scripts/generate.py` 実行
4. プレビューで確認

## 完了タスク

- [x] Playwright 自動 DL (Uレジ → CSV → push) `scripts/auto_download.py`
- [x] launchd 毎朝 8:15 JST 自動デプロイ `scripts/com.hanabi-board.daily.plist`
- [x] GitHub リポジトリ + GitHub Pages 公開 `https://hanabi-board.github.io/hanabi-dashboard/`
- [x] パスワード認証 (本部/管理者, SHA-256, 24h session)
- [x] 採用管理機能 (本部のみ候補者追加・編集・削除モーダル + JSON出力)
- [x] FY22-25 全月バックフィル `scripts/backfill.py YYYYMM YYYYMM`
- [x] メニュー別実績スクレイプ `scripts/scrape_menu.py FY22 / FY25_MONTHLY` 等
- [x] 異常検知アラートパネル (サマリータブ上部)
- [x] 印刷ビュー (A4 1枚 サマリーレポート)

## 残タスク

- [ ] 伝票明細スクレイプ (取引粒度でリピート率分析)
- [ ] FY22-24 メニュー別データ取得 (scrape_menu.py で `FY22`, `FY23`, `FY24` を実行)
- [ ] 情報分析の他レポート (失客 / 年代別 / 曜日別 / Zチャート)
- [ ] 男女別売上の時系列チャート

## 主要設計

### タブ構造

| タブ | 内容 |
|---|---|
| サマリー | 6 KPI + 異常検知アラート + 状態パネル + 月次推移 + 店舗比較 + 部門別(宮古島) + 新規vsリピート店舗別donut |
| 売上・予算 | 店舗カード(綱島/宮古島 月予算進捗) + 日別推移 + 部門別予算vs実績 |
| 来客分析 | 来店種別 + 指名・フリー + 男女別 + 月次推移チャート4種 (客数/リピート率/客単価/指名率) |
| スタッフ実績 | 店舗別 1テーブル + 並び順セレクト |
| メニュー別実績 | 期間/並び/検索フィルタ + 5スコープ展開 |
| 年度レポート | 任意のFYペアで通年比較 (FY22から) + 月次重ねチャート + 部門別 + メニューTOP10 |
| 採用 | KPI + ファネル + ソース + 候補者リスト (本部は追加・編集・削除可) |

### 達成率の表記ルール

- **月達成率**: 当月実績 / 月予算 (期末判断用)
- **ペース達成率**: 当月実績 / (月予算 × 経過日数/月日数) ← 月途中の判断はこちら
- **前年同月比** (ペース調整): 当月実績 / (FY25月平均 × 経過日数/月日数)
- バッジ色: 緑≥100% / 黄80-99% / 赤<80%

### 部門色 (確定)

- ヘア = ピンク `#E91E63`
- アイ = ブルー `#1E88E5`
- ネイル = イエロー `#F59E0B`

### データ制約

- 部門別の新規/リピート区分は取れない (日別CSVは店舗単位までで部門breakdownなし)
- 代替: 部門別 客数+客単価+指名率+構成比 を staff_ranking 集計から表示
- 伝票明細CSVなし → リピート率分析等は不可 (Playwright scrape は技術的に可能、未実装)
- ELLE 宮古島店は 2025/9 OPEN のため FY25 の前半 (5月-8月) はデータなし。 同店舗 YoY 比較で除外

### 水野陽平の扱い

スタッフ店販購入を売上計上しているため `HIDDEN_STAFF_NAMES` に登録済。  
集計には含まれるが、ランキング・スタッフ表示からは除外される。

## 出典

- FY26 予算: `Box: 050_HANABI/010_運営本部/HABABI_FY26予実管理表.xlsx` (annual ¥113.75M)
- 前年実績: 綱島 ¥40.4M / 宮古島 ¥42.8M (FY25)
