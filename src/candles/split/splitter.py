"""Cut clean bars into discovery / validation / holdout by date (Design Doc 2, module 3).

Reads   data/clean/<SYMBOL>.parquet
Writes  data/discovery/<SYMBOL>.parquet
        data/validation/<SYMBOL>.parquet
        vault/holdout/<SYMBOL>.parquet     (written, never read back)
        plus a small manifest JSON beside each file.

Bars that fall in an embargo day are dropped from every block, so a forward
label near the end of one block can never reach into the next.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

import polars as pl

from candles.config import SplitsConfig
from candles.vault import HoldoutLockedError

OpenSplit = Literal["discovery", "validation"]
OPEN_SPLITS: tuple[str, ...] = ("discovery", "validation")


def _utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day, tzinfo=UTC)


def split_bars(bars: pl.DataFrame, cfg: SplitsConfig) -> dict[str, pl.DataFrame]:
    """Pure function: clean bars in, three blocks out. No file I/O."""
    ts = pl.col("ts_open_utc")
    return {
        "discovery": bars.filter(ts < _utc(cfg.discovery_end)),
        "validation": bars.filter((ts >= _utc(cfg.validation_start)) & (ts < _utc(cfg.validation_end))),
        "holdout": bars.filter(ts >= _utc(cfg.holdout_start)),
    }


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def split_instrument(symbol: str, data_root: Path, cfg: SplitsConfig) -> dict:
    """Split one instrument's clean file and write all three blocks."""
    clean_path = data_root / "clean" / f"{symbol}.parquet"
    if not clean_path.exists():
        raise FileNotFoundError(f"{clean_path} not found; run `candles clean` first")
    bars = pl.read_parquet(clean_path)
    blocks = split_bars(bars, cfg)

    out_dirs = {
        "discovery": data_root / "discovery",
        "validation": data_root / "validation",
        "holdout": Path(cfg.vault_root),
    }
    summary: dict = {"symbol": symbol, "clean_rows": bars.height, "clean_sha256": _sha256(clean_path)}
    for name, df in blocks.items():
        out_dir = out_dirs[name]
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{symbol}.parquet"
        df.write_parquet(out_path)
        info = {
            "instrument": symbol,
            "split": name,
            "rows": df.height,
            "first_bar_utc": str(df["ts_open_utc"].min()) if df.height else None,
            "last_bar_utc": str(df["ts_open_utc"].max()) if df.height else None,
            "discovery_end": str(cfg.discovery_end),
            "validation_end": str(cfg.validation_end),
            "embargo_days": cfg.embargo_days,
            "source_clean_sha256": summary["clean_sha256"],
            "output_sha256": _sha256(out_path),
            "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        (out_dir / f"{symbol}.manifest.json").write_text(json.dumps(info, indent=2))
        summary[name] = info
    summary["embargo_rows_dropped"] = bars.height - sum(df.height for df in blocks.values())
    return summary


def split_path(data_root: Path, split: str, symbol: str) -> Path:
    """Path to an OPEN split file. The holdout is not reachable from here."""
    if split not in OPEN_SPLITS:
        raise HoldoutLockedError(
            f"split '{split}' is not readable here. Only {OPEN_SPLITS} are open; "
            "the holdout goes through candles.vault.read_holdout with --unlock-holdout."
        )
    return data_root / split / f"{symbol}.parquet"


def read_split(data_root: Path, split: str, symbol: str) -> pl.DataFrame:
    """Read discovery or validation bars for one instrument."""
    path = split_path(data_root, split, symbol)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found; run `candles split` first")
    return pl.read_parquet(path)
