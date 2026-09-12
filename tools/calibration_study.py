"""Calibration study: do the significance tests hold their nominal size?

Every design below has a true edge of exactly zero, so a calibrated one-sided
test at alpha = 0.05 rejects about 5% of the time.

Real prices -- the paths are fixed and only the entry dates are random
  independent      each ticker picks its own random dates (the SRS null's own design)
  semi             each ticker picks from one shared pool of 400 dates
  clustered        every ticker fires on the same 150 dates, like a week-open gap

Simulated panel -- the paths are redrawn on every rep
  A GARCH(1,1) market factor plus GARCH(1,1) idiosyncratic noise, Student-t(5)
  shocks, compounded arithmetically. Daily returns are martingale differences,
  so every h-day forward return has conditional mean exactly zero whatever the
  past: even volatility-timed entries have no edge.
  sim_independent  as above, on simulated paths
  sim_clustered    as above, on simulated paths
  sim_vol_timed    each ticker fires on random dates from its top decile of
                   trailing 20-day volatility, so entries crowd into turbulent
                   markets -- as structure-break and displacement detectors do.

Tests
  srs       matched_randomization_test: simple-random-sampling variance
            (the study's first primary test, kept for comparison)
  calendar  matched_excess_calendar_test: calendar-time Newey-West on the
            per-trade excess (the primary test)
  rotation  rotation_null_exact: every circular calendar rotation (secondary)

Besides the rejection rate, each row reports the average standard error a test
uses next to the empirical standard deviation of its own estimate across reps.
se_ratio > 1 means the test overstates its uncertainty (conservative); < 1
means it understates it (anti-conservative).

    python tools/calibration_study.py            # ~10 min on 6 cores
    CALIBRATION_REPS=50 python tools/calibration_study.py   # smoke run
"""

from __future__ import annotations

import os
import sys
import warnings
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analytics.montecarlo import rotation_matrix, rotation_null_exact  # noqa: E402
from analytics.statistics import (  # noqa: E402
    build_return_pools,
    matched_excess_calendar_test,
    matched_randomization_test,
)
from utils.config import DATA_CACHE_DIR, RESULTS_DIR  # noqa: E402
from utils.prices import load_prices  # noqa: E402
from utils.rng import get_rng  # noqa: E402

H = 10
REPS = int(os.environ.get("CALIBRATION_REPS", 1000))
N_TICKERS = 60
N_SIGNALS = 80          # entries per ticker in the per-ticker designs
T_SIM = 4000            # simulated trading days, ~16 years
ALPHA = 0.05

REAL = ("independent", "semi", "clustered")
SIM = ("sim_independent", "sim_clustered", "sim_vol_timed")


def _real_prices() -> dict[str, pd.DataFrame]:
    files = sorted(Path(DATA_CACHE_DIR).glob("*.parquet"))[::7]
    prices = {}
    for f in files:
        df = load_prices(f)
        if len(df) >= 4000:
            prices[f.stem] = df
        if len(prices) >= N_TICKERS:
            break
    if len(prices) < 10:
        raise SystemExit("Not enough cached tickers with full history for the study.")
    return prices


def simulate_panel(rng: np.random.Generator, n_tickers: int = N_TICKERS, T: int = T_SIM):
    """GARCH-factor panel whose h-day forward returns have conditional mean zero."""
    nu = 5.0
    unit = np.sqrt(nu / (nu - 2.0))
    a_m, b_m, v_m = 0.08, 0.90, 0.011      # market: 1.1% daily vol, persistent
    a_i, b_i, v_i = 0.05, 0.93, 0.015      # idiosyncratic: 1.5% daily vol
    w_m, w_i = v_m**2 * (1 - a_m - b_m), v_i**2 * (1 - a_i - b_i)
    zm = rng.standard_t(nu, size=T) / unit
    zi = rng.standard_t(nu, size=(T, n_tickers)) / unit
    beta = rng.uniform(0.6, 1.4, size=n_tickers)
    m = np.empty(T)
    e = np.empty((T, n_tickers))
    s2m, s2i = v_m**2, np.full(n_tickers, v_i**2)
    for t in range(T):
        m[t] = np.sqrt(s2m) * zm[t]
        e[t] = np.sqrt(s2i) * zi[t]
        s2m = w_m + a_m * m[t] ** 2 + b_m * s2m
        s2i = w_i + a_i * e[t] ** 2 + b_i * s2i
    # A symmetric clip keeps prices positive without moving the conditional mean.
    r = np.clip(m[:, None] * beta + e, -0.5, 0.5)
    idx = pd.bdate_range("2010-01-04", periods=T)
    close = 100.0 * np.cumprod(1.0 + r, axis=0)
    names = [f"S{j:02d}" for j in range(n_tickers)]
    prices = {n: pd.DataFrame({"close": close[:, j]}, index=idx) for j, n in enumerate(names)}
    # Trailing volatility through the close of day t: known at entry, no look-ahead.
    vol = pd.DataFrame(r, index=idx, columns=names).rolling(20).std()
    return prices, vol


def _fwd(prices: dict[str, pd.DataFrame]) -> dict[str, pd.Series]:
    out = {}
    for t, df in prices.items():
        c = df["close"].to_numpy(float)
        out[t] = pd.Series(c[H:] / c[:-H] - 1.0, index=df.index[:-H])
    return out


def _draw(design, rng, fwd, common, vol=None) -> pd.DataFrame:
    base = design.removeprefix("sim_")
    rows = []
    if base == "clustered":
        d = rng.choice(common, size=150, replace=False)
        for t, s in fwd.items():
            rows.append(pd.DataFrame({"ticker": t, "date": d, "fwd_return": s.loc[d].to_numpy()}))
    else:
        pool = rng.choice(common, size=400, replace=False) if base == "semi" else None
        for t, s in fwd.items():
            if base == "vol_timed":
                v = vol[t].reindex(s.index)
                cand = s.index[(v >= v.quantile(0.9)).to_numpy()]
            else:
                cand = pool if pool is not None else s.index
            d = rng.choice(cand, size=N_SIGNALS, replace=False)
            rows.append(pd.DataFrame({"ticker": t, "date": d, "fwd_return": s.loc[d].to_numpy()}))
    tr = pd.concat(rows, ignore_index=True)
    tr["direction"] = 1
    return tr


def run_design(design: str) -> list[dict]:
    rng = get_rng(f"calibration:{design}")
    real = design in REAL
    vol = None
    if real:
        prices = _real_prices()
        fwd = _fwd(prices)
        pools = build_return_pools(prices, [H])
        matrix = rotation_matrix(prices, H)
        common = pd.DatetimeIndex(sorted(set.intersection(*[set(s.index) for s in fwd.values()])))
    rec = {k: {"p": [], "est": [], "se": []} for k in ("srs", "calendar", "rotation")}
    for _ in range(REPS):
        if not real:
            prices, vol = simulate_panel(rng)
            fwd = _fwd(prices)
            pools = build_return_pools(prices, [H])
            matrix = rotation_matrix(prices, H)
            common = next(iter(fwd.values())).index
        tr = _draw(design, rng, fwd, common, vol)
        counts = tr.groupby("ticker").size().to_dict()
        mr = matched_randomization_test(counts, float(tr["fwd_return"].mean()), 1, pools, H)
        ct = matched_excess_calendar_test(tr, pools, H, 1)
        ro = rotation_null_exact(tr, H, matrix=matrix)
        for k, p, est, se in (
            ("srs", mr["p_value"], mr["excess_return"], mr["null_se"]),
            ("calendar", ct["p_value"], ct["excess_return"], ct["se"]),
            ("rotation", ro["p_value"], ro["excess_vs_rotation"], ro["null_se"]),
        ):
            rec[k]["p"].append(p)
            rec[k]["est"].append(est)
            rec[k]["se"].append(se)

    mcse = float(np.sqrt(ALPHA * (1 - ALPHA) / REPS))
    out = []
    for k, r in rec.items():
        p, est, se = (np.asarray(r[x], dtype=float) for x in ("p", "est", "se"))
        rate = float(np.mean(p < ALPHA))
        verdict = ("anti-conservative" if rate > ALPHA + 2.5 * mcse
                   else "conservative" if rate < ALPHA - 2.5 * mcse else "calibrated")
        sd = float(np.nanstd(est, ddof=1))
        out.append({
            "design": design,
            "frame": "real prices, paths fixed" if real else "simulated GARCH panel, paths redrawn",
            "test": k,
            "reps": int(len(p)),
            "rejection_rate": rate,
            "mc_se": mcse,
            "size_verdict": verdict,
            "calibrated": verdict != "anti-conservative",
            "mean_estimate": float(np.nanmean(est)),
            "mean_reported_se": float(np.nanmean(se)),
            "empirical_sd": sd,
            "se_ratio": float(np.nanmean(se) / sd) if sd > 0 else np.nan,
        })
    return out


def main() -> int:
    designs = REAL + SIM
    with ProcessPoolExecutor(max_workers=min(len(designs), 6)) as ex:
        results = list(ex.map(run_design, designs))
    res = pd.DataFrame([row for rows in results for row in rows])
    res.to_csv(RESULTS_DIR / "test_calibration.csv", index=False)
    with pd.option_context("display.width", 200):
        print(res[["design", "test", "rejection_rate", "size_verdict", "se_ratio",
                   "mean_estimate"]].to_string(index=False))
    print(f"\nh={H}, {REPS} reps per design. Wrote {RESULTS_DIR / 'test_calibration.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
