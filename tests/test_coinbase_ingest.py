"""Tests for the Coinbase downloader, using a fake exchange instead of the network."""

from datetime import UTC, date, datetime

import polars as pl
import pytest

from candles.ingest import coinbase

BAR_S = 900


class FakeCoinbase:
    """Mimics the /candles endpoint: inclusive start/end, max 300 rows, newest first,
    and no row for buckets with no trades."""

    def __init__(self, first: datetime, last: datetime, missing: set[int] = frozenset()):
        self.first, self.last = int(first.timestamp()), int(last.timestamp())
        self.missing = set(missing)
        self.calls: list[dict] = []

    def __call__(self, url: str, params: dict) -> list:
        self.calls.append(params)
        assert params["granularity"] == BAR_S
        s = int(datetime.fromisoformat(params["start"]).timestamp())
        e = int(datetime.fromisoformat(params["end"]).timestamp())
        assert (e - s) // BAR_S + 1 <= 300, "asked for more than 300 candles"
        rows = []
        for t in range(max(s, self.first), min(e, self.last) + 1, BAR_S):
            if t in self.missing:
                continue
            p = 100 + (t // BAR_S) % 7
            rows.append([t, p - 1, p + 1, p, p + 0.5, 10.0])  # time, low, high, open, close, volume
        return sorted(rows, reverse=True)


def ts(*a) -> datetime:
    return datetime(*a, tzinfo=UTC)


def test_windows_cover_range_without_overlap():
    start, end = ts(2024, 1, 1), ts(2024, 1, 10)
    wins = list(coinbase._windows(start, end, BAR_S))
    assert wins[0][0] == start
    for (a0, a1), (b0, _) in zip(wins, wins[1:]):
        assert (b0 - a1).total_seconds() == BAR_S  # next window starts one bar later
        assert (a1 - a0).total_seconds() / BAR_S + 1 <= 300
    assert (end - wins[-1][1]).total_seconds() == BAR_S


def test_fetch_range_returns_every_bar_oldest_first():
    fake = FakeCoinbase(ts(2024, 1, 1), ts(2024, 2, 1))
    df = coinbase.fetch_range("BTC-USD", ts(2024, 1, 1), ts(2024, 1, 8), get=fake, pause_s=0)
    assert df.height == 7 * 96  # 96 fifteen-minute bars per day
    assert df["ts_epoch"].is_sorted()
    assert df["ts_epoch"].n_unique() == df.height
    assert set(df.columns) == set(coinbase.RAW_SCHEMA)


def test_fetch_range_keeps_gaps_as_gaps():
    missing = {int(ts(2024, 1, 2, 3, 15).timestamp()), int(ts(2024, 1, 2, 3, 30).timestamp())}
    fake = FakeCoinbase(ts(2024, 1, 1), ts(2024, 2, 1), missing)
    df = coinbase.fetch_range("BTC-USD", ts(2024, 1, 2), ts(2024, 1, 3), get=fake, pause_s=0)
    assert df.height == 96 - 2
    assert not set(df["ts_epoch"].to_list()) & missing


def test_download_resumes_and_marks_current_month_partial(tmp_path):
    fake = FakeCoinbase(ts(2023, 12, 15), ts(2024, 3, 31))
    now = ts(2024, 3, 10, 12, 7)  # mid-March, mid-bar

    s1 = coinbase.download_symbol("BTC-USD", date(2023, 11, 1), tmp_path, now=now, get=fake, pause_s=0)
    files = sorted(p.name for p in (tmp_path / "coinbase" / "BTC-USD").iterdir())
    assert files == ["2023-11.parquet", "2023-12.parquet", "2024-01.parquet", "2024-02.parquet", "2024-03.partial.parquet"]
    assert pl.read_parquet(tmp_path / "coinbase/BTC-USD/2023-11.parquet").height == 0  # before listing

    # Partial month stops before the still-forming 12:00 bar.
    mar = pl.read_parquet(tmp_path / "coinbase/BTC-USD/2024-03.partial.parquet")
    assert mar["ts_epoch"].max() == int(ts(2024, 3, 10, 11, 45).timestamp())
    assert s1["months_downloaded"] == 5

    # Second run, after March is over: finished months are skipped, March is finalized.
    later = ts(2024, 4, 2)
    s2 = coinbase.download_symbol("BTC-USD", date(2023, 11, 1), tmp_path, now=later, get=fake, pause_s=0)
    assert s2["months_skipped"] == 4
    files = sorted(p.name for p in (tmp_path / "coinbase" / "BTC-USD").iterdir())
    assert "2024-03.parquet" in files and "2024-03.partial.parquet" not in files
    assert "2024-04.partial.parquet" in files


def test_http_getter_retries_on_rate_limit(monkeypatch):
    monkeypatch.setattr(coinbase.time, "sleep", lambda s: None)

    class Resp:
        def __init__(self, code, body=None):
            self.status_code, self._body = code, body

        def json(self):
            return self._body

        def raise_for_status(self):
            raise RuntimeError(self.status_code)

    class Session:
        headers: dict = {}

        def __init__(self):
            self.replies = [Resp(429), Resp(503), Resp(200, [[1, 2, 3, 4, 5, 6]])]

        def get(self, *a, **k):
            return self.replies.pop(0)

    get = coinbase.http_getter(Session())
    assert get("u", {}) == [[1, 2, 3, 4, 5, 6]]


def test_http_getter_fails_fast_on_bad_request():
    class Resp:
        status_code = 404

        def raise_for_status(self):
            raise ValueError("404")

    class Session:
        headers: dict = {}

        def get(self, *a, **k):
            return Resp()

    with pytest.raises(ValueError):
        coinbase.http_getter(Session())("u", {})
