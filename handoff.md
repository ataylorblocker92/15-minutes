# Handoff — 2026-11-11

For a fresh session. Read `CLAUDE.md` first (hard rules), then this note. Replace this file at the next handoff; don't add a second one.

## Where things stand

| Phase (Design Doc 2) | Status |
| --- | --- |
| 1. Data foundation | Crypto done. BTC, ETH and SOL are downloaded and cleaned on Taylor's Mac (2026-11-10 log entry). On the Windows PC only BTC-USD is downloaded. Stocks (Massive) and forex (Dukascopy) downloaders not built. |
| 2. Splits and vault | First version built and run on BTC-USD. Holdout lock in place and tested. Split dates are still "Proposed" (D13). |
| 3. Features and labels | Thin slice only: ATR(14), four 2-candle patterns, 1-candle-ahead direction label. No Track B shape codes, no context features, no horizons 2/4/8, no MFE/MAE/barrier labels. |
| 4. Stats engine | Thin slice only: up-vs-down hit rate vs all-bars base rate, naive binomial p-value, test registry. No clustering, no time-of-day base rate, no bootstrap, no FDR correction. |
| 5–8. Findings, backtester, validation, holdout | Not started. |

## Committed vs. not committed

- **Committed and pushed:** the Phase 1 code (`28a1ef6`), the Mac session's log entry (`9b04e9c`), plus this note, `research_log.md` and `DECISIONS.md`.
- **NOT committed (sitting in the working tree):** the whole end-to-end slice. Taylor was asked whether to commit it and has not answered yet. Do not commit it without a yes.
  - Modified: `CLAUDE.md`, `README.md`, `pyproject.toml`, `src/candles/cli.py`, `src/candles/config.py`
  - New: `config/splits.yaml`, `config/patterns.yaml`, `config/labels.yaml`, `src/candles/vault.py`, `src/candles/runid.py`, `src/candles/split/splitter.py`, `src/candles/features/{atr,patterns,build}.py`, `src/candles/labels/forward.py`, `src/candles/stats/{hit_rate,registry}.py`, `tests/helpers.py`, `tests/test_{split,features,labels,stats}.py`
- Note: the committed research log and DECISIONS entries describe this uncommitted code.

## Two machines

Work happens on both a Mac and a Windows PC. Data and results are git-ignored, so each machine has its own copy. The Mac has BTC/ETH/SOL clean data but none of the slice's outputs; the Windows PC has everything below. The two BTC-USD downloads differ by 83 bars (pulled at different times), so checksums and run IDs differ between machines. **Always `git pull` before starting**: this handoff hit a push conflict because the Mac session had pushed a log entry.

## What's on disk (git-ignored, Windows PC only)

- `.venv/` on **Python 3.14**. CLAUDE.md now says 3.15 (also installed here); 3.14 was picked before that change was seen. Everything passes on 3.14. Run things as `.venv/Scripts/candles ...` and `.venv/Scripts/python -m pytest`.
- `data/raw/coinbase/BTC-USD/` and `data/clean/BTC-USD.parquet`: 240,565 bars, 2020-01-01 to 2026-11-11, 16 gaps (105 missing bars).
- `data/discovery/`, `data/validation/`, `vault/holdout/` for BTC-USD. **The holdout has been written but never read. Keep it that way** (hard rule 1).
- `data/features/discovery/`, `data/labels/discovery/` for BTC-USD.
- `results/test_registry.parquet`: 4 rows. Append-only, never delete.
- `results/patterns/321b96de-28a1ef6-7f1c85e3-dirty-20261111T233803Z/`: the first hit-rate table.

## Tests

43 passing (`.venv/Scripts/python -m pytest`). Nothing known to be broken.

## First result (not a finding)

Discovery only, next candle, base rate 50.44% up. Bullish engulfing 49.45% (p 0.033), bearish engulfing 51.77% (p 0.010), inside bar 50.51%, outside bar 50.21%. Edges are about 1 point at most and the p-values are naive and uncorrected. Details in `research_log.md`.

## Known gaps and rough edges

- Run IDs are marked `-dirty-<timestamp>` whenever the tree has uncommitted changes, so every `candles stats` run right now logs 4 more registry rows. Commit before re-running stats to avoid padding the registry.
- The stats shortcuts listed above mean no p-value from this slice should be trusted or quoted.
- `candles split` rewrites all three blocks (including the vault file) each time it runs, and the holdout grows with each new download because it has no end date.
- The Windows `.venv` is Python 3.14 while CLAUDE.md says 3.15. `AssetClass` in `config.py` still lists `future` (dropped in D10). Harmless, not cleaned up.
- The registry and results live on the Windows PC only. If stats are also run on the Mac, there will be two separate registries, which breaks the true test count (hard rule 5). Pick one machine for stats, or decide how to share `results/`.
- Design Doc 2 says tables are partitioned by instrument and year; the code writes one file per instrument. Not raised with Taylor yet.

## Waiting on Taylor

1. **Commit the slice?** (and push)
2. **D13, split dates:** global calendar dates (discovery before 2024-02-01, validation to 2025-06-30, holdout from 2025-07-02). Stocks with 5 years of history would get a smaller discovery share. Hard to change after more discovery work.
3. **D14:** plain-average ATR, blank across gaps, instead of Wilder smoothing.
4. **D15:** features and labels under `data/features/` and `data/labels/`.
5. Give the holdout a fixed end date?
6. Which machine is the home for stats runs and the test registry?
7. Older open items in `DECISIONS.md`: confirm Massive and Dukascopy (D12), the starter instrument list, pooling across asset classes, holdout pass/fail thresholds. D4, D6, D7, D8 are also still "Proposed".

## Recommended next step

Get answers to 1 and 2 first. Then, in order:

1. Horizons 2, 4, 8 in labels (the code already loops over `config/labels.yaml` horizons; add tests for overlap).
2. Proper stats: standard errors clustered by day, base rate matched by time of day, Benjamini–Hochberg over the registry (fills `adjusted_p`).
3. Run the same slice on ETH-USD and SOL-USD (`candles ingest`, `clean`, `split`, `features`, `labels`, `stats` with no `-s`).

The Mac session's own next step was the Dukascopy forex adapter; that is independent of the above and can go in either order.
