"""Tests for the split step and the holdout lock (hard rule 1)."""

import json
from datetime import UTC, date, datetime

import polars as pl
import pytest
from helpers import BAR, make_bars

from candles.config import SplitsConfig
from candles.split.splitter import read_split, split_bars, split_instrument, split_path
from candles.vault import HoldoutLockedError, read_holdout

CFG = SplitsConfig(discovery_end=date(2024, 1, 3), validation_end=date(2024, 1, 6), embargo_days=1)


def six_days():
    # one bar every 15 minutes, 2024-01-01 00:00 through 2024-01-08 23:45
    return make_bars([(i, 10, 11, 9, 10) for i in range(8 * 96)])


def test_blocks_respect_dates_and_embargo():
    blocks = split_bars(six_days(), CFG)
    d, v, h = (blocks[k]["ts_open_utc"] for k in ("discovery", "validation", "holdout"))
    assert d.max() == datetime(2024, 1, 2, 23, 45, tzinfo=UTC)  # day 3 is embargo
    assert v.min() == datetime(2024, 1, 4, tzinfo=UTC)
    assert v.max() == datetime(2024, 1, 5, 23, 45, tzinfo=UTC)  # day 6 is embargo
    assert h.min() == datetime(2024, 1, 7, tzinfo=UTC)
    # two full days dropped, nothing duplicated
    assert len(d) + len(v) + len(h) == 8 * 96 - 2 * 96
    assert v.min() - d.max() > 8 * BAR  # an 8-bar label can't reach across


def test_boundaries_must_be_in_order():
    with pytest.raises(ValueError):
        SplitsConfig(discovery_end=date(2024, 1, 5), validation_end=date(2024, 1, 5))


def _write_and_split(tmp_path):
    cfg = CFG.model_copy(update={"vault_root": tmp_path / "vault" / "holdout"})
    (tmp_path / "clean").mkdir()
    six_days().write_parquet(tmp_path / "clean" / "BTC-USD.parquet")
    return cfg, split_instrument("BTC-USD", tmp_path, cfg)


def test_split_writes_three_blocks_with_manifests(tmp_path):
    cfg, summary = _write_and_split(tmp_path)
    assert read_split(tmp_path, "discovery", "BTC-USD").height == 2 * 96
    assert read_split(tmp_path, "validation", "BTC-USD").height == 2 * 96
    assert (cfg.vault_root / "BTC-USD.parquet").exists()
    assert summary["embargo_rows_dropped"] == 2 * 96
    m = json.loads((tmp_path / "discovery" / "BTC-USD.manifest.json").read_text())
    assert m["rows"] == 2 * 96 and len(m["output_sha256"]) == 64


def test_holdout_is_not_reachable_through_the_normal_reader(tmp_path):
    _write_and_split(tmp_path)
    for name in ("holdout", "vault", "../vault/holdout"):
        with pytest.raises(HoldoutLockedError):
            split_path(tmp_path, name, "BTC-USD")
        with pytest.raises(HoldoutLockedError):
            read_split(tmp_path, name, "BTC-USD")


def test_holdout_read_without_unlock_raises_and_is_logged(tmp_path):
    cfg, _ = _write_and_split(tmp_path)
    log_dir = tmp_path / "results"
    with pytest.raises(HoldoutLockedError):
        read_holdout(cfg.vault_root, "BTC-USD", unlock=False, reason="test peek", log_dir=log_dir)
    # truthy-but-not-True must not open it either
    with pytest.raises(HoldoutLockedError):
        read_holdout(cfg.vault_root, "BTC-USD", unlock="yes", reason="test peek", log_dir=log_dir)
    entries = [json.loads(x) for x in (log_dir / "holdout_access.log").read_text().splitlines()]
    assert [e["allowed"] for e in entries] == [False, False]


def test_holdout_read_with_unlock_works_and_is_logged(tmp_path):
    cfg, _ = _write_and_split(tmp_path)
    log_dir = tmp_path / "results"
    df = read_holdout(cfg.vault_root, "BTC-USD", unlock=True, reason="final test", log_dir=log_dir)
    assert isinstance(df, pl.DataFrame) and df.height == 2 * 96
    entry = json.loads((log_dir / "holdout_access.log").read_text().splitlines()[-1])
    assert entry["allowed"] is True and entry["reason"] == "final test"
