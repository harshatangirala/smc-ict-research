"""CLI entry point for the SMC/ICT research pipeline.

Usage:
    python main.py ingest              # download + cache + validate OHLCV
    python main.py detect              # run event detection engine
    python main.py backtest            # run forward-return backtests
    python main.py analyze             # rankings, combinations, regimes, sectors
    python main.py export              # write CSV/Excel/JSON deliverables
    python main.py all                 # run every stage in order
"""

from __future__ import annotations

import argparse
import sys
import time

from utils.config import RESULTS_DIR
from utils.logging_config import get_logger

log = get_logger("main")


def stage_ingest() -> None:
    from utils.data_loader import download_universe, load_constituents
    from utils.data_quality import build_data_quality_report

    constituents = load_constituents()
    tickers = constituents["YFSymbol"].tolist()
    log.info("Starting ingestion for %d tickers", len(tickers))

    t0 = time.time()
    price_data = download_universe(tickers, max_workers=8)
    log.info("Ingestion finished in %.1fs, %d/%d tickers with data",
              time.time() - t0, len(price_data), len(tickers))

    report = build_data_quality_report(price_data)
    report_path = RESULTS_DIR / "data_quality_report.csv"
    report.to_csv(report_path, index=False)
    log.info("Data quality report written to %s", report_path)


def stage_detect() -> None:
    from signals.event_engine import build_master_events

    events = build_master_events()
    path = RESULTS_DIR / "master_events.parquet"
    events.to_parquet(path)
    log.info("Master event table written to %s (%d rows)", path, len(events))


def stage_backtest() -> None:
    from backtest.engine import run_backtest

    trades = run_backtest()
    path = RESULTS_DIR / "trades.parquet"
    trades.to_parquet(path)
    log.info("Backtest trade table written to %s (%d rows)", path, len(trades))


def stage_analyze() -> None:
    from analytics.concept_ranking import rank_concepts
    from analytics.stock_ranking import rank_stocks
    from analytics.combinations import rank_combinations
    from analytics.regimes import regime_analysis
    from analytics.sectors import sector_analysis

    rank_concepts().to_csv(RESULTS_DIR / "concept_rankings.csv", index=False)
    rank_stocks().to_csv(RESULTS_DIR / "stock_rankings.csv", index=False)
    rank_combinations().to_csv(RESULTS_DIR / "combination_rankings.csv", index=False)
    regime_analysis().to_csv(RESULTS_DIR / "regime_analysis.csv", index=False)
    sector_analysis().to_csv(RESULTS_DIR / "sector_analysis.csv", index=False)
    log.info("Analytics stage complete")


def stage_export() -> None:
    from utils.export import export_all

    export_all()
    log.info("Export stage complete")


STAGES = {
    "ingest": stage_ingest,
    "detect": stage_detect,
    "backtest": stage_backtest,
    "analyze": stage_analyze,
    "export": stage_export,
}


def main() -> None:
    parser = argparse.ArgumentParser(description="SMC/ICT research pipeline")
    parser.add_argument("stage", choices=list(STAGES) + ["all"])
    args = parser.parse_args()

    if args.stage == "all":
        for name, fn in STAGES.items():
            log.info("=== Stage: %s ===", name)
            fn()
    else:
        STAGES[args.stage]()


if __name__ == "__main__":
    sys.exit(main())
