#!/usr/bin/env bash
# Full reproduction: the numbers reported in docs/manuscript.md.
#
# Requires network (downloads ~500 tickers of daily OHLCV from Yahoo Finance)
# and roughly 8 GB of RAM. Expect roughly 3 hours end to end on a modern
# laptop (add ~2 more with --with-sensitivity) -- dominated by the statistics
# stage's bootstrap over ~17.6M trades. See docs/replication_guide.md Section
# 4 for a stage-by-stage timing breakdown; that table is the source of truth
# if the two ever disagree again.
#
#   ./run_full_pipeline.sh                 # everything except sensitivity
#   ./run_full_pipeline.sh --with-sensitivity
set -euo pipefail
cd "$(dirname "$0")"

export SMC_ICT_PROFILE=final     # 10,000 bootstrap iterations
export PYTHONHASHSEED=0          # belt-and-braces; seeding does not rely on it

WITH_SENSITIVITY=0
[[ "${1:-}" == "--with-sensitivity" ]] && WITH_SENSITIVITY=1

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_HASH="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
RUN_DIR="results/runs/${STAMP}_${GIT_HASH}"
mkdir -p "$RUN_DIR"
echo "==> Run directory: $RUN_DIR"

step () {
  echo
  echo "=============================================================="
  echo "==> $1"
  echo "=============================================================="
  local t0=$SECONDS
  python main.py "$1"
  echo "==> $1 finished in $((SECONDS - t0))s"
}

step ingest
step detect
step backtest
step baseline
step statistics
step analyze
step walkforward
step costs
step montecarlo
step survivorship
[[ $WITH_SENSITIVITY -eq 1 ]] && step sensitivity
step report
step export

echo
echo "==> Generating figures"
python tools/make_figures.py

echo "==> Verifying artefacts"
python tools/check_artifacts.py

echo "==> Archiving this run to $RUN_DIR"
cp -f results/*.csv results/*.md results/*.json "$RUN_DIR"/ 2>/dev/null || true
cp -rf results/figures "$RUN_DIR"/ 2>/dev/null || true

echo
echo "Full pipeline complete."
echo "  Validation report : results/validation_report.md"
echo "  Master summary    : results/master_summary.md"
echo "  Master statistics : results/statistics_master.csv"
echo "  Archived copy     : $RUN_DIR"
