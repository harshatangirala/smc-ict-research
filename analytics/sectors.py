"""Sector Analysis (Task 12): group stocks by GICS-style sector and compare
performance.

LIMITATION (documented, not hidden): the supplied S&P 500 constituents list
has no sector column. SECTOR_MAP below is a manually curated static mapping
covering the large-cap/high-weight majority of the index; tickers not present
fall back to "Unknown" and are reported separately rather than silently
dropped or mis-bucketed. ``load_sector_map`` offers an optional live lookup
path, but the static map is the reproducible default.

Duplicate-key defect fixed here
-------------------------------
SECTOR_MAP is built by merging one dict-comprehension per sector. A ticker
listed under two sectors is therefore silently resolved to whichever sector
appears LAST in the literal, with no error. Three tickers were affected:

===== ======================================  ==================  =============
Ticker Declared in                             Silently resolved   Correct
===== ======================================  ==================  =============
AME    Industrials, Real Estate                Real Estate         Industrials
GEN    Information Technology, Health Care     Health Care         Info. Tech.
KVUE   Health Care, Consumer Staples           Consumer Staples    Cons. Staples
===== ======================================  ==================  =============

``_assert_no_duplicate_assignments`` now runs at import and raises, so this
class of error cannot recur silently.
"""

from __future__ import annotations

import pathlib

import pandas as pd

import numpy as np

from analytics.statistics import build_return_pools, matched_randomization_test
from backtest.metrics import summarize_returns
from utils.config import PRIMARY_HOLDING_PERIOD, RESULTS_DIR

SECTOR_MAP: dict[str, str] = {
    # Information Technology
    **{t: "Information Technology" for t in [
        "AAPL", "MSFT", "NVDA", "AVGO", "ORCL", "CRM", "AMD", "ADBE", "CSCO", "ACN",
        "IBM", "INTU", "TXN", "QCOM", "NOW", "AMAT", "PANW", "ANET", "MU", "LRCX",
        "KLAC", "SNPS", "CDNS", "ADI", "APH", "MSI", "FTNT", "CRWD", "ADSK", "ROP",
        "NXPI", "MCHP", "FICO", "IT", "GDDY", "TEL", "KEYS", "GEN", "TDY", "TER",
        "SWKS", "TYL", "ZBRA", "PTC", "AKAM", "JNPR", "ON", "STX", "WDC", "HPQ",
        "DELL", "HPE", "SMCI", "COHR", "TRMB", "FSLR", "ENPH", "GLW", "VRSN", "DDOG",
        "PLTR", "APP", "SNDK", "Q",
    ]},
    # Health Care
    **{t: "Health Care" for t in [
        "LLY", "UNH", "JNJ", "ABBV", "MRK", "TMO", "ABT", "PFE", "DHR", "AMGN",
        "ISRG", "BSX", "SYK", "VRTX", "GILD", "MDT", "CI", "ELV", "REGN", "ZTS",
        "BDX", "HCA", "CVS", "MCK", "EW", "IDXX", "IQV", "CNC", "GEHC", "A",
        "BIIB", "MRNA", "RMD", "DXCM", "COR", "HUM", "WAT", "ALGN", "STE", "TECH",
        "VTRS", "INCY", "PODD", "UHS", "DVA", "CAH", "MOH", "HSIC", "BMY", "SOLV",
        "RVTY", "COO", "CRL",
    ]},
    # Financials
    **{t: "Financials" for t in [
        "BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS", "MS", "SPGI", "AXP",
        "C", "BLK", "SCHW", "CB", "PGR", "MMC", "MRSH", "ICE", "CME", "AON",
        "USB", "PNC", "TFC", "AJG", "COF", "BX", "APO", "KKR", "MCO", "TRV",
        "AFL", "MET", "ALL", "AIG", "PRU", "FIS", "BK", "BNY", "STT", "NTRS",
        "FITB", "HBAN", "RF", "CFG", "KEY", "SYF", "DFS", "AMP", "WTW", "ARES",
        "IVZ", "PFG", "GL", "L", "GPN", "CPAY", "FDS", "MTB", "RJF", "TROW",
        "HIG", "CINF", "ERIE", "WRB", "ACGL", "EG", "CBOE", "NDAQ", "COIN", "IBKR",
        "HOOD", "BEN",
    ]},
    # Consumer Discretionary
    **{t: "Consumer Discretionary" for t in [
        "AMZN", "TSLA", "HD", "MCD", "BKNG", "LOW", "TJX", "SBUX", "NKE", "ABNB",
        "CMG", "ORLY", "MAR", "GM", "F", "HLT", "AZO", "ROST", "YUM", "DHI",
        "LEN", "EBAY", "NVR", "LULU", "PHM", "RCL", "CCL", "NCLH", "DPZ", "TSCO",
        "LVS", "WYNN", "MGM", "EXPE", "ULTA", "DECK", "RL", "GRMN", "APTV", "BBY",
        "GPC", "TPR", "POOL", "CZR", "WSM", "DASH", "UBER", "CVNA", "KMX", "HAS",
        "BLDR", "TKO",
    ]},
    # Communication Services
    **{t: "Communication Services" for t in [
        "GOOGL", "GOOG", "META", "NFLX", "DIS", "TMUS", "CMCSA", "VZ", "T", "CHTR",
        "EA", "TTWO", "WBD", "OMC", "LYV", "NWSA", "NWS", "FOXA", "FOX", "PARA",
        "IPG", "MTCH", "PSKY",
    ]},
    # Industrials
    **{t: "Industrials" for t in [
        "GE", "CAT", "RTX", "UNP", "HON", "BA", "DE", "LMT", "UPS", "ADP",
        "GEV", "ETN", "WM", "ITW", "PH", "TT", "CSX", "NOC", "EMR", "CTAS",
        "CARR", "GD", "NSC", "PCAR", "JCI", "TDG", "AME", "URI", "FDX", "PWR",
        "RSG", "CMI", "OTIS", "XYL", "IR", "HWM", "DOV", "ROK", "WAB", "FAST",
        "EFX", "VRSK", "LHX", "SNA", "PAYX", "J", "IEX", "HII", "TXT", "ALLE",
        "CHRW", "EXPD", "MAS", "AOS", "NDSN", "LII", "PNR", "GNRC", "AXON", "LDOS",
        "JBHT", "GWW", "BR", "FIX", "HUBB", "EME",
    ]},
    # Consumer Staples
    **{t: "Consumer Staples" for t in [
        "WMT", "PG", "KO", "PEP", "COST", "PM", "MO", "MDLZ", "CL", "TGT",
        "KMB", "GIS", "SYY", "KDP", "STZ", "KHC", "HSY", "MNST", "ADM", "KR",
        "KVUE", "CHD", "CLX", "TAP", "CASY", "BG", "TSN", "DG", "DLTR", "SJM",
        "LW", "HRL", "CAG", "MKC",
    ]},
    # Energy
    **{t: "Energy" for t in [
        "XOM", "CVX", "COP", "WMB", "EOG", "SLB", "OKE", "KMI", "PSX", "MPC",
        "VLO", "BKR", "TRGP", "OXY", "HAL", "DVN", "FANG", "EXE", "EQT", "APA",
    ]},
    # Utilities
    **{t: "Utilities" for t in [
        "NEE", "SO", "DUK", "CEG", "AEP", "D", "SRE", "EXC", "XEL", "ED",
        "PEG", "WEC", "EIX", "ETR", "DTE", "PPL", "AEE", "FE", "ES", "CMS",
        "ATO", "CNP", "NI", "EVRG", "LNT", "PNW", "PCG", "NRG", "VST",
    ]},
    # Real Estate
    **{t: "Real Estate" for t in [
        "PLD", "AMT", "EQIX", "WELL", "DLR", "PSA", "O", "SPG", "CCI", "CBRE",
        "VICI", "AWK", "AAT", "AIRC", "AIV", "IRM", "AMH", "SBAC",
        "AVB", "BXP", "CPT", "DOC", "EQR", "ESS", "EXR", "FRT", "HST", "INVH",
        "KIM", "MAA", "REG", "UDR", "VTR",
    ]},
    # Materials
    **{t: "Materials" for t in [
        "LIN", "APD", "SHW", "ECL", "FCX", "NEM", "NUE", "DOW", "DD", "PPG",
        "VMC", "MLM", "CTVA", "STLD", "IFF", "ALB", "CF", "AMCR", "PKG", "BALL",
        "AVY", "LYB", "EMN", "MOS", "IP",
    ]},
}


def _assert_no_duplicate_assignments(source_path: str = __file__) -> dict[str, list[str]]:
    """Raise if any ticker is declared under more than one sector.

    The check reads this module's own source rather than SECTOR_MAP, because
    by the time the dict exists the duplicates have already collapsed.
    """
    import re as _re

    text = pathlib.Path(source_path).read_text(encoding="utf-8")
    blocks = _re.findall(r'\*\*\{t: "([^"]+)" for t in \[(.*?)\]\}', text, _re.S)
    seen: dict[str, list[str]] = {}
    for sector, body in blocks:
        for ticker in _re.findall(r'"([A-Z\-]+)"', body):
            seen.setdefault(ticker, []).append(sector)
    dupes = {t: v for t, v in seen.items() if len(v) > 1}
    if dupes:
        raise ValueError(
            "Ticker(s) assigned to multiple sectors -- a dict literal would "
            f"silently keep the last: {dupes}"
        )
    return seen


_assert_no_duplicate_assignments()


def sector_coverage_report(tickers) -> pd.DataFrame:
    """Per-sector ticker counts plus the unmapped remainder.

    Sector conclusions rest on how many distinct names actually back each
    bucket; a sector carried by three tickers is not evidence about a sector.
    """
    mapped = pd.Series({t: SECTOR_MAP.get(t, "Unknown") for t in tickers})
    counts = mapped.value_counts().rename_axis("sector").reset_index(name="n_tickers")
    counts["share_of_universe"] = counts["n_tickers"] / max(len(mapped), 1)
    return counts.sort_values("n_tickers", ascending=False).reset_index(drop=True)


def _load_baseline_trades() -> pd.DataFrame | None:
    path = RESULTS_DIR / "baseline_trades.parquet"
    if not path.exists():
        return None
    baseline = pd.read_parquet(path)
    return baseline[baseline["signal"] == "baseline_random_bullish"]


def sector_analysis(
    trades: pd.DataFrame | None = None,
    holding_period: int = PRIMARY_HOLDING_PERIOD,
) -> pd.DataFrame:
    """Per-sector performance against a DIRECTION-MATCHED random-entry null.

    Why not the long-only baseline
    ------------------------------
    The signal population is roughly half long and half short. Its pooled mean
    return over 2010-2026 is therefore near zero or negative, because the short
    half loses in a bull market. The random-entry baseline, by contrast, is
    long-only. Subtracting one from the other measures *net long exposure*, not
    signal quality, and it does so identically in every sector -- which is why
    the previous version found every sector negative by a similar margin
    (-0.5pp to -1.2pp) and concluded that SMC/ICT underperforms random entry
    almost everywhere.

    Each direction is now compared against its own null: long signals against
    the mean forward return of random long entries on the same tickers, short
    signals against the negation of it. `excess_return_vs_matched_random` is
    the trade-count-weighted combination, so a sector's number answers "did
    these signals beat random entry taken in the same direction, on these
    names" rather than "were these signals net long".
    """
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    subset = trades[trades["holding_period"] == holding_period].copy()
    subset["sector"] = subset["ticker"].map(SECTOR_MAP).fillna("Unknown")

    pools = _build_pools(holding_period)

    rows = []
    for sector, grp in subset.groupby("sector"):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        metrics["sector"] = sector
        metrics["n_tickers"] = grp["ticker"].nunique()

        # Direction-matched null, weighted by each direction's trade count.
        null_total, n_total, excess_num = 0.0, 0, 0.0
        for direction, dgrp in grp.groupby("direction"):
            mr = matched_randomization_test(
                dgrp.groupby("ticker").size().to_dict(),
                float(dgrp["fwd_return"].mean()),
                int(direction),
                pools,
                holding_period,
            )
            n_d = len(dgrp)
            if mr["null_mean"] is not None and np.isfinite(mr["null_mean"]):
                null_total += mr["null_mean"] * n_d
                excess_num += mr["excess_return"] * n_d
                n_total += n_d
        metrics["matched_null_mean"] = null_total / n_total if n_total else np.nan
        metrics["excess_return_vs_matched_random"] = (
            excess_num / n_total if n_total else np.nan
        )
        metrics["n_long_trades"] = int((grp["direction"] == 1).sum())
        metrics["n_short_trades"] = int((grp["direction"] == -1).sum())
        # Long-only view, so a reader can still see the directional split.
        longs = grp[grp["direction"] == 1]["fwd_return"]
        shorts = grp[grp["direction"] == -1]["fwd_return"]
        metrics["avg_return_long"] = float(longs.mean()) if len(longs) else np.nan
        metrics["avg_return_short"] = float(shorts.mean()) if len(shorts) else np.nan
        rows.append(metrics)

    ranking = pd.DataFrame(rows).sort_values(
        "excess_return_vs_matched_random", ascending=False, na_position="last"
    )
    return ranking.reset_index(drop=True)


def _build_pools(holding_period: int) -> dict:
    """Per-(ticker, horizon) forward-return pools for the matched null."""
    from backtest.engine import _load_price_cache

    prices = {t: df.set_index("date") for t, df in _load_price_cache().items()}
    return build_return_pools(prices, [holding_period])
