"""One-off helper: rebuild the data quality report from cached parquet files
without re-downloading (used after validator logic changes)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from utils.config import DATA_CACHE_DIR, RESULTS_DIR
from utils.data_quality import build_data_quality_report

if __name__ == "__main__":
    data = {}
    for f in Path(DATA_CACHE_DIR).glob("*.parquet"):
        data[f.stem] = pd.read_parquet(f)
    report = build_data_quality_report(data)
    report.to_csv(RESULTS_DIR / "data_quality_report.csv", index=False)
    print(report["status"].value_counts())
    print("tickers with 0 rows:", (report["rows"] == 0).sum())
    print("median coverage_ratio:", report["coverage_ratio"].median())
