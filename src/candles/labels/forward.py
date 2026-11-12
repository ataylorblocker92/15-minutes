"""Forward-looking targets (Design Doc 2, module 5).

THIS IS THE ONLY MODULE THAT LOOKS FORWARD IN TIME (hard rule 3). Its output
must never be read by `features` or by the backtester's entry/exit logic.

Reads   data/<split>/<SYMBOL>.parquet
Writes  data/labels/<split>/<SYMBOL>.parquet

For each bar t and horizon h (in candles), measured close to close:
    ret_pts_h   close(t+h) - close(t)                  raw price points
    ret_pct_h   that move as a percent of close(t)
    net_atr_h   that move in ATR multiples
    dir_h       "up" / "down", or "flat" if |move| < flat_atr x ATR

No label is produced when any of the next h bars is missing (never bridge a
gap), when the split ends first, or when ATR at t is not available.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from candles.config import LabelsConfig
from candles.features.atr import atr_expr
from candles.split.splitter import read_split

KEYS = ["instrument", "ts_open_utc"]


def _path_clear_expr(h: int) -> pl.Expr:
    """True when bars t+1 ... t+h all exist back to back."""
    clear = pl.lit(True)
    for k in range(1, h + 1):
        # shift(-k) is empty past the end of the data, which makes the whole thing empty
        clear = clear & pl.col("gap_before").shift(-k).not_()
    return clear.fill_null(False)


def build_labels(bars: pl.DataFrame, cfg: LabelsConfig, atr_period: int) -> pl.DataFrame:
    """Pure function: bars in, one label row per bar out."""
    bars = bars.sort("ts_open_utc")
    atr = atr_expr(atr_period)
    cols: list[pl.Expr] = []
    for h in cfg.horizons:
        move = pl.when(_path_clear_expr(h)).then(pl.col("close").shift(-h) - pl.col("close")).otherwise(None)
        net_atr = move / atr
        direction = (
            pl.when(net_atr.is_null())
            .then(None)
            .when(net_atr.abs() < cfg.flat_atr)
            .then(pl.lit("flat"))
            .when(net_atr > 0)
            .then(pl.lit("up"))
            .otherwise(pl.lit("down"))
        )
        cols += [
            direction.alias(f"dir_{h}"),
            net_atr.alias(f"net_atr_{h}"),
            move.alias(f"ret_pts_{h}"),
            (move / pl.col("close") * 100).alias(f"ret_pct_{h}"),
        ]
    return bars.select(*KEYS, *cols)


def labels_path(data_root: Path, split: str, symbol: str) -> Path:
    return data_root / "labels" / split / f"{symbol}.parquet"


def build_labels_for(
    symbol: str, split: str, data_root: Path, cfg: LabelsConfig, atr_period: int
) -> pl.DataFrame:
    labels = build_labels(read_split(data_root, split, symbol), cfg, atr_period)
    out = labels_path(data_root, split, symbol)
    out.parent.mkdir(parents=True, exist_ok=True)
    labels.write_parquet(out)
    return labels
