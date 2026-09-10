"""Calibration study: do the significance tests hold their nominal size?

Draws entry dates at RANDOM from real price data -- so the true edge is zero by
construction -- and records how often each test rejects at alpha = 0.05. A
calibrated one-sided test rejects about 5% of the time.

Entry designs, from independent to fully clustered:
  independent  each ticker picks its own random dates (the SRS null's own design)
  semi         each ticker picks from one shared pool of 400 dates
  clustered    every ticker fires on the same 150 dates, like a week-open gap signal

Tests:
  srs          matched_randomization_test -- simple-random-sampling variance
               (the study's first primary test; kept for comparison)
  calendar     matched_excess_calendar_test -- per-trade excess over the same
               benchmark, calendar-time Newey-West (the primary test)
  rotation     monte_carlo_rotation_null -- calendar rotation, preserves clustering

Writes results/test_calibration.csv. The audit that motivated it found the SRS
test rejecting 28-40% of uninformative clustered signals.

    python tools/calibration_study.py
"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analytics.montecarlo import monte_carlo_rotation_null  # noqa: E402
from analytics.statistics import (  # noqa: E402
    build_return_pools,
    matched_excess_calendar_test,
    matched_randomization_test,
)
from utils.config import DATA_CACHE_DIR, RESULTS_DIR  # noqa: E402
from utils.prices import load_prices  # noqa: E402
from utils.rng import get_rng  # noqa: E402

H = 10
REPS = 300
ROTATION_REPS = 200
ROTATION_RUNS = 199
N_TICKERS = 60


def main() -> int:
    rng = get_rng("calibration_study")
    files = sorted(Path(DATA_CACHE_DIR).glob("*.parquet"))[::7]
    prices = {}
    for f in files:
        df = load_prices(f)
        if len(df) >= 4000:
            prices[f.stem] = df
        if len(prices) >= N_TICKERS:
            break
    if len(prices) < 10:
        print("Not enough cached tickers with full history for the study.")
        return 1

    pools = build_return_pools(prices, [H])
    fwd = {}
    for t, df in prices.items():
        c = df["close"].to_numpy(float)
        fwd[t] = pd.Series(c[H:] / c[:-H] - 1.0, index=df.index[:-H])
    common = pd.DatetimeIndex(sorted(set.intersection(*[set(s.index) for s in fwd.values()])))

    def draw(design):
        rows = []
        if design == "independent":
            for t, s in fwd.items():
                d = rng.choice(s.index, size=80, replace=False)
                rows.append(pd.DataFrame({"ticker": t, "date": d, "fwd_return": s.loc[d].to_numpy()}))
        elif design == "semi":
            pool = rng.choice(common, size=400, replace=False)
            for t, s in fwd.items():
                d = rng.choice(pool, size=80, replace=False)
                rows.append(pd.DataFrame({"ticker": t, "date": d, "fwd_return": s.loc[d].to_numpy()}))
        else:
            d = rng.choice(common, size=150, replace=False)
            for t, s in fwd.items():
                rows.append(pd.DataFrame({"ticker": t, "date": d, "fwd_return": s.loc[d].to_numpy()}))
        tr = pd.concat(rows, ignore_index=True)
        tr["direction"] = 1
        return tr

    out = []
    for design in ("independent", "semi", "clustered"):
        srs, cal, rot = [], [], []
        for i in range(REPS):
            tr = draw(design)
            counts = tr.groupby("ticker").size().to_dict()
            srs.append(matched_randomization_test(
                counts, float(tr["fwd_return"].mean()), 1, pools, H)["p_value"])
            cal.append(matched_excess_calendar_test(tr, pools, H, 1)["p_value"])
            if i < ROTATION_REPS:
                rot.append(monte_carlo_rotation_null(
                    tr, prices, H, n_runs=ROTATION_RUNS, label=f"cal:{design}:{i}")["p_value"])
        for name, ps in (("srs", srs), ("calendar", cal), ("rotation", rot)):
            ps = np.asarray(ps)
            rate = float((ps < 0.05).mean())
            out.append({
                "design": design, "test": name, "reps": len(ps),
                "rejection_rate": rate,
                "mc_se": float(np.sqrt(0.05 * 0.95 / len(ps))),
                "calibrated": bool(rate <= 0.05 + 2.5 * np.sqrt(0.05 * 0.95 / len(ps))),
            })
        print(f"{design:<12}" + "  ".join(
            f"{r['test']}={r['rejection_rate']:.3f}" for r in out[-3:]))

    res = pd.DataFrame(out)
    res.to_csv(RESULTS_DIR / "test_calibration.csv", index=False)
    print(f"\n{len(prices)} tickers, h={H}. Wrote {RESULTS_DIR / 'test_calibration.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
