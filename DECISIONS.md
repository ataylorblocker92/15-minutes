# Decisions

Settled choices. Each entry has a date, the decision, and why. To change one, add a new entry that replaces it. Don't edit history.

| # | Date | Decision | Why | Status |
| --- | --- | --- | --- | --- |
| D1 | 2026-11-08 | Timeframe is 15-minute bars only; patterns are 2 or 3 candles | Project scope | Settled |
| D2 | 2026-11-08 | Forecast horizons: 1, 2, 4, 8 candles | Project scope | Settled |
| D3 | 2026-11-08 | Priority: direction first, then size and path | Project scope | Settled |
| D4 | 2026-11-08 | Time split: ~60% discovery, ~20% validation, ~20% holdout, with embargo gaps | Holdout must be truly unseen | Proposed |
| D5 | 2026-11-08 | Holdout opened once, after strategy configs are frozen | Prevents tuning on test data | Settled |
| D6 | 2026-11-08 | False discovery rate held at 5% (Benjamini–Hochberg) across all discovery tests | Thousands of tests guarantee lucky hits otherwise | Proposed |
| D7 | 2026-11-08 | Entry at next bar's open; ATR-based stop/target; time-out at horizon | Tradable, comparable across instruments | Proposed |
| D8 | 2026-11-08 | Python stack: Polars, DuckDB, Parquet, Numba, pytest | Fast on one machine, readable | Proposed |
| D9 | 2026-11-09 | Code lives in GitHub repo `15-minutes` | Persists across sessions | Settled |
| D10 | 2026-11-09 | Futures dropped from scope; at most one paid data subscription | Futures history too expensive; budget limit | Settled |
| D11 | 2026-11-09 | Crypto data from Coinbase public API (BTC-USD, ETH-USD, SOL-USD) | Free, US-accessible, USD pairs | Settled |
| D12 | 2026-11-09 | Stocks/ETFs from Massive Stocks Starter ($29/mo, 5 yrs minute bars); forex from Dukascopy (free) | One paid source; forex is available free | Proposed |

## Open

- Confirm Massive for stocks and Dukascopy for forex
- Starter instrument list (proposed: SPY, QQQ, IWM, AAPL · EUR/USD, GBP/USD, USD/JPY, AUD/USD · BTC, ETH, SOL)
- Pool all asset classes in discovery, or run each class separately first
- Holdout pass/fail thresholds (minimum Sharpe, maximum drawdown, minimum trade count)
