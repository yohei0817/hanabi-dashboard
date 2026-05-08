#!/usr/bin/env bash
# 毎朝の自動更新パイプライン
# launchdから呼ばれる: Uレジから最新CSV → JSON生成 → git push → GitHub Pages反映
#
# 環境: ~/hanabi-dashboard/

set -euo pipefail

ROOT="$HOME/hanabi-dashboard"
cd "$ROOT"

LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/deploy_$(date +%Y%m%d_%H%M%S).log"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG_FILE"; }
fail() { log "❌ $*"; exit 1; }

log "==== HANABI dashboard daily auto-deploy ===="

# 1. Uレジから最新CSV DL (current month)
YM=$(date +%Y%m)
log "[1/4] Uレジ自動DL ($YM)"
python3 scripts/auto_download.py "$YM" 2>&1 | tee -a "$LOG_FILE"

# 2. 月初日 (1日) なら前月の最終日も補完取得 (前月CSVが空のままにならないように)
DAY=$(date +%d)
if [ "$DAY" = "01" ]; then
  PREV_YM=$(date -v -1m +%Y%m 2>/dev/null || date -d "-1 month" +%Y%m)
  log "[1b/4] 月初なので前月($PREV_YM)も補完取得"
  python3 scripts/auto_download.py "$PREV_YM" 2>&1 | tee -a "$LOG_FILE"
fi

# 3. JSON再生成
log "[2/4] generate.py"
python3 scripts/generate.py 2>&1 | tee -a "$LOG_FILE"

# 4. 差分があればコミット&プッシュ
log "[3/4] git commit if changed"
if git diff --quiet -- data/ docs/data.json; then
  log "  no changes — skipping commit"
else
  git add data/ docs/data.json
  COMMIT_MSG="auto: refresh data $(date '+%Y-%m-%d %H:%M')"
  git -c user.email=hanabi-board@local -c user.name="HANABI Auto" commit -q -m "$COMMIT_MSG"
  log "[4/4] git push"
  git push -q origin main
  log "  ✓ pushed: $COMMIT_MSG"
fi

log "==== done ===="
