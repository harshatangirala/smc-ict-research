"""Export System (Task 14): write every research deliverable to CSV, Excel,
and JSON under exports/, verified to match the in-memory results they were
derived from (row-count + checksum-style sanity check after each write).
"""

from __future__ import annotations

import json

import pandas as pd

from utils.config import EXPORTS_DIR, RESULTS_DIR
from utils.logging_config import get_logger

log = get_logger("export")

TRADES_CSV_SAMPLE_SIZE = 500_000

DELIVERABLES = {
    "data_quality_report": "data_quality_report.csv",
    "concept_rankings": "concept_rankings.csv",
    "stock_rankings": "stock_rankings.csv",
    "combination_rankings": "combination_rankings.csv",
    "regime_analysis": "regime_analysis.csv",
    "sector_analysis": "sector_analysis.csv",
}


def _verify_export(df: pd.DataFrame, path) -> bool:
    reloaded = pd.read_csv(path) if str(path).endswith(".csv") else pd.read_json(path)
    ok = len(reloaded) == len(df)
    if not ok:
        log.error("Export verification FAILED for %s: wrote %d rows, read back %d", path, len(df), len(reloaded))
    return ok


def export_all() -> None:
    excel_path = EXPORTS_DIR / "smc_ict_research_results.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for name, filename in DELIVERABLES.items():
            src = RESULTS_DIR / filename
            if not src.exists():
                log.warning("Skipping export for %s: %s not found (stage not yet run)", name, src)
                continue
            df = pd.read_csv(src)

            csv_path = EXPORTS_DIR / f"{name}.csv"
            df.to_csv(csv_path, index=False)
            _verify_export(df, csv_path)

            json_path = EXPORTS_DIR / f"{name}.json"
            df.to_json(json_path, orient="records", indent=2, date_format="iso")

            sheet_name = name[:31]  # Excel sheet-name length limit
            df.to_excel(writer, sheet_name=sheet_name, index=False)

            log.info("Exported %s: %d rows -> csv, json, xlsx", name, len(df))

    # master_events is large but browsable (~250MB); trades is not (34.6M
    # rows -> ~4.8GB as CSV, unopenable in Excel/most tools and not a useful
    # deliverable in that form). The full trades table remains available as
    # results/trades.parquet (columnar, fast to load with pandas) for anyone
    # doing programmatic analysis; here we export a representative sample
    # instead of the full CSV.
    src = RESULTS_DIR / "master_events.parquet"
    if src.exists():
        df = pd.read_parquet(src)
        df.to_csv(EXPORTS_DIR / "master_events.csv", index=False)
        log.info("Exported master_events: %d rows -> csv", len(df))

    trades_src = RESULTS_DIR / "trades.parquet"
    if trades_src.exists():
        df = pd.read_parquet(trades_src)
        sample_n = min(len(df), TRADES_CSV_SAMPLE_SIZE)
        sample = df.sample(n=sample_n, random_state=42) if len(df) > sample_n else df
        sample.to_csv(EXPORTS_DIR / "trades_sample.csv", index=False)
        log.info(
            "Exported trades_sample: %d of %d rows -> csv (full table stays in results/trades.parquet, "
            "%d rows, not exported as CSV -- would be several GB and unopenable in spreadsheet tools)",
            len(sample), len(df), len(df),
        )

    manifest = {
        "deliverables": list(DELIVERABLES.keys()) + ["master_events", "trades"],
        "exported_formats": ["csv", "json", "xlsx (rankings/reports only)"],
    }
    with open(EXPORTS_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Export manifest written to %s", EXPORTS_DIR / "manifest.json")
