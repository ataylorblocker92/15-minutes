# Handoff — 2026-11-17

For a fresh session. Read `CLAUDE.md` first (hard rules), then this note. Replace this file at the next handoff; don't add a second one.

## Where things stand

| Phase (Design Doc 2) | Status |
| --- | --- |
| 1. Data foundation | Crypto done. BTC, ETH and SOL downloaded and cleaned on Taylor's Mac (2026-11-10 log entry). On the Windows PC only BTC-USD is downloaded. Stocks (Massive) and forex (Dukascopy) downloaders not built. |
| 2. Splits and vault | Built and run on BTC-USD. Holdout lock in place and tested. Split dates are now **Settled** (D13, confirmed 2026-11-13): global UTC calendar dates, same for every instrument. |
| 3. Features and labels | ATR(14), four 2-candle patterns, and now **all four horizons** (1, 2, 4, 8 candles ahead) — turned on 2026-11-13. No Track B shape codes, no context features, no MFE/MAE/barrier labels. |
| 4. Stats engine | Thin slice only: up-vs-down hit rate vs all-bars base rate, naive binomial p-value, test registry. No clustering, no time-of-day base rate, no bootstrap, no FDR correction. |
| 5–8. Findings, backtester, validation, holdout | Not started. |

## Committed vs. not committed

Working tree is clean (`git status` shows nothing). Everything is committed and pushed to `origin/main`, including this handoff.

45 tests passing (`.venv/Scripts/python -m pytest`).

## Two machines

Work happens on both a Mac and a Windows PC. Data and results are git-ignored, so each machine has its own copy — this note only covers the Windows PC's state. The two BTC-USD downloads differ by bar count (pulled at different times), so checksums and run IDs differ between machines. **Always `git pull` before starting.**

## What's on disk (git-ignored, Windows PC only)

- `.venv/` on **Python 3.14**. CLAUDE.md says 3.15 (also installed here); 3.14 was picked before that change was seen. Everything passes on 3.14.
- `data/clean/BTC-USD.parquet`: 240,565 bars, 2020-01-01 to 2026-11-11.
- `data/discovery/`, `data/validation/`, `vault/holdout/` for BTC-USD. **The holdout has been written but never read. Keep it that way** (hard rule 1).
- `data/features/discovery/`, `data/labels/discovery/` for BTC-USD — labels now cover horizons 1/2/4/8.
- `results/test_registry.parquet`: **40 rows** for 16 distinct tests (4 patterns × 4 horizons), duplicated by two separate dirty-run-then-clean-rerun incidents — see "Known gaps" below. Append-only, never delete.
- `results/patterns/`: four result folders now — the original h=1-only pair from 2026-11-11/12, plus `d208c8b1-c8ab666-edf56f2d-dirty-20261113T234054Z/` (dirty, superseded) and `d208c8b1-2f35484-edf56f2d/` (clean, the one to cite for the horizons-2/4/8 result).

## Latest result (still not a finding)

Discovery only, BTC-USD, run `d208c8b1-2f35484-edf56f2d`. Base rates: 50.44% up (h=1), 50.57% (h=2), 50.89% (h=4), 51.05% (h=8).

| Pattern | h=1 edge (p) | h=2 edge (p) | h=4 edge (p) | h=8 edge (p) |
| --- | --- | --- | --- | --- |
| bullish_engulfing | -0.99% (0.033) | -2.64% (<0.0001) | -2.33% (<0.0001) | -2.33% (<0.0001) |
| bearish_engulfing | +1.33% (0.010) | +2.96% (<0.0001) | +2.67% (<0.0001) | +2.40% (<0.0001) |
| inside_bar | +0.07% (0.835) | +0.11% (0.734) | -0.24% (0.470) | +0.01% (0.984) |
| outside_bar | -0.23% (0.604) | -0.32% (0.452) | -0.50% (0.244) | -0.66% (0.120) |

Reading: same mild mean-reversion lean on both engulfing patterns as the first slice, now larger and more "significant" at the longer horizons — **still not a finding**. The p-values are naive (no clustering by day, no time-of-day base rate, no FDR correction) and the registry has known duplicate rows (below), so nothing here should be trusted or quoted yet. Full detail in `research_log.md` (2026-11-13 entry).

## Decisions settled since the last handoff

- **D13** (split dates): confirmed global UTC calendar dates as-is. Stocks will get a smaller discovery share than crypto under this scheme — accepted, not a flaw.
- **D16** (new): `candles stats` must never run on an uncommitted tree. A dirty run followed by a clean rerun logs the same tests twice in the append-only registry — this has now happened twice (2026-11-11/12, then again 2026-11-13 via the stray `AGENTS.md` file making the tree look dirty even right after a commit). Going forward: commit or stash before running stats.
- **`AGENTS.md`**: Taylor chose to commit it as-is (mirrors CLAUDE.md; some tools look for it by that name) rather than delete it. It's tracked now and needs manual updates alongside CLAUDE.md.

## Known gaps and rough edges

- **Registry has 40 rows for 16 distinct tests** (4 patterns × 4 horizons). The 4 h=1 tests were logged 4 times each (dirty + clean on 2026-11-11/12, then dirty + clean again on 2026-11-13) = 16 rows; the 12 tests for h=2/4/8 were logged twice each (dirty + clean on 2026-11-13 only) = 24 rows. 16 + 24 = 40. D16 (above) prevents new duplicates; these existing ones still need filtering by run_id pattern when FDR correction is built.
- No p-value from this project should be trusted or quoted yet — stats are still naive.
- `candles split` rewrites all three blocks (including the vault file) each time it runs, and the holdout grows with each new download because it has no end date.
- The Windows `.venv` is Python 3.14 while CLAUDE.md says 3.15. `AssetClass` in `config.py` still lists `future` (dropped in D10). Harmless, not cleaned up.
- The registry and results live on the Windows PC only. If stats are also run on the Mac, there will be two separate registries, which breaks the true test count (hard rule 5). Pick one machine for stats, or decide how to share `results/`.
- Design Doc 2 says tables are partitioned by instrument and year; the code writes one file per instrument. Not raised with Taylor yet.
- README.md's "Getting started" section still describes the labels step as "next-candle direction" — now stale since horizons 2/4/8 were added. Harmless, not fixed.

## Waiting on Taylor

1. Give the holdout a fixed end date?
2. Which machine is the home for stats runs and the test registry?
3. Older open items in `DECISIONS.md`: confirm Massive and Dukascopy (D12), the starter instrument list, pooling across asset classes, holdout pass/fail thresholds. D4, D6, D7, D8 are also still "Proposed".

## Recommended next step

Pick one of two independent directions (both were on the table at the end of the last session):

1. **Proper stats**: standard errors clustered by day, base rate matched by time of day, Benjamini–Hochberg correction over the registry (fills `adjusted_p`) — settle the registry duplicate-row filtering (item from "Known gaps") before trusting this.
2. **Widen to more instruments**: run the same slice (`candles ingest`, `clean`, `split`, `features`, `labels`, `stats`, no `-s`) on ETH-USD and SOL-USD, which are already downloaded on the Mac.

The Mac session's own next step was the Dukascopy forex adapter; that is independent of the above and can go in either order.
