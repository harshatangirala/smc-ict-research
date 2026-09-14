#!/usr/bin/env bash
# Fast validation: hermetic, ~2-4 minutes, no network.
#
# Runs the whole pipeline over the committed 12-ticker sample with the reduced
# bootstrap budget. Use this to check that a change did not break the pipeline;
# use run_full_pipeline.sh for numbers you intend to publish.
set -euo pipefail
cd "$(dirname "$0")"

export SMC_ICT_PROFILE=fast
export PYTHONHASHSEED=0

echo "==> Preparing hermetic sample cache (12 tickers)"
python tools/prepare_sample.py --limit 12

echo "==> Running test suite"
pytest tests/ -q

echo "==> Running pipeline (ingest skipped: sample cache is pre-populated)"
python main.py all --skip ingest

echo "==> Checking artefacts"
python tools/check_artifacts.py

echo
echo "Fast validation complete. See results/validation_report.md"
