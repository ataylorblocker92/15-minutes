"""Command-line entry point. One command per pipeline step.

    candles ingest                 # download every instrument whose source is built
    candles ingest -s BTC-USD      # just one
    candles clean                  # clean everything that has raw data
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import typer

from candles.clean.bars import clean_instrument
from candles.config import load_universe
from candles.ingest import coinbase

app = typer.Typer(help="15-minute candlestick study pipeline", no_args_is_help=True)

ConfigOpt = Annotated[Path, typer.Option("--config", "-c", help="Instrument config file")]
SymbolsOpt = Annotated[list[str] | None, typer.Option("--symbol", "-s", help="Limit to these symbols")]

BUILT_SOURCES = {"coinbase"}  # grows as Massive and Dukascopy adapters are added


@app.callback()
def _setup(verbose: Annotated[bool, typer.Option("--verbose", "-v")] = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


@app.command()
def ingest(config: ConfigOpt = Path("config/instruments.yaml"), symbol: SymbolsOpt = None) -> None:
    """Download raw bars into data/raw/."""
    uni = load_universe(config)
    for inst in uni.select(symbol):
        if inst.source not in BUILT_SOURCES:
            typer.echo(f"skip {inst.symbol}: '{inst.source}' downloader not built yet")
            continue
        summary = coinbase.download_symbol(
            inst.symbol, inst.history_start, uni.data_root / "raw", uni.bar_minutes
        )
        typer.echo(
            f"{inst.symbol}: {summary['months_downloaded']} months downloaded, "
            f"{summary['months_skipped']} already on disk, {summary['bars_written']:,} bars"
        )


@app.command()
def clean(config: ConfigOpt = Path("config/instruments.yaml"), symbol: SymbolsOpt = None) -> None:
    """Build data/clean/<SYMBOL>.parquet and its manifest from raw downloads."""
    uni = load_universe(config)
    for inst in uni.select(symbol):
        raw_dir = uni.data_root / "raw" / inst.source / inst.symbol
        if not raw_dir.exists():
            typer.echo(f"skip {inst.symbol}: no raw data yet")
            continue
        m = clean_instrument(inst, uni.data_root, uni.bar_minutes)
        typer.echo(
            f"{inst.symbol}: {m['rows']:,} bars {m['first_bar_utc']} -> {m['last_bar_utc']}, "
            f"{m['gap_count']:,} gaps ({m['bars_missing_total']:,} missing bars), "
            f"{m['invalid_bars_dropped']} invalid dropped"
        )


if __name__ == "__main__":
    app()
