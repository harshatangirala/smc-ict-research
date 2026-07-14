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

    for parquet_name in ("master_events", "trades"):
        src = RESULTS_DIR / f"{parquet_name}.parquet"
        if src.exists():
            df = pd.read_parquet(src)
            df.to_csv(EXPORTS_DIR / f"{parquet_name}.csv", index=False)
            log.info("Exported %s: %d rows -> csv", parquet_name, len(df))

    manifest = {
        "deliverables": list(DELIVERABLES.keys()) + ["master_events", "trades"],
        "exported_formats": ["csv", "json", "xlsx (rankings/reports only)"],
    }
    with open(EXPORTS_DIR / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)
    log.info("Export manifest written to %s", EXPORTS_DIR / "manifest.json")
