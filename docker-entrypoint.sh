#!/usr/bin/env bash
# Dispatch for the container's three modes.
set -euo pipefail

case "${1:-fast}" in
  test)
    exec pytest tests/ -v
    ;;
  fast)
    exec ./run_fast_validation.sh
    ;;
  full)
    exec ./run_full_pipeline.sh
    ;;
  shell)
    exec /bin/bash
    ;;
  *)
    # Anything else is passed through, e.g. `docker run ... python main.py detect`
    exec "$@"
    ;;
esac
