"""Shared test helper: build a small clean-bars table by hand."""

from datetime import UTC, datetime, timedelta

import polars as pl

T0 = datetime(2024, 1, 1, tzinfo=UTC)
BAR = timedelta(minutes=15)


def make_bars(rows, start: datetime = T0) -> pl.DataFrame:
    """rows: (bar index, open, high, low, close[, volume]). Missing indexes become gaps."""
    idx = [r[0] for r in rows]
    missing = [0] + [b - a - 1 for a, b in zip(idx, idx[1:])]
    return pl.DataFrame(
        {
            "instrument": ["BTC-USD"] * len(rows),
            "asset_class": ["crypto"] * len(rows),
            "ts_open_utc": [start + i * BAR for i in idx],
            "open": [float(r[1]) for r in rows],
            "high": [float(r[2]) for r in rows],
            "low": [float(r[3]) for r in rows],
            "close": [float(r[4]) for r in rows],
            "volume": [float(r[5]) if len(r) > 5 else 1.0 for r in rows],
            "gap_before": [m > 0 for m in missing],
            "bars_missing_before": missing,
            "zero_range": [r[2] == r[3] for r in rows],
            "zero_volume": [(r[5] if len(r) > 5 else 1.0) == 0 for r in rows],
            "session": ["24x7"] * len(rows),
            "exchange_tz": ["UTC"] * len(rows),
            "source": ["coinbase"] * len(rows),
        },
        schema_overrides={"ts_open_utc": pl.Datetime("us", "UTC"), "bars_missing_before": pl.Int32},
    )


def random_bars(rng, n: int, drop: set[int] = frozenset()) -> pl.DataFrame:
    """A random walk of n candles; indexes in `drop` are left out to make gaps."""
    rows, price = [], 100.0
    for i in range(n):
        o = price
        c = o + rng.normal(0, 1)
        h = max(o, c) + abs(rng.normal(0, 0.5))
        lo = min(o, c) - abs(rng.normal(0, 0.5))
        price = c
        if i not in drop:
            rows.append((i, o, h, lo, c, 1.0))
    return make_bars(rows)
