"""Turn raw downloads into the standard `bars` table (Design Doc 2).

What this step does, in order:
  1. Stack all raw monthly files for one instrument.
  2. Remove duplicate bars (keep the most recently fetched copy).
  3. Drop bars that are physically impossible (high below low, open or
     close outside the high-low range, non-positive prices). These are
     counted in the manifest, not silently discarded.
  4. Flag zero-range and zero-volume bars. They stay in the table but are
     excluded from pattern discovery later.
  5. Mark `gap_before` when the previous bar is missing. Missing bars are
     NEVER filled in (CLAUDE.md hard rule 6).
  6. Write data/clean/<SYMBOL>.parquet plus a manifest JSON with row
     counts, gap counts and a checksum so the run can be reproduced.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

from candles.config import Instrument

BARS_SCHEMA_ORDER = [
    "instrument",
    "asset_class",
    "ts_open_utc",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "gap_before",
    "bars_missing_before",
    "zero_range",
    "zero_volume",
    "session",
    "exchange_tz",
    "source",
]


def _read_raw(raw_dir: Path) -> pl.DataFrame:
    files = sorted(raw_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"no raw files in {raw_dir}; run ingest first")
    frames = [pl.read_parquet(f) for f in files]
    non_empty = [f for f in frames if f.height]
    # Months before an instrument was listed are saved as empty files.
    return pl.concat(non_empty, how="vertical") if non_empty else frames[0]


def clean_bars(raw: pl.DataFrame, inst: Instrument, bar_minutes: int = 15) -> tuple[pl.DataFrame, dict]:
    """Pure function: raw rows in, clean bars + stats out. No file I/O."""
    stats: dict = {"raw_rows": raw.height}

    df = raw.sort(["ts_epoch", "fetched_at_utc"]).unique(subset="ts_epoch", keep="last").sort("ts_epoch")
    stats["duplicates_removed"] = raw.height - df.height

    valid = (
        (pl.col("high") >= pl.col("low"))
        & pl.col("open").is_between(pl.col("low"), pl.col("high"))
        & pl.col("close").is_between(pl.col("low"), pl.col("high"))
        & (pl.col("low") > 0)
        & (pl.col("volume") >= 0)
    )
    stats["invalid_bars_dropped"] = df.filter(~valid).height
    df = df.filter(valid)

    bar_s = bar_minutes * 60
    off_grid = df.filter(pl.col("ts_epoch") % bar_s != 0).height
    if off_grid:
        raise ValueError(f"{off_grid} bars are not aligned to {bar_minutes}-minute boundaries")

    step = pl.col("ts_epoch").diff()
    df = df.with_columns(
        bars_missing_before=((step // bar_s) - 1).fill_null(0).cast(pl.Int32),
    ).with_columns(
        gap_before=pl.col("bars_missing_before") > 0,
        zero_range=pl.col("high") == pl.col("low"),
        zero_volume=pl.col("volume") == 0,
        ts_open_utc=pl.from_epoch("ts_epoch", time_unit="s").dt.replace_time_zone("UTC"),
        instrument=pl.lit(inst.symbol),
        asset_class=pl.lit(inst.asset_class),
        session=pl.lit(inst.session),
        exchange_tz=pl.lit(inst.exchange_tz),
        source=pl.lit(inst.source),
    )

    out = df.select(BARS_SCHEMA_ORDER)
    stats.update(
        rows=out.height,
        first_bar_utc=str(out["ts_open_utc"].min()) if out.height else None,
        last_bar_utc=str(out["ts_open_utc"].max()) if out.height else None,
        gap_count=int(out["gap_before"].sum()),
        bars_missing_total=int(out["bars_missing_before"].sum()),
        zero_range_bars=int(out["zero_range"].sum()),
        zero_volume_bars=int(out["zero_volume"].sum()),
    )
    return out, stats


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clean_instrument(inst: Instrument, data_root: Path, bar_minutes: int = 15) -> dict:
    """Read raw files, clean them, write the clean table and its manifest."""
    raw_dir = data_root / "raw" / inst.source / inst.symbol
    raw = _read_raw(raw_dir)
    bars, stats = clean_bars(raw, inst, bar_minutes)

    clean_dir = data_root / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    out_path = clean_dir / f"{inst.symbol}.parquet"
    bars.write_parquet(out_path)

    manifest = {
        "instrument": inst.symbol,
        "asset_class": inst.asset_class,
        "source": inst.source,
        "bar_minutes": bar_minutes,
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "raw_files": sorted(p.name for p in raw_dir.glob("*.parquet")),
        **stats,
        "output_file": out_path.name,
        "output_sha256": _sha256(out_path),
    }
    (clean_dir / f"{inst.symbol}.manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
