# CLAUDE.md — 15-minutes

Research project: find 2- and 3-candle patterns on 15-minute charts (stocks/ETFs, futures, forex, crypto), test whether they predict direction, then size and path, over the next 1, 2, 4 and 8 candles, and check whether strategies built on them survive unseen data after costs and risk.

## Source of truth

- Design Doc 1, Research Methodology: https://claude.ai/artifact/G9dqNXocBDPCF4WaTxon4j
- Design Doc 2, System Architecture: https://claude.ai/artifact/Ec94jFbZP5wm22hDMWSZXi
- Settled choices: `DECISIONS.md`. Do not re-open a decision there without the owner (Taylor) agreeing.
- What happened and when: `research_log.md`.

If code and the design docs disagree, stop and ask. Don't quietly pick one.

## Hard rules (never break these)

1. **Never read `vault/holdout/`** unless the command was run with `--unlock-holdout` and Taylor explicitly asked for the final holdout test. Any code path that touches the vault must check the flag and log the access.
2. **Features use past bars only.** A feature at bar t may read bars ≤ t. Every new feature gets a future-shift test in `tests/` (randomize bars after t; the feature at t must not change).
3. **Only `labels` looks forward.** Label columns must never feed `features` or the backtester's entry/exit decisions.
4. **Trades enter at the next bar's open**, never at the close of the pattern's last bar.
5. **Log every statistical test** to the test registry (`results/test_registry.parquet`, append-only). Never delete rows. The FDR correction depends on the true count.
6. **Never forward-fill missing bars.** A pattern that spans a gap is discarded.
7. **Costs are always on.** No backtest result is reported without the cost model from `config/costs.yaml`. Also report the 2× cost stress run.
8. **No tuning on the holdout.** Strategy configs are frozen and committed before the holdout is unlocked.

## Conventions

- Python 3.12. Polars for dataframes, DuckDB for SQL over Parquet, NumPy/Numba for bar loops, SciPy/statsmodels for stats, Pydantic for config, Typer for the CLI, pytest + Hypothesis for tests, Plotly for charts.
- All timestamps are UTC, stored as bar-open time. Keep the exchange timezone in a separate column.
- Normalize price moves by ATR(14) for cross-instrument comparisons. Keep raw points and percent too.
- Settings live in `config/*.yaml`, not in code. Don't hard-code instruments, dates, buckets, horizons or cost rates.
- Each module reads from one folder and writes to another (see Design Doc 2). A stage must be rerunnable alone.
- Every run gets a run ID = config hash + git commit + data checksums. Results go under that ID; never overwrite.
- Data and results are git-ignored. Code, config, docs and tests are committed.

## Layout

```
config/            instruments, patterns, context, costs, splits, strategies/
src/candles/       ingest, clean, split, features, labels, stats, backtest, report
data/              raw, clean, discovery, validation (git-ignored)
vault/holdout/     locked holdout (git-ignored)
results/           pattern stats, backtests, test registry (git-ignored)
reports/           notebooks and charts
tests/
```

## Commands

Not built yet. When the CLI exists, list one command per module here, e.g. `candles ingest --config config/instruments.yaml`.

## Working style

- Taylor is an experienced CNC machinist/programmer, not a career software developer. Explain what changed and why in plain language, conversationally.
- After any change that could affect results, add a dated entry to `research_log.md`.
- When a choice is settled, record it in `DECISIONS.md` with the date and the reason.
- Prefer small, checkable steps: get one instrument working end to end before widening.
