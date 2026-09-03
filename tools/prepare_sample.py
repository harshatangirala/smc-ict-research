"""Populate data/cache from the committed sample bundle.

CI and the fast-validation path must not depend on a live Yahoo Finance call:
the API rate-limits, occasionally returns empty frames, and five constituents
are permanently unavailable. `data/bundle/prices/` holds a committed 50-ticker
sample so `pytest` and a trimmed `main.py all` run hermetically.

    python tools/prepare_sample.py            # all bundled tickers
    python tools/prepare_sample.py --limit 12 # a smaller, faster subset
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE = ROOT / "data" / "bundle" / "prices"
CACHE = ROOT / "data" / "cache"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0, help="use only the first N tickers")
    ap.add_argument("--force", action="store_true", help="overwrite existing cache files")
    args = ap.parse_args()

    if not BUNDLE.exists():
        print(f"ERROR: sample bundle missing at {BUNDLE}", file=sys.stderr)
        return 1

    CACHE.mkdir(parents=True, exist_ok=True)
    files = sorted(BUNDLE.glob("*.parquet"))
    if args.limit:
        files = files[: args.limit]

    copied = 0
    for f in files:
        dest = CACHE / f.name
        if dest.exists() and not args.force:
            continue
        shutil.copy2(f, dest)
        copied += 1

    print(f"Sample cache ready: {len(files)} tickers available, {copied} copied -> {CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
