"""Tests for index-membership metadata and the survivorship robustness test."""

from __future__ import annotations

import pathlib

import pandas as pd
import pytest

from utils.universe import (
    SNAPSHOT_CSV,
    entry_dates,
    estimate_missing_members,
    load_snapshot,
    membership_mask,
)


@pytest.fixture
def snap(tmp_path):
    """A four-row synthetic snapshot covering each membership case."""
    df = pd.DataFrame(
        [
            ("OLD", "Old Co", "Industrials", "x", "1990-01-01"),
            ("NEW", "New Co", "Information Technology", "x", "2020-06-01"),
            ("BRK.B", "Berkshire", "Financials", "x", "2008-02-01"),
            ("NODATE", "No Date", "Energy", "x", None),
        ],
        columns=["symbol", "company", "gics_sector", "gics_sub_industry", "date_added"],
    )
    df["yf_symbol"] = df["symbol"].str.replace(".", "-", regex=False)
    path = tmp_path / "snapshot.csv"
    df.to_csv(path, index=False)
    return path


class TestMembershipMask:
    def test_trades_before_entry_are_dropped(self, snap):
        trades = pd.DataFrame(
            {
                "ticker": ["NEW", "NEW", "OLD"],
                "date": pd.to_datetime(["2019-01-02", "2021-01-04", "2011-01-03"]),
            }
        )
        assert membership_mask(trades, path=snap).tolist() == [False, True, True]

    def test_entry_date_itself_counts_as_member(self, snap):
        trades = pd.DataFrame({"ticker": ["NEW"], "date": pd.to_datetime(["2020-06-01"])})
        assert membership_mask(trades, path=snap).tolist() == [True]

    def test_dotted_symbols_are_normalised(self, snap):
        assert "BRK-B" in entry_dates(snap)

    @pytest.mark.parametrize("policy, expected", [("keep", True), ("drop", False)])
    def test_unknown_entry_date_policy(self, snap, policy, expected):
        """No entry date, or absent from the snapshot entirely: policy decides."""
        trades = pd.DataFrame(
            {
                "ticker": ["NODATE", "NOT_IN_SNAPSHOT"],
                "date": pd.to_datetime(["2015-01-02", "2015-01-02"]),
            }
        )
        mask = membership_mask(trades, path=snap, unknown_policy=policy)
        assert mask.tolist() == [expected, expected]


class TestSurvivorshipEstimate:
    def test_arithmetic(self, snap):
        est = estimate_missing_members(path=snap, start="2010-01-01")
        assert est["in_index_at_sample_start"] == 2      # OLD, BRK.B
        assert est["joined_during_sample"] == 1          # NEW
        assert est["entry_date_unknown"] == 1            # NODATE
        assert est["estimated_removed_names_missing"] == 500 - 2 - 1

    def test_scope_can_be_restricted_to_analysed_tickers(self, snap):
        est = estimate_missing_members(path=snap, start="2010-01-01", tickers=["OLD", "NEW"])
        assert est["scope"] == "analysed tickers"
        assert est["current_constituents"] == 2
        assert est["in_index_at_sample_start"] == 1
        assert est["estimated_removed_names_missing"] == 499


needs_snapshot = pytest.mark.skipif(
    not SNAPSHOT_CSV.exists(), reason="constituent snapshot not committed"
)


@needs_snapshot
class TestCommittedSnapshot:
    def test_eleven_gics_sectors_and_no_duplicate_symbols(self):
        snap = load_snapshot()
        assert snap["gics_sector"].nunique() == 11
        assert not snap["yf_symbol"].duplicated().any()

    def test_every_bundled_ticker_has_a_gics_sector(self):
        """The CI sample must be fully classifiable, or sector tables gain an Unknown row."""
        snap = load_snapshot()
        sectors = dict(zip(snap["yf_symbol"], snap["gics_sector"]))
        tickers = [p.stem for p in pathlib.Path("data/bundle/prices").glob("*.parquet")]
        assert tickers, "sample bundle is empty"
        missing = [t for t in tickers if not isinstance(sectors.get(t), str)]
        assert not missing, f"bundled tickers without a GICS sector: {missing}"

    def test_resolved_map_uses_published_gics(self):
        """The curated map mis-classified APP, AWK, BLDR, DD, TKO and UBER."""
        from analytics.sectors import resolve_sector_map

        resolved = resolve_sector_map()
        snap = load_snapshot()
        official = dict(zip(snap["yf_symbol"], snap["gics_sector"]))
        wrong = {t: (resolved.get(t), s) for t, s in official.items() if resolved.get(t) != s}
        assert not wrong, f"resolved map disagrees with GICS: {dict(list(wrong.items())[:5])}"


class TestRepoStructure:
    """Package markers must exist.

    All seven were found missing from a working tree once, with no code path in
    this repo that removes files. Without ``tests/__init__.py`` pytest resolves
    imports from a different root, and CI can fail on ``import signals``.
    """

    @pytest.mark.parametrize(
        "pkg", ["analytics", "backtest", "dashboard", "pine_parser", "signals", "tests", "utils"]
    )
    def test_package_has_init(self, pkg):
        assert (pathlib.Path(pkg) / "__init__.py").exists(), f"{pkg}/__init__.py is missing"
