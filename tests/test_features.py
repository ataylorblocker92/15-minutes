"""Tests for features: future-shift (hard rule 2), hand-checked patterns, gap handling."""

from pathlib import Path

import numpy as np
import polars as pl
import pytest
from helpers import make_bars, random_bars
from hypothesis import given, settings
from hypothesis import strategies as st

from candles.config import PatternsConfig
from candles.features.build import build_features
from candles.features.patterns import TWO_CANDLE_RULES

CFG = PatternsConfig(atr_period=3, min_occurrences=300, two_candle=list(TWO_CANDLE_RULES))
CFG14 = CFG.model_copy(update={"atr_period": 14})


# ---------- hard rule 2: features at bar t must not depend on anything after t ----------


@settings(max_examples=40, deadline=None)
@given(seed=st.integers(0, 10_000), t=st.integers(0, 79))
def test_future_shift_every_feature(seed, t):
    rng = np.random.default_rng(seed)
    bars = random_bars(rng, 80, drop={20, 21, 50})
    before = build_features(bars, CFG14)

    # Replace every bar AFTER row t with different random candles (same timestamps).
    other = random_bars(np.random.default_rng(seed + 1), 80, drop={20, 21, 50})
    price_cols = ["open", "high", "low", "close", "volume", "zero_range", "zero_volume"]
    keep = pl.int_range(pl.len()) <= t
    scrambled = bars.with_columns(
        [pl.when(keep).then(pl.col(c)).otherwise(other[c]).alias(c) for c in price_cols]
    )
    after = build_features(scrambled, CFG14)

    assert before.head(t + 1).equals(after.head(t + 1))


# ---------- hand-checked patterns ----------


def flags(rows, name):
    return build_features(make_bars(rows), CFG)["p2_" + name].to_list()


def test_bullish_engulfing_by_hand():
    # prev: down candle 10 -> 9.  this: up candle 8.9 -> 10.2, body covers prev's body.
    assert flags([(0, 10, 10.1, 8.9, 9), (1, 8.9, 10.3, 8.8, 10.2)], "bullish_engulfing") == [False, True]
    # this candle is up but does not reach prev's open: not engulfing
    assert flags([(0, 10, 10.1, 8.9, 9), (1, 8.9, 9.9, 8.8, 9.8)], "bullish_engulfing") == [False, False]
    # prev was an up candle: not a bullish engulfing
    assert flags([(0, 9, 10.1, 8.9, 10), (1, 8.9, 10.3, 8.8, 10.2)], "bullish_engulfing") == [False, False]


def test_bearish_engulfing_by_hand():
    # prev: up 9 -> 10.  this: down 10.1 -> 8.8.
    assert flags([(0, 9, 10.1, 8.9, 10), (1, 10.1, 10.2, 8.7, 8.8)], "bearish_engulfing") == [False, True]
    assert flags([(0, 9, 10.1, 8.9, 10), (1, 10.1, 10.2, 9.1, 9.2)], "bearish_engulfing") == [False, False]


def test_inside_and_outside_bar_by_hand():
    prev = (0, 10, 12, 8, 11)
    inside = (1, 11, 11.5, 9, 10)
    outside = (1, 11, 12.5, 7.5, 10)
    neither = (1, 11, 12.5, 9, 10)  # higher high but not a lower low
    assert flags([prev, inside], "inside_bar") == [False, True]
    assert flags([prev, inside], "outside_bar") == [False, False]
    assert flags([prev, outside], "outside_bar") == [False, True]
    assert flags([prev, outside], "inside_bar") == [False, False]
    assert flags([prev, neither], "inside_bar") == [False, False]
    assert flags([prev, neither], "outside_bar") == [False, False]


# ---------- hard rule 6: a pattern that spans a gap is discarded ----------


def test_pattern_spanning_a_gap_is_discarded():
    prev, this = (0, 10, 12, 8, 11), (1, 11, 11.5, 9, 10)
    assert flags([prev, this], "inside_bar") == [False, True]
    gapped = (3, 11, 11.5, 9, 10)  # same candle, but bars 1 and 2 are missing
    f = build_features(make_bars([prev, gapped]), CFG)
    assert f["p2_inside_bar"].to_list() == [False, False]
    assert f["pattern_valid"].to_list() == [False, False]


@pytest.mark.parametrize("dead", ["zero_range_prev", "zero_volume_prev", "zero_volume_this"])
def test_dead_bars_are_excluded(dead):
    prev, this = [0, 10, 12, 8, 11, 1.0], [1, 11, 11.5, 9, 10, 1.0]
    if dead == "zero_range_prev":
        prev = [0, 10, 10, 10, 10, 1.0]
        this = [1, 10, 10, 10, 10, 1.0]  # would be an inside bar by the numbers
    elif dead == "zero_volume_prev":
        prev[5] = 0.0
    else:
        this[5] = 0.0
    assert flags([tuple(prev), tuple(this)], "inside_bar") == [False, False]


# ---------- ATR ----------


def test_atr_by_hand():
    # true ranges after bar 0: 2 (h-l), 3 (|h - prev close|), 4 (|l - prev close|)
    bars = make_bars([(0, 10, 11, 9, 10), (1, 10, 11, 9, 10), (2, 12, 13, 12, 12.5), (3, 9, 9.5, 8.5, 9)])
    atr = build_features(bars, CFG)["atr3"].to_list()
    assert atr[:3] == [None, None, None]
    assert atr[3] == pytest.approx((2 + 3 + 4) / 3)


def test_atr_is_blank_until_window_is_clear_of_gaps():
    rows = [(i, 10, 11, 9, 10) for i in (0, 1, 2, 3, 4, 7, 8, 9, 10)]  # bars 5, 6 missing
    atr = build_features(make_bars(rows), CFG)["atr3"].to_list()
    #      idx: 0     1     2     3    4    7     8     9     10
    assert [a is not None for a in atr] == [False, False, False, True, True, False, False, False, True]


# ---------- hard rule 3: features never touch labels ----------


def test_features_package_does_not_import_labels():
    src = Path(__file__).parents[1] / "src" / "candles" / "features"
    for f in src.glob("*.py"):
        assert "labels" not in f.read_text().replace("never import or read anything from `labels`", "")


def test_feature_columns_contain_no_label_columns():
    cols = build_features(random_bars(np.random.default_rng(0), 30), CFG).columns
    assert not [c for c in cols if c.startswith(("dir_", "net_atr_", "ret_", "mfe_", "mae_"))]
