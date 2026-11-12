"""Track A classical 2-candle patterns (Design Doc 1). One written rule each.

"prev" is the first candle of the pattern, "this" is the second (bar t).
Every rule reads only those two bars, so it is past-only by construction.
The pattern is flagged on its LAST candle.

A pattern is thrown out (flag = False) when
  - the two candles are not back to back (a gap between them), or
  - either candle has zero range or zero volume.

Rules, in plain words:

bullish_engulfing  prev closed down, this closed up, and this candle's body
                   covers prev's whole body and is strictly bigger.
bearish_engulfing  the mirror image.
inside_bar         this candle's high and low both sit within prev's high-low
                   range (touching the edge counts).
outside_bar        this candle's high is above prev's high AND its low is
                   below prev's low.
"""

from __future__ import annotations

import polars as pl

from candles.features.atr import has_prev_expr

_o, _h, _l, _c = (pl.col(x) for x in ("open", "high", "low", "close"))
_po, _ph, _pl, _pc = (pl.col(x).shift(1) for x in ("open", "high", "low", "close"))

TWO_CANDLE_RULES: dict[str, pl.Expr] = {
    "bullish_engulfing": (_pc < _po) & (_c > _o) & (_o <= _pc) & (_c >= _po) & ((_c - _o) > (_po - _pc)),
    "bearish_engulfing": (_pc > _po) & (_c < _o) & (_o >= _pc) & (_c <= _po) & ((_o - _c) > (_pc - _po)),
    "inside_bar": (_h <= _ph) & (_l >= _pl),
    "outside_bar": (_h > _ph) & (_l < _pl),
}

PATTERN_PREFIX = "p2_"


def pattern_valid_expr() -> pl.Expr:
    """True when both candles exist back to back and neither is a dead bar."""
    dead = pl.col("zero_range") | pl.col("zero_volume")
    return (has_prev_expr() & dead.not_() & dead.shift(1).not_()).fill_null(False)


def two_candle_exprs(names: list[str]) -> list[pl.Expr]:
    unknown = [n for n in names if n not in TWO_CANDLE_RULES]
    if unknown:
        raise ValueError(f"no rule written for pattern(s): {unknown}")
    valid = pattern_valid_expr()
    return [(TWO_CANDLE_RULES[n] & valid).fill_null(False).alias(PATTERN_PREFIX + n) for n in names]
