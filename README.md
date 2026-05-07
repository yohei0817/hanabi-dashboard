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

## Phase 2 残タスク

- [ ] Playwright 自動 DL (Uレジ → CSV → push)
- [ ] launchd 毎朝起動
- [ ] GitHub リポジトリ作成 + GitHub Pages 公開
- [ ] 採用管理機能 (サロン版から移植)
- [ ] パスワード認証
- [ ] 公式ロゴ画像差し替え (現状: テキストロゴ)
- [ ] FY25 月次推移データ追加 (前年同月比をより精緻に)

## 主要設計

### タブ構造

| タブ | 内容 |
|---|---|
| サマリー | 6 KPI + 状態パネル + 月次推移 + 店舗比較 + 部門別(宮古島) + 新規vsリピート店舗別donut |
| 売上・予算 | 店舗カード(綱島/宮古島 月予算進捗) + 日別推移 + 部門別予算vs実績 |
| 来客分析 | 来店種別 (店舗別) + 指名/フリー (店舗別) |
| スタッフ実績 | 店舗別 1テーブル + 並び順セレクト |
| 採用 | Phase 2 placeholder |

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
- 伝票明細CSVなし → リピート率分析等は不可

### 水野陽平の扱い

スタッフ店販購入を売上計上しているため `HIDDEN_STAFF_NAMES` に登録済。  
集計には含まれるが、ランキング・スタッフ表示からは除外される。

## 出典

- FY26 予算: `Box: 050_HANABI/010_運営本部/HABABI_FY26予実管理表.xlsx` (annual ¥113.75M)
- 前年実績: 綱島 ¥40.4M / 宮古島 ¥42.8M (FY25)
