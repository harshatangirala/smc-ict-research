"""Assert that a pipeline run produced the artefacts the acceptance criteria name.

Exits non-zero with a specific message on the first failure, so a CI log points
at what is missing rather than at a generic traceback.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"

#: path -> minimum row count (0 = existence only)
REQUIRED: dict[str, int] = {
    "master_events.parquet": 100,
    "trades.parquet": 500,
    "baseline_trades.parquet": 100,
    "statistics_master.csv": 8,
    "concept_rankings.csv": 5,
    "stock_rankings.csv": 1,
    "sector_analysis.csv": 1,
    "regime_analysis.csv": 1,
    "walkforward_summary.csv": 0,
    "net_of_cost_rankings.csv": 1,
    "breakeven_costs.csv": 1,
    "monte_carlo.csv": 0,
    "validation_report.md": 0,
    "master_summary.md": 0,
    "run_manifest.json": 0,
    "seed.txt": 0,
}

#: columns statistics_master.csv must carry for the paper's claims to be checkable
REQUIRED_COLUMNS = [
    "signal", "holding_period", "n_trades", "avg_return", "win_rate",
    "excess_return_vs_matched_random", "p_value_vs_matched_random",
    "p_adj_vs_matched_random", "beats_matched_random",
    "effect_size_cohens_d", "cohens_d_ci_lower", "cohens_d_ci_upper",
    "ci_lower", "ci_upper", "sharpe", "sortino", "max_drawdown",
    "skewness", "kurtosis", "profit_factor", "expectancy",
]


def fail(msg: str) -> None:
    print(f"ARTIFACT CHECK FAILED: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    for name, min_rows in REQUIRED.items():
        p = RESULTS / name
        if not p.exists():
            fail(f"{p} does not exist")
        if p.stat().st_size == 0:
            fail(f"{p} is empty")
        if min_rows:
            df = pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)
            if len(df) < min_rows:
                fail(f"{p} has {len(df)} rows, expected >= {min_rows}")
        print(f"  ok  {name}")

    master = pd.read_csv(RESULTS / "statistics_master.csv")
    missing = [c for c in REQUIRED_COLUMNS if c not in master.columns]
    if missing:
        fail(f"statistics_master.csv is missing columns: {missing}")
    print(f"  ok  statistics_master.csv carries all {len(REQUIRED_COLUMNS)} required columns")

    # The headline flag must never be set on a negative excess -- that is the
    # exact defect this study was correcting.
    bad = master[
        master["beats_matched_random"].fillna(False)
        & (master["excess_return_vs_matched_random"] <= 0)
    ]
    if len(bad):
        fail(
            f"{len(bad)} row(s) flagged beats_matched_random with a non-positive "
            f"excess return: {bad['signal'].tolist()[:5]}"
        )
    print("  ok  no concept is flagged as beating the null with a negative excess")

    events = pd.read_parquet(RESULTS / "master_events.parquet")
    leaked = [s for s in events["signal"].unique() if "filled" in s or s.endswith("_label")]
    if leaked:
        fail(f"forward-looking labels present in the event table: {leaked}")
    print("  ok  no forward-looking labels in the event table")

    if set(events["direction"].unique()) - {1, -1}:
        fail(f"event table contains invalid directions: {sorted(set(events['direction']))}")
    print("  ok  every event carries direction +1 or -1")

    print("\nAll artefact checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
