#!/usr/bin/env bash
# Daily GoldenRatios update: GSR history, market ratios, GSR chart.
# Soft-fail: each step runs even if a prior step fails; exit code is last failure.
#
# Cron example (weekday evenings, after data is usually available):
#   30 17 * * 1-5 /home/james/myPrograms/KSI/GoldenRatios/run_daily.sh
#
# Override data dir:
#   GSR_DATA_DIR=/path/to/data MARKET_RATIOS_DIR=/path/to/data ./run_daily.sh

set -u
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PY="$(command -v python3)"
else
  echo "ERROR: no python3 found" >&2
  exit 1
fi

export GSR_DATA_DIR="${GSR_DATA_DIR:-$ROOT}"
export MARKET_RATIOS_DIR="${MARKET_RATIOS_DIR:-$GSR_DATA_DIR}"
LOG_DIR="${GSR_DATA_DIR}/logs"
mkdir -p "$LOG_DIR"
MAIN_LOG="$LOG_DIR/run_daily.log"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$MAIN_LOG"; }

log "=== GoldenRatios daily run (python=$PY) ==="
rc=0

log "--- gsr_data_collector ---"
if ! "$PY" "$ROOT/gsr_data_collector.py" >>"$LOG_DIR/gsr_collector.log" 2>&1; then
  log "WARN: gsr_data_collector failed (exit $?)"
  rc=1
fi

log "--- market_ratios_collector ---"
if ! "$PY" "$ROOT/market_ratios_collector.py" >>"$LOG_DIR/market_ratios.log" 2>&1; then
  log "WARN: market_ratios_collector failed (exit $?)"
  rc=1
fi

log "--- update_gsr_chart ---"
if ! "$PY" "$ROOT/update_gsr_chart.py" >>"$LOG_DIR/gsr_collector.log" 2>&1; then
  log "WARN: update_gsr_chart failed (exit $?)"
  rc=1
fi

log "=== done (rc=$rc) ==="
exit "$rc"
