"""Refresh data/raw/sp500_wikipedia_snapshot.csv from Wikipedia.

Deliberately a separate, manual step. The pipeline reads the committed snapshot
and never fetches, so a rerun cannot silently pick up a different index
composition and change the results.

    python tools/refresh_universe.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from utils.universe import estimate_missing_members, fetch_snapshot, save_snapshot


def main() -> int:
    df = fetch_snapshot()
    save_snapshot(df)
    print(f"{len(df)} constituents; {df['gics_sector'].nunique()} GICS sectors")
    print(f"entry dates known for {df['date_added'].notna().sum()}")
    print()
    for k, v in estimate_missing_members().items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
