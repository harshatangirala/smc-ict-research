"""One-off audit: flag any cached ticker whose history doesn't start near
DATA_START, which would indicate a stale/partial cache file."""

from pathlib import Path

import pandas as pd

from utils.config import DATA_CACHE_DIR, DATA_START

if __name__ == "__main__":
    start = pd.Timestamp(DATA_START)
    suspects = []
    for f in Path(DATA_CACHE_DIR).glob("*.parquet"):
        df = pd.read_parquet(f)
        if df.empty or (df.index.min() - start).days > 400:
            suspects.append((f.stem, len(df), df.index.min() if not df.empty else None))
    print(f"{len(suspects)} suspect cache files:")
    for s in suspects:
        print(s)
