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
