"""Build the features table for one split (Design Doc 2, module 4).

Reads   data/<split>/<SYMBOL>.parquet
Writes  data/features/<split>/<SYMBOL>.parquet

Hard rule 2: a feature at bar t reads bars <= t only.
Hard rule 3: this module must never import or read anything from `labels`.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

from candles.config import PatternsConfig
from candles.features.atr import atr_expr
from candles.features.patterns import pattern_valid_expr, two_candle_exprs
from candles.split.splitter import read_split

KEYS = ["instrument", "ts_open_utc"]


def build_features(bars: pl.DataFrame, cfg: PatternsConfig) -> pl.DataFrame:
    """Pure function: bars in, one feature row per bar out."""
    bars = bars.sort("ts_open_utc")
    return bars.select(
        *KEYS,
        atr_expr(cfg.atr_period).alias(f"atr{cfg.atr_period}"),
        pattern_valid_expr().alias("pattern_valid"),
        *two_candle_exprs(cfg.two_candle),
    )


def features_path(data_root: Path, split: str, symbol: str) -> Path:
    return data_root / "features" / split / f"{symbol}.parquet"


def build_features_for(symbol: str, split: str, data_root: Path, cfg: PatternsConfig) -> pl.DataFrame:
    feats = build_features(read_split(data_root, split, symbol), cfg)
    out = features_path(data_root, split, symbol)
    out.parent.mkdir(parents=True, exist_ok=True)
    feats.write_parquet(out)
    return feats
