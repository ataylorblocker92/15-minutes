# Research log

Dated notes on every decision, data pull and test run, newest at the top. Record the run ID with any result.

Template:

```
## YYYY-MM-DD — short title
- What was done:
- Run ID:
- Result:
- Next:
```

---

## 2026-11-10 — First real crypto download and clean (BTC, ETH, SOL)
- What was done: set up `.venv` on Taylor's Mac (Python 3.15.2), 17 tests passing. Ran `candles ingest` for BTC-USD, ETH-USD and SOL-USD from Coinbase (83 monthly files each, 2020-01 to 2026-11), then `candles clean`. The three were topped up back to back at 02:48 UTC on 2026-11-11 so they end on the same bar.
- Run ID: none yet (run IDs start with the later stages). Clean file checksums (sha256, first 12 characters): BTC-USD `a7967abfb695`, ETH-USD `b8e4d91e9b55`, SOL-USD `898f05505d44`. Code at commit 28a1ef6.
- Result:

  | Symbol | Bars | First bar (UTC) | Last bar (UTC) | Gaps | Missing bars | Invalid dropped |
  | --- | --- | --- | --- | --- | --- | --- |
  | BTC-USD | 240,482 | 2020-01-01 00:00 | 2026-11-11 02:30 | 16 | 105 | 0 |
  | ETH-USD | 240,480 | 2020-01-01 00:00 | 2026-11-11 02:30 | 17 | 107 | 0 |
  | SOL-USD | 189,273 | 2021-06-17 16:00 | 2026-11-11 02:30 | 9 | 82 | 0 |

- Notes: no duplicates removed in any symbol. Missing bars are under 0.1% of each series and are left as gaps, not filled. Zero-range bars flagged: BTC 1, ETH 3, SOL 0; zero-volume bars: none. SOL-USD starts 2021-06-17 because Coinbase has no SOL data before then (the 2020-01 to 2021-05 raw files are empty).
- Also: CLAUDE.md now says Python 3.15, the version in use.
- Next: Dukascopy forex adapter.

## 2026-11-09 — Crypto downloader and clean step built
- What was done: `candles ingest` (Coinbase, month-by-month, resumable) and `candles clean` (dedupe, drop impossible bars, flag gaps/zero-range/zero-volume, manifest with checksum). 17 tests passing against a fake exchange.
- Scope change: futures dropped (D10). Plan is crypto + stocks (one paid source) + forex (free).
- Not yet run on real data: the build workspace can't reach Coinbase, so the first real download runs on Taylor's computer.
- Next: real BTC-USD download, check the manifest's gap count, then Dukascopy forex adapter.

## 2026-11-09 — Repo created
- What was done: Set up the repo skeleton, CLAUDE.md, DECISIONS.md and this log.
- Data source: still being chosen. Webull's API doesn't look like a practical source for years of 15-minute history (no forex, needs a paid Nasdaq data feed for stocks, history depth not documented).
- Next: pick vendors, then Phase 1 (ingest + clean for SPY).

## 2026-11-08 — Design docs drafted
- Design Doc 1 (Research Methodology) and Design Doc 2 (System Architecture), links in CLAUDE.md.
