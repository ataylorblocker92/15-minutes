"""Up-vs-down hit rate per pattern (first, simple version of Design Doc 2 module 6).

Reads   data/features/<split>/ + data/labels/<split>/
Writes  results/patterns/<run_id>/hit_rate_<SYMBOL>_<split>.parquet
        and appends one row per test to results/test_registry.parquet

For each pattern and horizon:
    hit_rate_up = ups / (ups + downs)          flat moves are counted separately
    edge        = hit_rate_up - base rate      base rate = same thing over ALL labelled bars
    p_value     = two-sided binomial test of the pattern's up-count against the base rate

Known simplifications (not yet what Design Doc 1 asks for):
  - the base rate is not matched by time of day;
  - the p-value treats occurrences as independent (no clustering by day);
  - no false-discovery correction yet (adjusted_p stays empty).
So p-values here are rough and somewhat too optimistic.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl
from scipy.stats import binomtest

from candles.features.patterns import PATTERN_PREFIX

BASELINE = "ALL_BARS"
TEST_NAME = "binomial_two_sided_vs_base_rate"


def _counts(df: pl.DataFrame, dir_col: str) -> dict:
    vc = dict(df[dir_col].value_counts().iter_rows())
    up, down, flat = vc.get("up", 0), vc.get("down", 0), vc.get("flat", 0)
    return {
        "n": up + down + flat,
        "n_up": up,
        "n_down": down,
        "n_flat": flat,
        "hit_rate_up": up / (up + down) if up + down else None,
    }


def hit_rate_table(
    features: pl.DataFrame, labels: pl.DataFrame, horizons: list[int], min_occurrences: int
) -> pl.DataFrame:
    """Pure function: one row per pattern x horizon, plus a baseline row per horizon."""
    patterns = [c for c in features.columns if c.startswith(PATTERN_PREFIX)]
    df = features.join(labels, on=["instrument", "ts_open_utc"], how="inner", validate="1:1")
    rows: list[dict] = []
    for h in horizons:
        dir_col = f"dir_{h}"
        labelled = df.filter(pl.col(dir_col).is_not_null())
        base = _counts(labelled, dir_col)
        base_rate = base["hit_rate_up"]
        rows.append({"pattern": BASELINE, "horizon": h, **base, "base_rate_up": base_rate,
                     "edge": None, "p_value": None, "tested": False})  # fmt: skip
        for p in patterns:
            c = _counts(labelled.filter(pl.col(p)), dir_col)
            decided = c["n_up"] + c["n_down"]
            tested = c["n"] >= min_occurrences and decided > 0 and base_rate is not None
            rows.append(
                {
                    "pattern": p.removeprefix(PATTERN_PREFIX),
                    "horizon": h,
                    **c,
                    "base_rate_up": base_rate,
                    "edge": c["hit_rate_up"] - base_rate if tested else None,
                    "p_value": binomtest(c["n_up"], decided, base_rate).pvalue if tested else None,
                    "tested": tested,
                }
            )
    return pl.DataFrame(
        rows,
        schema_overrides={"hit_rate_up": pl.Float64, "base_rate_up": pl.Float64,
                          "edge": pl.Float64, "p_value": pl.Float64},  # fmt: skip
    )


def registry_rows(table: pl.DataFrame, instrument: str, split: str) -> list[dict]:
    """One registry row for each test that was actually run."""
    return [
        {
            "instrument": instrument,
            "pattern": r["pattern"],
            "horizon": r["horizon"],
            "context": "none",
            "split": split,
            "test": TEST_NAME,
            "n_obs": r["n_up"] + r["n_down"],
            "effect": r["edge"],
            "p_value": r["p_value"],
        }
        for r in table.filter(pl.col("tested")).iter_rows(named=True)
    ]


def result_path(results_root: Path, run_id: str, symbol: str, split: str) -> Path:
    return results_root / "patterns" / run_id / f"hit_rate_{symbol}_{split}.parquet"
