"""CLI entry point for the SMC/ICT research pipeline.

Stages, in dependency order::

    python main.py ingest        # download + cache + validate OHLCV
    python main.py detect        # run the event detection engine
    python main.py backtest      # forward returns at 8 horizons, no look-ahead
    python main.py baseline      # benchmark strategies through the same engine
    python main.py statistics    # results/statistics_master.csv (BH-FDR family)
    python main.py analyze       # concept/stock/combination/sector/regime tables
    python main.py walkforward   # rolling out-of-sample evaluation
    python main.py costs         # transaction-cost-aware restatement
    python main.py montecarlo    # resampling evidence for the headline concepts
    python main.py sensitivity   # parameter sweeps (subsample; slow)
    python main.py report        # validation report + master summary
    python main.py export        # CSV/Excel/JSON deliverables
    python main.py all           # every stage above, in order

``SMC_ICT_PROFILE=fast`` lowers the bootstrap budget from 10,000 to 5,000 and
is what CI uses; the published numbers come from the default ``final`` profile.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time

from utils.config import PROFILE, RESULTS_DIR
from utils.logging_config import get_logger

log = get_logger("main")


def _git_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _write_run_manifest() -> None:
    """Stamp every run with its git hash, profile and timestamp."""
    import json
    from datetime import datetime, timezone

    from utils.config import BOOTSTRAP_ITERATIONS, FDR_ALPHA, RANDOM_SEED
    from utils.rng import write_seed_manifest

    manifest = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "git_hash": _git_hash(),
        "profile": PROFILE,
        "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
        "fdr_alpha": FDR_ALPHA,
        "random_seed": RANDOM_SEED,
        "python": sys.version.split()[0],
    }
    (RESULTS_DIR / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    write_seed_manifest(extra={"git_hash": manifest["git_hash"], "profile": PROFILE})
    log.info("Run manifest: git=%s profile=%s", manifest["git_hash"], PROFILE)


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


def stage_baseline() -> None:
    """Detect and backtest the benchmark strategies through the identical engine."""
    from backtest.baseline_engine import build_baseline_events
    from backtest.engine import run_backtest

    events = build_baseline_events()
    events.to_parquet(RESULTS_DIR / "baseline_events.parquet")
    trades = run_backtest(events)
    path = RESULTS_DIR / "baseline_trades.parquet"
    trades.to_parquet(path)
    log.info("Baseline trade table written to %s (%d rows)", path, len(trades))


def stage_statistics() -> None:
    import pandas as pd

    from analytics.master_stats import build_statistics_master, write_statistics_master

    trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    master = build_statistics_master(trades)
    write_statistics_master(master)


def stage_analyze() -> None:
    import pandas as pd

    from analytics.combinations import rank_combinations
    from analytics.concept_ranking import rank_concepts, rank_concepts_all_horizons
    from analytics.regimes import regime_analysis
    from analytics.sectors import sector_analysis
    from analytics.stock_ranking import rank_stocks

    log.info("Loading trades.parquet once for the whole analyze stage")
    trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")

    rank_concepts(trades).to_csv(RESULTS_DIR / "concept_rankings.csv", index=False)
    rank_concepts_all_horizons(trades).to_csv(
        RESULTS_DIR / "concept_rankings_all_horizons.csv", index=False
    )
    log.info("Concept rankings written")
    rank_stocks(trades).to_csv(RESULTS_DIR / "stock_rankings.csv", index=False)
    log.info("Stock rankings written")
    rank_combinations().to_csv(RESULTS_DIR / "combination_rankings.csv", index=False)
    log.info("Combination rankings written")
    regime_analysis(trades).to_csv(RESULTS_DIR / "regime_analysis.csv", index=False)
    log.info("Regime analysis written")
    sector_analysis(trades).to_csv(RESULTS_DIR / "sector_analysis.csv", index=False)
    log.info("Analytics stage complete")


def stage_walkforward() -> None:
    import pandas as pd

    from analytics.walkforward import walk_forward_analysis

    trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    detail, summary = walk_forward_analysis(trades)
    detail.to_csv(RESULTS_DIR / "walkforward_detail.csv", index=False)
    summary.to_csv(RESULTS_DIR / "walkforward_summary.csv", index=False)
    log.info("Walk-forward written (%d folds)", len(summary))


def stage_costs() -> None:
    import pandas as pd

    from backtest.engine_tc import apply_costs, breakeven_cost_bps, sweep_cost_grid
    from utils.config import PRIMARY_HOLDING_PERIOD

    trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    sub = trades[trades["holding_period"] == PRIMARY_HOLDING_PERIOD]
    net = apply_costs(sub)
    (
        net.groupby("signal")
        .agg(
            n_trades=("net_return", "size"),
            gross_mean=("fwd_return", "mean"),
            mean_cost_bps=("cost_bps", "mean"),
            net_mean=("net_return", "mean"),
            net_win_rate=("net_return", lambda s: float((s > 0).mean())),
        )
        .reset_index()
        .sort_values("net_mean", ascending=False)
        .to_csv(RESULTS_DIR / "net_of_cost_rankings.csv", index=False)
    )
    # Break-even is reported against BOTH the gross mean and the excess over
    # the matched-random null; only the latter says whether the signal itself
    # pays for its own trading costs.
    excess_map = None
    master_path = RESULTS_DIR / "statistics_master.csv"
    if master_path.exists():
        mm = pd.read_csv(master_path)
        mm = mm[mm["holding_period"] == PRIMARY_HOLDING_PERIOD]
        excess_map = dict(zip(mm["signal"], mm["excess_return_vs_matched_random"]))
    breakeven_cost_bps(sub, excess_by_signal=excess_map).to_csv(
        RESULTS_DIR / "breakeven_costs.csv", index=False
    )
    sweep_cost_grid(sub).to_csv(RESULTS_DIR / "cost_sensitivity_grid.csv", index=False)
    log.info("Transaction-cost tables written")


def stage_montecarlo() -> None:
    import pandas as pd

    from analytics.montecarlo import monte_carlo_block_bootstrap, monte_carlo_matched_null
    from backtest.engine import _load_price_cache
    from utils.config import MONTE_CARLO_RUNS, PRIMARY_HOLDING_PERIOD

    trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    sub = trades[trades["holding_period"] == PRIMARY_HOLDING_PERIOD]
    prices = {t: df.set_index("date") for t, df in _load_price_cache().items()}

    master_path = RESULTS_DIR / "statistics_master.csv"
    if master_path.exists():
        master = pd.read_csv(master_path)
        master = master[master["holding_period"] == PRIMARY_HOLDING_PERIOD]
        signals = (
            master.nlargest(10, "excess_return_vs_matched_random")["signal"].tolist()
            + master.nsmallest(5, "excess_return_vs_matched_random")["signal"].tolist()
        )
    else:
        signals = sorted(sub["signal"].unique())[:12]

    rows = []
    for sig in signals:
        grp = sub[sub["signal"] == sig]
        if grp.empty:
            continue
        counts = grp.groupby("ticker").size().to_dict()
        direction = int(grp["direction"].iloc[0])
        observed = float(grp["fwd_return"].mean())
        mc = monte_carlo_matched_null(
            counts, prices, PRIMARY_HOLDING_PERIOD, direction, observed,
            n_runs=MONTE_CARLO_RUNS, label=f"mc:{sig}",
        )
        blk = monte_carlo_block_bootstrap(
            prices, counts, PRIMARY_HOLDING_PERIOD, direction, observed,
            n_runs=MONTE_CARLO_RUNS, label=f"blk:{sig}",
        )
        rows.append(
            {
                "signal": sig, "n_trades": len(grp), "observed_mean": observed,
                "mc_null_mean": mc["null_mean"], "mc_p_value": mc["p_value"],
                "block_null_mean": blk["null_mean"], "block_p_value": blk["p_value"],
                "n_runs": MONTE_CARLO_RUNS,
            }
        )
        log.info("Monte Carlo done for %s (p=%.4f)", sig, mc["p_value"])
    pd.DataFrame(rows).to_csv(RESULTS_DIR / "monte_carlo.csv", index=False)
    log.info("Monte Carlo table written")


def stage_sensitivity() -> None:
    from analytics.sensitivity import grid_sweep, random_sweep, stability_summary

    grid = grid_sweep(
        {"ict.ob_swing_len": [5, 10, 15, 20], "ict.mss_pivot_len": [3, 5, 7, 10]},
        n_tickers=30,
    )
    grid.to_csv(RESULTS_DIR / "sensitivity_grid.csv", index=False)
    stability_summary(grid).to_csv(RESULTS_DIR / "sensitivity_stability.csv", index=False)

    rand = random_sweep(
        ["ict.ob_swing_len", "ict.mss_pivot_len", "ict.displacement_perc_body",
         "ict.sweep_penetration_atr", "smc.swing_len", "smc.internal_len"],
        n_draws=16, n_tickers=30,
    )
    rand.to_csv(RESULTS_DIR / "sensitivity_random.csv", index=False)
    log.info("Sensitivity tables written")


def stage_report() -> None:
    from utils.validation_report import build_validation_report
    from utils.master_summary import build_master_summary

    build_validation_report()
    build_master_summary()
    log.info("Reports written")


def stage_export() -> None:
    from utils.export import export_all

    export_all()
    log.info("Export stage complete")


STAGES = {
    "ingest": stage_ingest,
    "detect": stage_detect,
    "backtest": stage_backtest,
    "baseline": stage_baseline,
    "statistics": stage_statistics,
    "analyze": stage_analyze,
    "walkforward": stage_walkforward,
    "costs": stage_costs,
    "montecarlo": stage_montecarlo,
    "sensitivity": stage_sensitivity,
    "report": stage_report,
    "export": stage_export,
}

#: `all` deliberately excludes `sensitivity`, which re-runs detection over a
#: parameter grid and dominates total runtime. Run it explicitly.
ALL_STAGES = [s for s in STAGES if s != "sensitivity"]


def main() -> None:
    parser = argparse.ArgumentParser(description="SMC/ICT research pipeline")
    parser.add_argument("stage", choices=list(STAGES) + ["all"])
    parser.add_argument(
        "--skip", nargs="*", default=[],
        help="stage names to skip when running 'all' (e.g. --skip ingest detect)",
    )
    args = parser.parse_args()

    _write_run_manifest()

    if args.stage == "all":
        for name in ALL_STAGES:
            if name in args.skip:
                log.info("=== Stage: %s (skipped) ===", name)
                continue
            log.info("=== Stage: %s ===", name)
            t0 = time.time()
            STAGES[name]()
            log.info("=== Stage %s finished in %.1fs ===", name, time.time() - t0)
    else:
        STAGES[args.stage]()


if __name__ == "__main__":
    sys.exit(main())
