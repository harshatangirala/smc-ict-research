"""Sector Analysis (Task 12): group stocks by GICS-style sector and compare
performance.

LIMITATION (documented, not hidden): the supplied S&P 500 constituents list
has no sector column, and there is no live sector-lookup API wired into this
offline pipeline. SECTOR_MAP below is a manually curated, best-effort
static mapping covering the large-cap/high-weight majority of the index
(chosen to cover the bulk of total index weight and trading activity);
tickers not present fall back to "Unknown" and are reported separately
rather than silently dropped or mis-bucketed. A future improvement would
wire in a proper sector data source (see README "Future improvements").
"""

from __future__ import annotations

import pandas as pd

from backtest.metrics import summarize_returns
from utils.config import RESULTS_DIR

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
        "KVUE", "RVTY", "COO", "CRL", "GEN",
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
        "VICI", "AVB", "AWK", "AME", "AAT", "AIRC", "AIV", "IRM", "AMH", "SBAC",
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


def _load_baseline_trades() -> pd.DataFrame | None:
    path = RESULTS_DIR / "baseline_trades.parquet"
    if not path.exists():
        return None
    baseline = pd.read_parquet(path)
    return baseline[baseline["signal"] == "baseline_random_bullish"]


def sector_analysis(trades: pd.DataFrame | None = None, holding_period: int = 10) -> pd.DataFrame:
    if trades is None:
        trades = pd.read_parquet(RESULTS_DIR / "trades.parquet")
    subset = trades[trades["holding_period"] == holding_period].copy()
    subset["sector"] = subset["ticker"].map(SECTOR_MAP).fillna("Unknown")

    baseline_trades = _load_baseline_trades()
    baseline_sector_avg = {}
    if baseline_trades is not None:
        base_subset = baseline_trades[baseline_trades["holding_period"] == holding_period].copy()
        base_subset["sector"] = base_subset["ticker"].map(SECTOR_MAP).fillna("Unknown")
        baseline_sector_avg = base_subset.groupby("sector")["fwd_return"].mean().to_dict()

    rows = []
    for sector, grp in subset.groupby("sector"):
        metrics = summarize_returns(grp["fwd_return"], holding_period)
        metrics["sector"] = sector
        metrics["n_tickers"] = grp["ticker"].nunique()
        metrics["baseline_avg_return"] = baseline_sector_avg.get(sector, float("nan"))
        metrics["excess_return_vs_baseline"] = metrics["avg_return"] - metrics["baseline_avg_return"]
        rows.append(metrics)

    ranking = pd.DataFrame(rows).sort_values(
        "excess_return_vs_baseline", ascending=False, na_position="last"
    )
    return ranking.reset_index(drop=True)
