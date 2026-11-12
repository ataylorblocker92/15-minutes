"""Hit-rate table arithmetic and the append-only test registry (hard rule 5)."""

from datetime import timedelta

import polars as pl
import pytest
from helpers import T0
from scipy.stats import binomtest

from candles.stats.hit_rate import hit_rate_table, registry_rows
from candles.stats.registry import append_tests


def tables(dirs, flags):
    ts = [T0 + timedelta(minutes=15 * i) for i in range(len(dirs))]
    keys = {"instrument": ["BTC-USD"] * len(dirs), "ts_open_utc": ts}
    return pl.DataFrame({**keys, "p2_demo": flags}), pl.DataFrame({**keys, "dir_1": dirs})


def test_hit_rate_arithmetic():
    # 10 bars: pattern on the first 5 (4 up, 1 down); the rest 1 up, 3 down, 1 flat
    dirs = ["up", "up", "up", "up", "down", "up", "down", "down", "down", "flat"]
    feats, labs = tables(dirs, [True] * 5 + [False] * 5)
    t = hit_rate_table(feats, labs, [1], min_occurrences=5)
    base, demo = t.row(0, named=True), t.row(1, named=True)

    assert (base["pattern"], base["n"], base["n_up"], base["n_down"], base["n_flat"]) == ("ALL_BARS", 10, 5, 4, 1)
    assert base["hit_rate_up"] == pytest.approx(5 / 9)
    assert (demo["n"], demo["n_up"], demo["n_down"]) == (5, 4, 1)
    assert demo["hit_rate_up"] == pytest.approx(0.8)
    assert demo["edge"] == pytest.approx(0.8 - 5 / 9)
    assert demo["p_value"] == pytest.approx(binomtest(4, 5, 5 / 9).pvalue)


def test_unlabelled_bars_are_left_out():
    feats, labs = tables(["up", None, "down", None], [True, True, True, True])
    t = hit_rate_table(feats, labs, [1], min_occurrences=1)
    assert t.row(1, named=True)["n"] == 2


def test_rare_pattern_is_listed_but_not_tested():
    feats, labs = tables(["up", "down", "up", "down"], [True, True, False, False])
    t = hit_rate_table(feats, labs, [1], min_occurrences=300)
    demo = t.row(1, named=True)
    assert demo["n"] == 2 and demo["tested"] is False and demo["p_value"] is None
    assert registry_rows(t, "BTC-USD", "discovery") == []  # nothing run, nothing logged


def test_registry_is_append_only(tmp_path):
    feats, labs = tables(["up", "up", "down", "up"], [True, True, True, False])
    t = hit_rate_table(feats, labs, [1], min_occurrences=1)
    rows = registry_rows(t, "BTC-USD", "discovery")
    assert len(rows) == 1 and rows[0]["pattern"] == "demo" and rows[0]["n_obs"] == 3

    path = tmp_path / "test_registry.parquet"
    assert append_tests(path, rows, "run-a", "cfg") == 1
    first = pl.read_parquet(path)
    assert append_tests(path, rows, "run-b", "cfg") == 2
    both = pl.read_parquet(path)

    assert both.head(1).equals(first)  # the earlier row is untouched
    assert both["run_id"].to_list() == ["run-a", "run-b"]
    assert both["test_id"].n_unique() == 2
    assert both["adjusted_p"].to_list() == [None, None]
