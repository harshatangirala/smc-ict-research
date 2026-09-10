"""Sector Analysis (Task 12): group stocks by GICS-style sector and compare
performance.

Sector source (current)
-----------------------
Sectors come from the published GICS classification in the committed
Wikipedia constituent snapshot (``data/raw/sp500_wikipedia_snapshot.csv``,
see ``utils/universe.py``), through ``resolve_sector_map``. Against that
source the hand-curated SECTOR_MAP below left 54 of 503 constituents
unmapped ("Unknown") and mis-classified 6 (APP, AWK, BLDR, DD, TKO, UBER);
the full list is written to ``results/sector_map_disagreements.csv``.
SECTOR_MAP is retained only as a fallback for a ticker absent from the
snapshot. GICS labels are current, not point-in-time: the 2018 and 2023
GICS reclassifications are applied retroactively -- standard practice, but
it means a 2012 trade in GOOGL is bucketed under Communication Services.

LIMITATION (documented, not hidden): the supplied S&P 500 constituents list
has no sector column. SECTOR_MAP below is a manually curated static mapping
covering the large-cap/high-weight majority of the index; tickers not present
fall back to "Unknown" and are reported separately rather than silently
dropped or mis-bucketed. ``load_sector_map`` offers an optional live lookup
path (``source="live"``), but the static map is the reproducible default and is
what every published number in this study uses: a live lookup would make results
depend on when they were run.

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

from analytics.statistics import (
    build_return_pools,
    matched_excess_calendar_test,
    matched_randomization_test,
)
from backtest.metrics import summarize_returns
from utils.config import PRIMARY_HOLDING_PERIOD, RESULTS_DIR
from utils.logging_config import get_logger

log = get_logger("analytics.sectors")

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


def fetch_live_sectors(
    tickers: list[str], max_workers: int = 8, timeout: float = 10.0
) -> dict[str, str]:
    """Look up GICS-style sectors from Yahoo Finance. Optional, non-reproducible.

    Returns ``{ticker: sector}`` for whatever resolves; tickers that fail are
    simply absent, so a caller can fall back to the static map per ticker rather
    than losing the whole lookup to one bad symbol.

    This is deliberately NOT the default. Yahoo's sector labels change over time
    and the endpoint is unversioned, so a study that depended on it would not
    reproduce. Use it to audit or extend ``SECTOR_MAP``, not to generate results.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        import yfinance as yf
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "fetch_live_sectors needs yfinance: pip install yfinance"
        ) from exc

    def _one(ticker: str) -> tuple[str, str | None]:
        try:
            info = yf.Ticker(ticker).get_info()
            return ticker, info.get("sector") or None
        except Exception:  # noqa: BLE001 - network call, any failure is a miss
            return ticker, None

    out: dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_one, t): t for t in tickers}
        for fut in as_completed(futures, timeout=timeout * len(tickers)):
            try:
                ticker, sector = fut.result()
            except Exception:  # noqa: BLE001
                continue
            if sector:
                out[ticker] = sector
    log.info("Live sector lookup resolved %d/%d tickers", len(out), len(tickers))
    return out


def resolve_sector_map() -> dict[str, str]:
    """The sector map every analysis uses: published GICS, curated fallback.

    Reads the committed snapshot, never the network, so a rerun cannot pick up a
    different classification. Falls back to SECTOR_MAP entry by entry, so a
    ticker missing from the snapshot is still bucketed rather than dropped.
    """
    try:
        from utils.universe import sector_map_from_snapshot

        official = sector_map_from_snapshot()
    except FileNotFoundError:
        log.warning(
            "GICS snapshot missing -- falling back to the hand-curated SECTOR_MAP"
        )
        return dict(SECTOR_MAP)
    merged = dict(SECTOR_MAP)
    merged.update({t: s for t, s in official.items() if isinstance(s, str)})
    return merged


def load_sector_map(
    tickers: list[str] | None = None, source: str = "static"
) -> dict[str, str]:
    """Sector map for `tickers`.

    ``source="static"`` (default) returns the curated map -- reproducible, and
    what the study uses. ``source="live"`` queries Yahoo and falls back to the
    static entry for any ticker that does not resolve, so the result is never
    worse than the default.
    """
    if source == "static" or tickers is None:
        return resolve_sector_map()
    if source != "live":
        raise ValueError(f"source must be 'static' or 'live', got {source!r}")
    live = fetch_live_sectors(list(tickers))
    base = resolve_sector_map()
    merged = {t: live.get(t, base.get(t, "Unknown")) for t in tickers}
    disagreements = {
        t: (base[t], live[t])
        for t in live
        if t in base and base[t] != live[t]
    }
    if disagreements:
        log.warning(
            "Live lookup disagrees with the static map for %d ticker(s): %s",
            len(disagreements), dict(list(disagreements.items())[:5]),
        )
    return merged


def sector_power_analysis(
    sectors: pd.DataFrame, alpha: float = 0.05, power: float = 0.80
) -> pd.DataFrame:
    """Minimum detectable effect per sector, given the sample actually observed.

    A sector result that is "not significant" is uninformative unless the test
    could have detected an effect worth caring about. For each sector this
    reports the smallest true excess return a two-sided test at `alpha` would
    reject with probability `power`:

        MDE = (z_{1-alpha/2} + z_{power}) * SE

    where ``SE`` is the matched-null standard error already computed for that
    sector. ``adequately_powered`` marks sectors whose MDE is below 10 bp -- the
    order of magnitude of the concept-level effects this study found at all --
    so a null result there is genuinely evidence of absence rather than absence
    of evidence.
    """
    from scipy import stats as _st

    if sectors.empty:
        return pd.DataFrame()
    out = sectors.copy()

    se_col = None
    for cand in ("matched_null_se", "std_return"):
        if cand in out.columns:
            se_col = cand
            break
    if se_col == "std_return":
        # Fall back to the iid SE of the mean when a matched-null SE is absent.
        out["_se"] = out["std_return"] / np.sqrt(out["n_trades"].clip(lower=1))
    elif se_col:
        out["_se"] = out[se_col]
    else:
        out["_se"] = np.nan

    z_alpha = _st.norm.ppf(1 - alpha / 2)
    z_power = _st.norm.ppf(power)
    out["mde_return"] = (z_alpha + z_power) * out["_se"]
    out["mde_bps"] = out["mde_return"] * 10_000
    out["observed_excess_bps"] = out.get(
        "excess_return_vs_matched_random", pd.Series(np.nan, index=out.index)
    ) * 10_000
    out["adequately_powered"] = out["mde_bps"] < 10.0
    out["power_note"] = np.where(
        out["adequately_powered"],
        "null result is informative",
        "underpowered: a real effect of this size would likely be missed",
    )
    cols = [
        "sector", "n_tickers", "n_trades", "observed_excess_bps",
        "mde_bps", "adequately_powered", "power_note",
    ]
    return out[[c for c in cols if c in out.columns]].reset_index(drop=True)


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
    smap = resolve_sector_map()
    mapped = pd.Series({t: smap.get(t, "Unknown") for t in tickers})
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
    subset["sector"] = subset["ticker"].map(resolve_sector_map()).fillna("Unknown")

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
        # Design-based SE for the power analysis: calendar-time Newey-West on
        # the per-trade excess, pooling both directions so their same-day
        # covariance is counted. The first version summed per-direction SRS
        # variances, which ignores clustering across tickers and understates
        # the SE -- making every sector look better powered than it is.
        ct = matched_excess_calendar_test(
            grp, pools, holding_period, direction=None, alternative="two-sided"
        )
        metrics["matched_null_se"] = ct["se"]
        metrics["p_value_vs_matched_random"] = ct["p_value"]
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
