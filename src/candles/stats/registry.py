"""The test registry: one row for every statistical test ever run (hard rule 5).

Append-only. Rows are never edited or deleted, because the false-discovery
correction needs the true number of tests that were tried.
"""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

REGISTRY_SCHEMA = {
    "test_id": pl.String,
    "run_id": pl.String,
    "timestamp": pl.Datetime("us", "UTC"),
    "instrument": pl.String,
    "pattern": pl.String,
    "horizon": pl.Int32,
    "context": pl.String,
    "split": pl.String,
    "test": pl.String,
    "n_obs": pl.Int64,
    "effect": pl.Float64,
    "p_value": pl.Float64,
    "adjusted_p": pl.Float64,  # filled by the FDR step later; empty until then
    "config_hash": pl.String,
}


def append_tests(registry_path: Path, tests: list[dict], run_id: str, config_hash: str) -> int:
    """Add rows to the registry. Returns the total row count afterwards."""
    now = datetime.now(UTC)
    new = pl.DataFrame(
        [
            {
                "test_id": uuid.uuid4().hex,
                "run_id": run_id,
                "timestamp": now,
                "adjusted_p": None,
                "config_hash": config_hash,
                **t,
            }
            for t in tests
        ],
        schema=REGISTRY_SCHEMA,
    )
    registry_path = Path(registry_path)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    if registry_path.exists():
        old = pl.read_parquet(registry_path)
        combined = pl.concat([old, new], how="diagonal_relaxed")
        if combined.height != old.height + new.height:
            raise RuntimeError("registry append would lose rows; refusing to write")
    else:
        combined = new
    # Write beside the real file, then swap, so a crash can't leave a half-written registry.
    tmp = registry_path.with_suffix(".tmp.parquet")
    combined.write_parquet(tmp)
    os.replace(tmp, registry_path)
    return combined.height
