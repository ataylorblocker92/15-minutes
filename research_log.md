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

## 2026-11-12 — Clean rerun of stats after committing the slice
- What was done: the 2026-11-11 slice (`ab3e148`) was committed and pushed, then `candles stats -s BTC-USD` was rerun on the now-clean tree so the run ID would not carry a `-dirty-` timestamp. No code or data changed; same discovery bars, same patterns, same labels.
- Run ID: `321b96de-d9c42c6-7f1c85e3` (replaces the dirty run `321b96de-28a1ef6-7f1c85e3-dirty-20261111T233803Z` as the one to cite; the dirty run's output and registry rows are left in place, nothing is deleted)
- Result: identical numbers to the 2026-11-11 entry below (base rate 50.44% up; bullish engulfing 49.45% edge -0.99% p 0.033; bearish engulfing 51.77% edge +1.33% p 0.010; inside bar 50.51% edge +0.07% p 0.835; outside bar 50.21% edge -0.23% p 0.604), as expected since nothing upstream changed.
- Note: `results/test_registry.parquet` now holds 8 rows (4 from the dirty run + 4 from this clean run) for what is really one set of 4 tests. This is the registry doing its job (append-only, hard rule 5) but means the "true test count" for FDR purposes is currently inflated by this duplication. Worth deciding whether dirty-run rows should be marked/excluded before FDR correction is implemented.
- Next: see 2026-11-11 entry.

## 2026-11-11 — First end-to-end slice on BTC-USD (discovery only)
- What was done: on Taylor's Windows PC, a fresh BTC-USD download and clean (240,565 bars, 2020-01-01 to 2026-11-11 23:15, 16 gaps / 105 missing bars, 1 zero-range bar, 0 invalid). This is a separate copy from the Mac download in the 2026-11-10 entry: same gap counts, 83 more bars because it was pulled later, so the clean-file checksum and any run ID differ between the two machines. Built thin first versions of `split`, `features` (ATR14 + bullish/bearish engulfing, inside bar, outside bar), `labels` (1 candle ahead, flat under 0.05 ATR) and `stats` (up-vs-down hit rate against the all-bars base rate, binomial p-value, test registry). Holdout lock added (`candles.vault`). 43 tests passing, including future-shift tests. Added `tzdata` and `scipy` to dependencies; the Windows `.venv` is Python 3.14 (3.15 is also installed and is what CLAUDE.md names; 3.14 was picked before that change was seen).
- Split (D13, proposed): discovery 143,184 bars (59.5%), validation 49,431 (20.5%), holdout 47,758 (19.9%), 192 embargo bars dropped. Holdout written to the vault and not read.
- Run ID: `321b96de-28a1ef6-7f1c85e3-dirty-20261111T233803Z` ("dirty" = code not yet committed)
- Result (discovery, h=1, base rate 50.44% up of 143,004 labelled bars):

  | Pattern | n | Up rate | Edge vs base | p (naive) |
  | --- | --- | --- | --- | --- |
  | bullish_engulfing | 12,423 | 49.45% | -0.99% | 0.033 |
  | bearish_engulfing | 10,143 | 51.77% | +1.33% | 0.010 |
  | inside_bar | 23,732 | 50.51% | +0.07% | 0.835 |
  | outside_bar | 14,399 | 50.21% | -0.23% | 0.604 |

- Reading: nothing here is a finding. Edges are about 1 percentage point at most, far below trading costs. The p-values are naive (no clustering by day, base rate not matched by time of day, no FDR correction). Both engulfing patterns lean slightly against their textbook direction (mild mean reversion), which is worth re-checking once the stats are done properly. 4 tests logged to the registry.
- Next: Taylor to confirm D13–D15. Then horizons 2/4/8, clustered standard errors and time-of-day base rate, BH correction, and the same slice on ETH-USD and SOL-USD.

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
