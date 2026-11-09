"""Tests for the clean step: duplicates, impossible bars, gaps (never filled), flags."""

import json
from datetime import UTC, date, datetime

import polars as pl
import pytest

from candles.clean.bars import BARS_SCHEMA_ORDER, clean_bars, clean_instrument
from candles.config import Instrument

BTC = Instrument(
    symbol="BTC-USD", asset_class="crypto", source="coinbase", session="24x7", history_start=date(2020, 1, 1)
)
T0 = int(datetime(2024, 1, 1, tzinfo=UTC).timestamp())
F1 = datetime(2024, 2, 1, tzinfo=UTC)
F2 = datetime(2024, 3, 1, tzinfo=UTC)


def raw(rows):
    """rows: (bar index, open, high, low, close, volume, fetched_at)"""
    return pl.DataFrame(
        {
            "ts_epoch": [T0 + i * 900 for i, *_ in rows],
            "open": [r[1] for r in rows],
            "high": [r[2] for r in rows],
            "low": [r[3] for r in rows],
            "close": [r[4] for r in rows],
            "volume": [r[5] for r in rows],
            "fetched_at_utc": [r[6] for r in rows],
        },
        schema_overrides={"fetched_at_utc": pl.Datetime("us", "UTC")},
    )


def test_gaps_are_flagged_not_filled():
    df, stats = clean_bars(raw([(0, 10, 11, 9, 10, 1, F1), (1, 10, 11, 9, 10, 1, F1), (4, 10, 11, 9, 10, 1, F1)]), BTC)
    assert df.height == 3  # bars 2 and 3 stay missing
    assert df["gap_before"].to_list() == [False, False, True]
    assert df["bars_missing_before"].to_list() == [0, 0, 2]
    assert stats["gap_count"] == 1 and stats["bars_missing_total"] == 2


def test_duplicates_keep_latest_fetch():
    df, stats = clean_bars(raw([(0, 10, 11, 9, 10, 1, F1), (0, 10, 12, 9, 11, 2, F2)]), BTC)
    assert df.height == 1 and stats["duplicates_removed"] == 1
    assert df["close"][0] == 11


@pytest.mark.parametrize(
    "bad",
    [
        (1, 10, 9, 11, 10, 1, F1),  # high below low
        (1, 12, 11, 9, 10, 1, F1),  # open above high
        (1, 10, 11, 9, 8, 1, F1),  # close below low
        (1, 0, 0, 0, 0, 1, F1),  # zero price
        (1, 10, 11, 9, 10, -1, F1),  # negative volume
    ],
)
def test_impossible_bars_dropped_and_counted(bad):
    df, stats = clean_bars(raw([(0, 10, 11, 9, 10, 1, F1), bad, (2, 10, 11, 9, 10, 1, F1)]), BTC)
    assert df.height == 2 and stats["invalid_bars_dropped"] == 1
    assert df["gap_before"].to_list() == [False, True]  # a dropped bar becomes a gap


def test_zero_range_and_zero_volume_flagged_but_kept():
    df, stats = clean_bars(raw([(0, 10, 10, 10, 10, 1, F1), (1, 10, 11, 9, 10, 0, F1)]), BTC)
    assert df.height == 2
    assert df["zero_range"].to_list() == [True, False]
    assert df["zero_volume"].to_list() == [False, True]


def test_output_schema_and_utc_bar_open_time():
    df, _ = clean_bars(raw([(0, 10, 11, 9, 10, 1, F1)]), BTC)
    assert df.columns == BARS_SCHEMA_ORDER
    assert df["ts_open_utc"][0] == datetime(2024, 1, 1, tzinfo=UTC)
    assert str(df.schema["ts_open_utc"].time_zone) == "UTC"


def test_off_grid_timestamps_rejected():
    r = raw([(0, 10, 11, 9, 10, 1, F1)]).with_columns(pl.col("ts_epoch") + 60)
    with pytest.raises(ValueError, match="not aligned"):
        clean_bars(r, BTC)


def test_clean_instrument_writes_table_and_manifest(tmp_path):
    raw_dir = tmp_path / "raw" / "coinbase" / "BTC-USD"
    raw_dir.mkdir(parents=True)
    raw([]).head(0).write_parquet(raw_dir / "2023-12.parquet")  # empty pre-listing month
    raw([(0, 10, 11, 9, 10, 1, F1), (2, 10, 11, 9, 10, 1, F1)]).write_parquet(raw_dir / "2024-01.parquet")

    m = clean_instrument(BTC, tmp_path)
    assert (tmp_path / "clean" / "BTC-USD.parquet").exists()
    saved = json.loads((tmp_path / "clean" / "BTC-USD.manifest.json").read_text())
    assert saved == m
    assert m["rows"] == 2 and m["gap_count"] == 1 and len(m["output_sha256"]) == 64
