"""Data Quality Validation (Task 4 / Requirement 22).

Checks every cached ticker's OHLCV for missing values, duplicate rows,
timestamp gaps, invalid OHLC relationships, outliers, and coverage, and
produces a single Data Quality Report dataframe.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from utils.logging_config import get_logger

log = get_logger("data_quality")


def validate_ticker(ticker: str, df: pd.DataFrame) -> dict:
    """Run all data-quality checks for a single ticker's OHLCV frame."""
    report = {"ticker": ticker}

    if df is None or df.empty:
        report.update(
            {
                "rows": 0, "start": None, "end": None,
                "missing_values": None, "duplicate_dates": None,
                "invalid_ohlc_rows": 0, "non_monotonic_index": True,
                "zero_or_negative_price_rows": 0, "extreme_daily_move_rows": 0,
                "coverage_days": 0, "status": "NO_DATA",
            }
        )
        return report

    df = df.sort_index()
    report["rows"] = len(df)
    report["start"] = str(df.index.min().date())
    report["end"] = str(df.index.max().date())
    report["missing_values"] = int(df[["open", "high", "low", "close", "volume"]].isna().sum().sum())
    report["duplicate_dates"] = int(df.index.duplicated().sum())
    report["non_monotonic_index"] = bool(not df.index.is_monotonic_increasing)

    # A small relative tolerance absorbs floating-point noise introduced by
    # yfinance's auto_adjust (split/dividend back-adjustment), which can
    # otherwise make e.g. high fractionally less than close on an
    # ex-dividend bar even though the true, unadjusted OHLC relationship
    # was always valid.
    tol = 1e-6 * df["close"].abs().clip(lower=1e-9)
    invalid_ohlc = (
        (df["high"] < df["low"] - tol)
        | (df["high"] < df["open"] - tol)
        | (df["high"] < df["close"] - tol)
        | (df["low"] > df["open"] + tol)
        | (df["low"] > df["close"] + tol)
    )
    report["invalid_ohlc_rows"] = int(invalid_ohlc.sum())

    zero_or_neg = (df[["open", "high", "low", "close"]] <= 0).any(axis=1)
    report["zero_or_negative_price_rows"] = int(zero_or_neg.sum())

    daily_ret = df["close"].pct_change()
    extreme_move = daily_ret.abs() > 0.5  # >50% single-day move: flag for review
    report["extreme_daily_move_rows"] = int(extreme_move.sum())

    expected_trading_days = np.busday_count(
        df.index.min().date(), df.index.max().date()
    )
    report["coverage_days"] = len(df)
    report["expected_busdays_approx"] = int(expected_trading_days)
    report["coverage_ratio"] = round(
        len(df) / expected_trading_days, 3
    ) if expected_trading_days > 0 else None

    issues = (
        report["missing_values"]
        + report["duplicate_dates"]
        + report["invalid_ohlc_rows"]
        + report["zero_or_negative_price_rows"]
    )
    report["status"] = "OK" if issues == 0 else "ISSUES_FOUND"
    return report


def build_data_quality_report(price_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Run validate_ticker across the whole universe and return one dataframe."""
    rows = [validate_ticker(t, df) for t, df in price_data.items()]
    report = pd.DataFrame(rows)
    n_ok = (report["status"] == "OK").sum()
    n_issues = (report["status"] == "ISSUES_FOUND").sum()
    n_missing = (report["status"] == "NO_DATA").sum()
    log.info(
        "Data quality report: %d OK, %d with issues, %d with no data (of %d total)",
        n_ok, n_issues, n_missing, len(report),
    )
    return report
