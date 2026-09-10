"""Index-membership metadata: authoritative GICS sectors and index-entry dates.

Why this exists
---------------
Two weaknesses in the original pipeline trace to the same root -- the supplied
constituent list carries only symbol, name and weight:

1. **Sectors were hand-curated.** ``analytics/sectors.SECTOR_MAP`` covers 471 of
   503 tickers, leaves ~10% as "Unknown", and had three tickers silently
   mis-bucketed by duplicate dict keys. A hand-maintained map of 500 symbols
   cannot be kept correct.
2. **Index membership was treated as constant.** Every ticker was traded across
   the whole 2010-2026 window regardless of when it actually joined the index.
   PLTR is tested from its 2020 listing although it joined the S&P 500 in 2024;
   at the time, an investor following this strategy could not have been looking
   at it as an index constituent.

Both are fixed by the ``Date added`` and ``GICS Sector`` columns Wikipedia
publishes alongside the constituent list.

What this does NOT fix
----------------------
Companies that were in the index during 2010-2026 and have since been *removed*
are absent from the dataset entirely, and no free source reconstructs them: the
"Selected changes to the component stocks" table that Wikipedia used to publish
is no longer on the page as of this snapshot. ``estimate_missing_members``
quantifies how large that hole is rather than leaving it as a hand-wave, and
``docs/manuscript.md`` states it as the study's principal surviving limitation.

Reproducibility
---------------
The fetched table is cached to ``data/raw/sp500_wikipedia_snapshot.csv`` and
committed. The pipeline reads the cache; it never hits the network unless the
cache is missing and ``allow_fetch=True``. A live fetch would make results
depend on when they were run.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from utils.config import DATA_RAW_DIR, DATA_START
from utils.logging_config import get_logger

log = get_logger("utils.universe")

SNAPSHOT_CSV = DATA_RAW_DIR / "sp500_wikipedia_snapshot.csv"
WIKI_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"

#: Yahoo encodes share-class separators as '-' where the index list uses '.'.
def _normalize(symbol: str) -> str:
    return str(symbol).strip().replace(".", "-")


def fetch_snapshot(url: str = WIKI_URL, timeout: float = 30.0) -> pd.DataFrame:
    """Download the current constituent table: symbol, sector, date added.

    Network call. Use ``load_snapshot`` in the pipeline; this is for refreshing
    the committed cache deliberately.
    """
    import requests

    resp = requests.get(
        url, headers={"User-Agent": "Mozilla/5.0 (academic research)"}, timeout=timeout
    )
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    for t in tables:
        cols = {str(c) for c in t.columns}
        if {"Symbol", "GICS Sector"} <= cols:
            out = t.rename(
                columns={
                    "Symbol": "symbol",
                    "Security": "company",
                    "GICS Sector": "gics_sector",
                    "GICS Sub-Industry": "gics_sub_industry",
                    "Date added": "date_added",
                }
            )
            keep = [
                c for c in
                ["symbol", "company", "gics_sector", "gics_sub_industry", "date_added"]
                if c in out.columns
            ]
            out = out[keep].copy()
            out["yf_symbol"] = out["symbol"].map(_normalize)
            out["date_added"] = pd.to_datetime(out.get("date_added"), errors="coerce")
            out["retrieved_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            log.info("Fetched %d constituents from Wikipedia", len(out))
            return out.reset_index(drop=True)
    raise RuntimeError("No table with Symbol + GICS Sector found at " + url)


def save_snapshot(df: pd.DataFrame, path: Path = SNAPSHOT_CSV) -> Path:
    df.to_csv(path, index=False)
    log.info("Wrote constituent snapshot to %s (%d rows)", path, len(df))
    return path


def load_snapshot(path: Path = SNAPSHOT_CSV, allow_fetch: bool = False) -> pd.DataFrame:
    """Read the committed snapshot. Fetches only if missing and allowed."""
    path = Path(path)
    if path.exists():
        df = pd.read_csv(path)
        df["date_added"] = pd.to_datetime(df["date_added"], errors="coerce")
        return df
    if not allow_fetch:
        raise FileNotFoundError(
            f"{path} not found. Run `python tools/refresh_universe.py` to create it. "
            "The pipeline does not fetch automatically, so results cannot silently "
            "depend on when they were run."
        )
    df = fetch_snapshot()
    save_snapshot(df, path)
    return df


def sector_map_from_snapshot(path: Path = SNAPSHOT_CSV) -> dict[str, str]:
    """``{yf_symbol: GICS sector}`` -- authoritative, not hand-curated.

    Complete for every current constituent, so no ticker falls into "Unknown"
    for want of a manual entry.
    """
    df = load_snapshot(path)
    return dict(zip(df["yf_symbol"], df["gics_sector"]))


def entry_dates(path: Path = SNAPSHOT_CSV) -> dict[str, pd.Timestamp]:
    """``{yf_symbol: index-entry date}``, NaT where Wikipedia has none."""
    df = load_snapshot(path)
    return dict(zip(df["yf_symbol"], df["date_added"]))


def membership_mask(
    trades: pd.DataFrame,
    path: Path = SNAPSHOT_CSV,
    date_col: str = "date",
    ticker_col: str = "ticker",
    unknown_policy: str = "keep",
) -> pd.Series:
    """Boolean mask: was this ticker an index constituent on the trade date?

    ``Date added`` is the MOST RECENT addition. A company removed and later
    re-added is treated as a non-member for its whole earlier tenure, so the
    filter can drop trades from a period when the name genuinely was in the
    index. That errs toward removing data, never toward keeping look-ahead.

    ``unknown_policy`` governs tickers with no recorded entry date:
    ``"keep"`` (assume long-standing membership, the conservative choice for a
    study whose result is negative) or ``"drop"``.
    """
    added = entry_dates(path)
    dates = pd.to_datetime(trades[date_col])
    entry = trades[ticker_col].map(added)
    known = entry.notna()
    mask = pd.Series(unknown_policy == "keep", index=trades.index)
    mask.loc[known] = dates.loc[known] >= entry.loc[known]
    return mask


def estimate_missing_members(
    path: Path = SNAPSHOT_CSV,
    start: str = DATA_START,
    tickers: list[str] | None = None,
) -> dict:
    """Size the survivorship hole this dataset cannot fill.

    The index holds 500 names at every point in time. Of today's constituents,
    only those with ``date_added <= start`` were also in it at the start of the
    sample; the remainder of the 500 slots were held by companies that have
    since been removed and are absent here.

    This is an estimate of a *lower bound* on the number of distinct names
    missing: it counts slots, not the churn within them, so a slot that changed
    hands three times counts once.

    Pass ``tickers`` to size the hole relative to the universe actually
    analysed. The snapshot is a later vintage than the study's constituent
    list and differs from it by a few recent index changes, so the two scopes
    give slightly different counts; published numbers use the analysed scope.
    """
    df = load_snapshot(path)
    if tickers is not None:
        df = df[df["yf_symbol"].isin(set(tickers))]
    start_ts = pd.Timestamp(start)
    known = df["date_added"].notna()
    present_at_start = int((df["date_added"] <= start_ts).sum())
    joined_during = int(((df["date_added"] > start_ts) & known).sum())
    unknown = int((~known).sum())

    index_size = 500
    missing_lower_bound = max(index_size - present_at_start - unknown, 0)
    return {
        "scope": "analysed tickers" if tickers is not None else "full snapshot",
        "current_constituents": int(len(df)),
        "with_known_entry_date": int(known.sum()),
        "entry_date_unknown": unknown,
        "in_index_at_sample_start": present_at_start,
        "joined_during_sample": joined_during,
        "estimated_removed_names_missing": missing_lower_bound,
        "estimated_survivorship_gap_pct": round(
            100 * missing_lower_bound / index_size, 1
        ),
        "sample_start": str(start_ts.date()),
        "note": (
            "Lower bound on distinct names absent from the dataset. Counts index "
            "slots not held by a current constituent at the sample start; churn "
            "within a slot is not counted, so the true number of distinct names "
            "that passed through the index over 2010-2026 is larger."
        ),
    }


def coverage_report(tickers: list[str], path: Path = SNAPSHOT_CSV) -> pd.DataFrame:
    """Per-ticker membership metadata for the tickers actually analysed."""
    df = load_snapshot(path).set_index("yf_symbol")
    rows = []
    for t in tickers:
        if t in df.index:
            r = df.loc[t]
            rows.append(
                {
                    "ticker": t,
                    "gics_sector": r["gics_sector"],
                    "date_added": r["date_added"],
                    "in_index_at_start": bool(
                        pd.notna(r["date_added"])
                        and r["date_added"] <= pd.Timestamp(DATA_START)
                    ),
                }
            )
        else:
            rows.append(
                {"ticker": t, "gics_sector": np.nan, "date_added": pd.NaT,
                 "in_index_at_start": False}
            )
    return pd.DataFrame(rows)
