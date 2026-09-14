"""Order-block candle selection must match the LuxAlgo Pine source.

Audit finding: the SMC detector picked the block candle with the opposite
extreme -- argmax(parsed_high) for a BULLISH block, where Pine's storeOrdeBlock
takes argmin(parsed_low) -- and included the break bar. Formation timing was
unaffected, so formation-based tests all passed; only the block's price levels,
and therefore every *_mitigated signal, were wrong. These tests discriminate on
mitigation timing, which is exactly where the defect showed.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _ohlc(close, open_=None, wick=0.5):
    close = np.asarray(close, dtype=float)
    if open_ is None:
        open_ = np.r_[close[0], close[:-1]]
    open_ = np.asarray(open_, dtype=float)
    idx = pd.bdate_range("2020-01-01", periods=len(close))
    return (
        pd.Series(np.maximum(open_, close) + wick, index=idx),
        pd.Series(np.minimum(open_, close) - wick, index=idx),
        pd.Series(close, index=idx),
        pd.Series(open_, index=idx),
    )


class TestSMCOrderBlockSelection:
    """Swing high -> pullback to a clear low -> break above -> drift down."""

    CLOSE = np.r_[
        np.full(20, 100.0),
        np.linspace(100, 110, 10),   # rally: swing high near 110
        np.linspace(110, 100, 10),   # pullback low near 100 (the bullish block)
        np.linspace(100, 115, 10),   # break above the swing high
        np.linspace(115, 104, 20),   # drift down, staying ABOVE the pullback low
        np.linspace(104, 94, 20),    # then break below the pullback low
        np.full(10, 94.0),
    ]

    def _events(self):
        from signals.smc_signals import _structure_and_ob

        high, low, close, open_ = _ohlc(self.CLOSE)
        events, _, _ = _structure_and_ob(high, low, close, open_, size=5, prefix="t")
        return events

    def test_one_bullish_block_forms_on_the_break(self):
        formed = np.flatnonzero(self._events()["t_ob_bullish_formed"].to_numpy())
        assert len(formed) == 1 and 44 <= formed[0] <= 50, formed

    def test_block_is_not_mitigated_while_price_holds_above_the_pullback_low(self):
        """With the inverted selection the block sat at the top of the move and
        was 'mitigated' within a few bars of forming."""
        mit = np.flatnonzero(self._events()["t_ob_bullish_mitigated"].to_numpy())
        assert len(mit), "the block should be mitigated once price breaks the pullback low"
        assert mit.min() >= 70, (
            f"bullish block mitigated at bar {mit.min()}, while price was still above "
            "the pullback low -- the block candle was taken from the wrong extreme"
        )


class TestICTOrderBlockRange:
    """Pine's loop covers bars strictly between the swing bar and the break bar."""

    def test_break_bar_cannot_be_its_own_order_block(self):
        from signals.ict_signals import detect_order_blocks

        close = np.r_[
            np.full(20, 100.0),
            np.linspace(100, 110, 10),       # swing high
            np.linspace(110, 100, 10),       # pullback low: body min 100
            np.linspace(100, 108, 6),
            [112.0],                         # break bar...
            np.linspace(112, 98, 15),        # ...then drift below 100 but above 95
            np.full(10, 98.0),
        ]
        open_ = np.r_[close[0], close[:-1]]
        brk = 20 + 10 + 10 + 6
        open_[brk] = 95.0                    # ...whose body reaches down to 95
        high, low, c, o = _ohlc(close, open_, wick=0.3)
        df = pd.DataFrame({"open": o, "high": high, "low": low, "close": c})

        out = detect_order_blocks(df, length=5, use_body=True)
        assert out["ict_ob_bullish_formed"].iloc[brk], "break bar should form the block"
        # The correct block is the pullback-low candle (body low 100). The break
        # bar's own body reaches 95, so the correct block is mitigated at once, on
        # the break bar itself (Pine checks mitigation after formation on the same
        # bar). Had the break bar been taken as the block (body low 95), nothing in
        # this series trades below 95 and it could never be mitigated.
        mitigated = out["ict_ob_bullish_mitigated"].to_numpy()[brk:]
        assert mitigated.any(), (
            "the bullish block was never mitigated -- the break bar (body low 95) "
            "was taken as the block instead of the pullback low (100)"
        )
