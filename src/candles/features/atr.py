"""ATR: the average size of recent candles, used as the project's yardstick.

True range of a bar = the largest of
    high - low,  |high - previous close|,  |low - previous close|.
ATR(n) at bar t = plain average of the true ranges of bars t-n+1 ... t.

Past-only: nothing after bar t is read.

Gaps (hard rule 6): a bar whose previous bar is missing has no true range,
and any ATR whose window contains such a bar is left empty. A plain average
is used instead of Wilder's running smoothing because the running version
carries old values across gaps, which is a quiet form of filling.
"""

from __future__ import annotations

import polars as pl


def has_prev_expr() -> pl.Expr:
    """True when the bar directly before this one exists (no gap, not the first row)."""
    return pl.col("gap_before").not_() & pl.col("close").shift(1).is_not_null()


def true_range_expr() -> pl.Expr:
    prev_close = pl.col("close").shift(1)
    tr = pl.max_horizontal(
        pl.col("high") - pl.col("low"),
        (pl.col("high") - prev_close).abs(),
        (pl.col("low") - prev_close).abs(),
    )
    return pl.when(has_prev_expr()).then(tr).otherwise(None)


def atr_expr(period: int) -> pl.Expr:
    """ATR over `period` bars; empty until `period` back-to-back true ranges exist."""
    tr = true_range_expr()
    # rolling_mean skips empty values, so count them and blank any window that has one.
    full_window = tr.is_not_null().cast(pl.Int32).rolling_sum(period, min_samples=period) == period
    return pl.when(full_window).then(tr.rolling_mean(period, min_samples=period)).otherwise(None)
