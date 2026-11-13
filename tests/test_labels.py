"""Label spot checks: computed by hand, off-by-one horizons, gaps, flat band."""

import pytest
from helpers import make_bars

from candles.config import LabelsConfig
from candles.labels.forward import build_labels

CFG = LabelsConfig(horizons=[1, 2], flat_atr=0.05)
ATR_PERIOD = 2


def flat_candles(closes, skip=()):
    # every candle has high-low = 2 around its close, so true range is easy to work out
    return make_bars([(i, c, c + 1, c - 1, c) for i, c in enumerate(closes) if i not in skip])


def test_one_bar_ahead_by_hand():
    #        idx:   0    1    2      3    4
    bars = flat_candles([100, 100, 101, 101.01, 99])
    lab = build_labels(bars, CFG, ATR_PERIOD)
    # ATR(2) needs two true ranges, so it first exists at idx 2. TR = max(2, |h-pc|, |l-pc|).
    # idx1 TR=2, idx2 TR=2 (h=102 vs pc=100) -> ATR=2;  idx3 TR=2 -> ATR=2
    assert lab["dir_1"].to_list() == [None, None, "flat", "down", None]
    assert lab["ret_pts_1"].to_list()[2] == pytest.approx(0.01)  # 101 -> 101.01
    assert lab["net_atr_1"].to_list()[2] == pytest.approx(0.01 / 2)  # under 0.05 ATR -> flat
    assert lab["ret_pts_1"].to_list()[3] == pytest.approx(-2.01)
    assert lab["ret_pct_1"].to_list()[3] == pytest.approx(-2.01 / 101.01 * 100)


def test_up_label_and_horizon_two_is_not_off_by_one():
    bars = flat_candles([100, 100, 100, 103, 99, 99])
    lab = build_labels(bars, CFG, ATR_PERIOD)
    assert lab["dir_1"].to_list()[2] == "up"  # 100 -> 103
    assert lab["ret_pts_2"].to_list()[2] == pytest.approx(-1)  # 100 -> 99, two bars on
    assert lab["dir_2"].to_list()[2] == "down"
    assert lab["dir_2"].to_list()[-2:] == [None, None]  # not enough bars left


def test_no_label_across_a_gap():
    closes = [100, 100, 100, 101, 102, 103, 104]
    whole = build_labels(flat_candles(closes), CFG, ATR_PERIOD)
    gappy = build_labels(flat_candles(closes, skip={4}), CFG, ATR_PERIOD)  # bar 4 missing
    assert whole["dir_1"].to_list()[3] == "up"
    # rows are now idx 0,1,2,3,5,6. The bar after idx 3 is missing: no label, never bridged.
    assert gappy["dir_1"].to_list()[3] is None
    assert gappy["ret_pts_1"].to_list()[3] is None
    # horizon 2 from idx 2 would pass over the hole too
    assert gappy["dir_2"].to_list()[2] is None


def test_last_bar_has_no_label():
    lab = build_labels(flat_candles([100, 100, 100, 101]), CFG, ATR_PERIOD)
    assert lab["dir_1"].to_list()[-1] is None


def test_horizon_four_and_eight_by_hand():
    #              idx: 0    1    2      3    4    5    6      7    8    9    10     11
    closes = [100, 100, 100, 100, 100, 100, 108, 100, 100, 100, 116, 100]
    cfg = LabelsConfig(horizons=[4, 8], flat_atr=0.05)
    lab = build_labels(flat_candles(closes), cfg, ATR_PERIOD)
    assert lab["ret_pts_4"].to_list()[2] == pytest.approx(8)  # idx2 100 -> idx6 108
    assert lab["dir_4"].to_list()[2] == "up"
    assert lab["ret_pts_8"].to_list()[2] == pytest.approx(16)  # idx2 100 -> idx10 116
    assert lab["dir_8"].to_list()[2] == "up"
    assert lab["dir_8"].to_list()[4:] == [None] * 8  # not enough bars left from idx4 on


def test_gap_inside_the_eight_bar_window_but_outside_the_four_bar_one():
    # idx8 is missing. From idx2, the h=4 window only reaches idx6 and never sees
    # the hole; the h=8 window reaches idx10 and passes right over it.
    closes = [100, 100, 100, 100, 100, 100, 108, 100, 100, 100, 100, 100]
    cfg = LabelsConfig(horizons=[4, 8], flat_atr=0.05)
    gappy = build_labels(flat_candles(closes, skip={8}), cfg, ATR_PERIOD)
    assert gappy["dir_4"].to_list()[2] == "up"  # idx2 100 -> idx6 108, untouched by the gap
    assert gappy["dir_8"].to_list()[2] is None  # idx2 -> idx10 crosses the missing idx8
