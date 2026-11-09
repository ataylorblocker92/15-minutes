"""Download raw 15-minute candles from Coinbase's public market-data API.

No account or API key is needed. Coinbase returns at most 300 candles per
request, so a month of 15-minute bars (~2,900 bars) takes about 10 requests.

Raw files are written untouched (apart from column names) to
    data/raw/coinbase/<SYMBOL>/<YYYY-MM>.parquet
A month that is not over yet is written as <YYYY-MM>.partial.parquet and
re-downloaded on the next run. Finished months are never downloaded twice,
so the command can be stopped and restarted safely.

Coinbase leaves out any 15-minute bucket with no trades. Those gaps are
expected; the clean step records them and never fills them in.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import polars as pl
import requests

log = logging.getLogger(__name__)

BASE_URL = "https://api.exchange.coinbase.com"
MAX_CANDLES_PER_REQUEST = 300
PAUSE_BETWEEN_REQUESTS_S = 0.2  # public limit is ~10 req/s; stay well under it
MAX_RETRIES = 6

RAW_SCHEMA = {
    "ts_epoch": pl.Int64,  # bucket start, seconds since 1970 UTC
    "open": pl.Float64,
    "high": pl.Float64,
    "low": pl.Float64,
    "close": pl.Float64,
    "volume": pl.Float64,  # in units of the base currency (e.g. BTC)
    "fetched_at_utc": pl.Datetime("us", "UTC"),
}

# A getter takes (url, params) and returns parsed JSON. Swappable in tests.
Getter = Callable[[str, dict], list]


def http_getter(session: requests.Session | None = None) -> Getter:
    """Real HTTP getter with retry and backoff for rate limits and server errors."""
    s = session or requests.Session()
    s.headers.update({"User-Agent": "15-minutes-research/0.1"})

    def get(url: str, params: dict) -> list:
        wait = 1.0
        for attempt in range(1, MAX_RETRIES + 1):
            resp = s.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 429 or resp.status_code >= 500:
                log.warning("HTTP %s (attempt %s), waiting %.0fs", resp.status_code, attempt, wait)
                time.sleep(wait)
                wait = min(wait * 2, 60)
                continue
            resp.raise_for_status()
        raise RuntimeError(f"gave up after {MAX_RETRIES} tries: {url} {params}")

    return get


def _windows(start: datetime, end: datetime, bar_s: int) -> Iterator[tuple[datetime, datetime]]:
    """Split [start, end) into request windows of at most 300 bars each.

    Each window is (first_bar_start, last_bar_start), both inclusive, which is
    how Coinbase's start/end parameters behave.
    """
    step = timedelta(seconds=bar_s * MAX_CANDLES_PER_REQUEST)
    cur = start
    while cur < end:
        last = min(cur + step, end) - timedelta(seconds=bar_s)
        yield cur, last
        cur = last + timedelta(seconds=bar_s)


def fetch_range(
    symbol: str,
    start: datetime,
    end: datetime,
    bar_minutes: int = 15,
    get: Getter | None = None,
    pause_s: float = PAUSE_BETWEEN_REQUESTS_S,
) -> pl.DataFrame:
    """All candles whose bar-open time is in [start, end), oldest first."""
    get = get or http_getter()
    bar_s = bar_minutes * 60
    rows: list[list] = []
    for first, last in _windows(start, end, bar_s):
        data = get(
            f"{BASE_URL}/products/{symbol}/candles",
            {"granularity": bar_s, "start": first.isoformat(), "end": last.isoformat()},
        )
        # Each row from Coinbase: [time, low, high, open, close, volume]
        rows.extend(data)
        if pause_s:
            time.sleep(pause_s)

    fetched_at = datetime.now(UTC)
    if not rows:
        return pl.DataFrame(schema=RAW_SCHEMA)

    df = pl.DataFrame(
        {
            "ts_epoch": [int(r[0]) for r in rows],
            "open": [float(r[3]) for r in rows],
            "high": [float(r[2]) for r in rows],
            "low": [float(r[1]) for r in rows],
            "close": [float(r[4]) for r in rows],
            "volume": [float(r[5]) for r in rows],
        }
    ).with_columns(pl.lit(fetched_at).cast(pl.Datetime("us", "UTC")).alias("fetched_at_utc"))

    lo, hi = int(start.timestamp()), int(end.timestamp())
    return (
        df.filter((pl.col("ts_epoch") >= lo) & (pl.col("ts_epoch") < hi))
        .unique(subset="ts_epoch", keep="last")
        .sort("ts_epoch")
    )


def _month_starts(first: date, last_exclusive: datetime) -> Iterator[datetime]:
    cur = datetime(first.year, first.month, 1, tzinfo=UTC)
    while cur < last_exclusive:
        yield cur
        cur = datetime(cur.year + (cur.month == 12), cur.month % 12 + 1, 1, tzinfo=UTC)


def download_symbol(
    symbol: str,
    history_start: date,
    raw_root: Path,
    bar_minutes: int = 15,
    now: datetime | None = None,
    get: Getter | None = None,
    pause_s: float = PAUSE_BETWEEN_REQUESTS_S,
) -> dict:
    """Download every month from history_start up to the newest finished bar.

    Returns a small summary: months downloaded, months skipped, bars written.
    """
    now = now or datetime.now(UTC)
    bar_s = bar_minutes * 60
    # Newest finished bar: the bucket containing `now` is still forming, so stop before it.
    cutoff = datetime.fromtimestamp((int(now.timestamp()) // bar_s) * bar_s, UTC)

    out_dir = raw_root / "coinbase" / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {"symbol": symbol, "months_downloaded": 0, "months_skipped": 0, "bars_written": 0}

    for month_start in _month_starts(history_start, cutoff):
        month_end = datetime(
            month_start.year + (month_start.month == 12), month_start.month % 12 + 1, 1, tzinfo=UTC
        )
        tag = month_start.strftime("%Y-%m")
        final_path = out_dir / f"{tag}.parquet"
        partial_path = out_dir / f"{tag}.partial.parquet"

        if final_path.exists():
            summary["months_skipped"] += 1
            continue

        finished = month_end <= cutoff
        df = fetch_range(symbol, month_start, min(month_end, cutoff), bar_minutes, get, pause_s)

        if finished:
            df.write_parquet(final_path)
            partial_path.unlink(missing_ok=True)
        else:
            df.write_parquet(partial_path)

        summary["months_downloaded"] += 1
        summary["bars_written"] += df.height
        log.info("%s %s: %s bars%s", symbol, tag, df.height, "" if finished else " (month in progress)")

    return summary
