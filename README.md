# 15-minutes

Do 2- and 3-candle patterns on 15-minute charts predict anything a trader can actually use? This repo tests that across crypto, stocks/ETFs and forex, with a locked holdout and real trading costs.

- Design Doc 1, Research Methodology: https://claude.ai/artifact/G9dqNXocBDPCF4WaTxon4j
- Design Doc 2, System Architecture: https://claude.ai/artifact/Ec94jFbZP5wm22hDMWSZXi
- Rules for working in this repo: `CLAUDE.md`
- Settled choices: `DECISIONS.md`
- Progress and results: `research_log.md`

## Getting started

You need Python 3.12 or newer and Git.

```bash
git clone https://github.com/ataylorblocker92/15-minutes
cd 15-minutes
python -m venv .venv
# Windows:   .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest                      # should say all tests passed
```

## Download crypto data (free)

```bash
candles ingest -s BTC-USD   # about 600 requests, roughly 5-10 minutes
candles clean  -s BTC-USD
```

Then check `data/clean/BTC-USD.manifest.json`: it shows the bar count, date range and how many gaps the data has. When BTC looks right, run `candles ingest` and `candles clean` with no `-s` to get all three coins.

Status: Phase 1 (data foundation). Crypto downloader built; stocks and forex next.
