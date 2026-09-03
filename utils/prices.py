"""Single, shared price-cache loader.

Every consumer of cached OHLCV (event detection, the backtest engine, the
baseline engine, regime tagging) previously re-implemented "read parquet, sort,
drop duplicate index" inline. Those copies had already drifted -- only some of
them deduplicated -- so a repair applied in one place would silently not apply
in another. They all route through here now.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from utils.config import DATA_CACHE_DIR, REPAIR_INVALID_OHLC
from utils.logging_config import get_logger

log = get_logger("utils.prices")

OHLC = ["open", "high", "low", "close"]


#: Violations smaller than this fraction of the close are float-representation
#: noise from parquet round-tripping and back-adjustment, not bad data. Across
#: this 498-ticker universe there are 1,301 such bars and exactly 3 material
#: ones (APH 2021-05-05 and 2023-06-05, HUBB 2021-05-05), so logging every
#: clamp without this threshold would report 70+ "bad data" tickers and bury
#: the three that matter.
MATERIAL_TOLERANCE = 1e-6


def repair_ohlc(
    df: pd.DataFrame, ticker: str = "", tolerance: float = MATERIAL_TOLERANCE
) -> tuple[pd.DataFrame, int]:
    """Clamp `high`/`low` so each bar encloses its own open and close.

    Yahoo's split/dividend back-adjustment occasionally emits a bar whose low
    sits above the open, or whose high sits below it. The original pipeline
    *counted* these in the data-quality report and then fed them to the
    detectors unchanged, where an impossible bar can manufacture a spurious
    pivot, swing or order block.

    The repair is minimal and direction-preserving: ``high`` is raised to
    ``max(high, open, close)`` and ``low`` lowered to ``min(low, open, close)``
    -- the smallest change that restores the OHLC invariant without inventing
    a range the bar never had.

    Returns the repaired frame and the number of MATERIAL bars altered
    (violations exceeding `tolerance` as a fraction of close). Sub-tolerance
    clamps are still applied, just not reported.
    """
    if df.empty or not set(OHLC).issubset(df.columns):
        return df, 0
    hi = df[["high", "open", "close"]].max(axis=1)
    lo = df[["low", "open", "close"]].min(axis=1)
    changed = (hi != df["high"]) | (lo != df["low"])
    if not changed.any():
        return df, 0

    magnitude = ((hi - df["high"]).abs() + (df["low"] - lo).abs()) / df["close"].abs()
    material = int((magnitude > tolerance).sum())

    df = df.copy()
    df["high"] = hi
    df["low"] = lo
    if material:
        dates = ", ".join(str(d.date()) for d in magnitude[magnitude > tolerance].index[:5])
        log.warning(
            "Repaired %d materially invalid OHLC bar(s) for %s (%s)",
            material, ticker or "<unknown>", dates,
        )
    return df, material


def load_prices(path: Path | str, repair: bool = REPAIR_INVALID_OHLC) -> pd.DataFrame:
    """Load one cached ticker: sorted, de-duplicated, optionally OHLC-repaired."""
    path = Path(path)
    df = pd.read_parquet(path).sort_index()
    df = df[~df.index.duplicated(keep="first")]
    if repair:
        df, _ = repair_ohlc(df, path.stem)
    return df


def load_price_cache(
    cache_dir: Path | str = DATA_CACHE_DIR,
    tickers: list[str] | None = None,
    repair: bool = REPAIR_INVALID_OHLC,
) -> dict[str, pd.DataFrame]:
    """Load the whole cache as ``{ticker: date-indexed OHLCV frame}``."""
    files = sorted(Path(cache_dir).glob("*.parquet"))
    if tickers is not None:
        wanted = set(tickers)
        files = [f for f in files if f.stem in wanted]
    return {f.stem: load_prices(f, repair=repair) for f in files}
