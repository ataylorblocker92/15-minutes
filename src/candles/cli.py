"""Command-line entry point. One command per pipeline step.

    candles ingest                 # download every instrument whose source is built
    candles ingest -s BTC-USD      # just one
    candles clean                  # clean everything that has raw data
    candles split                  # discovery / validation / holdout (vault)
    candles features               # ATR + pattern flags (discovery by default)
    candles labels                 # forward targets
    candles stats                  # hit-rate table + test registry
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Annotated

import polars as pl
import typer

from candles.clean.bars import clean_instrument
from candles.config import load_labels, load_patterns, load_splits, load_universe
from candles.features.build import build_features_for, features_path
from candles.features.patterns import PATTERN_PREFIX
from candles.ingest import coinbase
from candles.labels.forward import build_labels_for, labels_path
from candles.runid import make_run_id
from candles.split.splitter import OpenSplit, split_instrument
from candles.stats.hit_rate import hit_rate_table, registry_rows, result_path
from candles.stats.registry import append_tests

app = typer.Typer(help="15-minute candlestick study pipeline", no_args_is_help=True)

ConfigOpt = Annotated[Path, typer.Option("--config", "-c", help="Instrument config file")]
SymbolsOpt = Annotated[list[str] | None, typer.Option("--symbol", "-s", help="Limit to these symbols")]
# Only the open splits can be named here. The holdout is not an option on purpose.
SplitOpt = Annotated[OpenSplit, typer.Option("--split", help="discovery or validation")]

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


def _symbols_with(uni, symbol: list[str] | None, folder: Path) -> list[str]:
    """Chosen symbols that have a file in `folder`; the rest are reported and skipped."""
    out = []
    for inst in uni.select(symbol):
        if (folder / f"{inst.symbol}.parquet").exists():
            out.append(inst.symbol)
        else:
            typer.echo(f"skip {inst.symbol}: nothing in {folder} yet")
    return out


@app.command()
def split(config: ConfigOpt = Path("config/instruments.yaml"), symbol: SymbolsOpt = None) -> None:
    """Cut clean bars into discovery / validation / holdout (holdout goes to the vault)."""
    uni = load_universe(config)
    cfg = load_splits(config.parent / "splits.yaml")
    for sym in _symbols_with(uni, symbol, uni.data_root / "clean"):
        s = split_instrument(sym, uni.data_root, cfg)
        for name in ("discovery", "validation", "holdout"):
            b = s[name]
            share = b["rows"] / s["clean_rows"] if s["clean_rows"] else 0
            typer.echo(
                f"{sym} {name:<10} {b['rows']:>8,} bars ({share:5.1%})  "
                f"{b['first_bar_utc']} -> {b['last_bar_utc']}"
            )
        typer.echo(f"{sym} embargo    {s['embargo_rows_dropped']:>8,} bars dropped")


@app.command()
def features(
    config: ConfigOpt = Path("config/instruments.yaml"), symbol: SymbolsOpt = None, split: SplitOpt = "discovery"
) -> None:
    """Build ATR and pattern flags for one split. Past bars only."""
    uni = load_universe(config)
    cfg = load_patterns(config.parent / "patterns.yaml")
    for sym in _symbols_with(uni, symbol, uni.data_root / split):
        f = build_features_for(sym, split, uni.data_root, cfg)
        counts = ", ".join(
            f"{c.removeprefix(PATTERN_PREFIX)} {int(f[c].sum()):,}" for c in f.columns if c.startswith(PATTERN_PREFIX)
        )
        typer.echo(f"{sym} {split}: {f.height:,} bars; {counts}")


@app.command()
def labels(
    config: ConfigOpt = Path("config/instruments.yaml"), symbol: SymbolsOpt = None, split: SplitOpt = "discovery"
) -> None:
    """Build forward-looking targets for one split. The only step that looks ahead."""
    uni = load_universe(config)
    cfg = load_labels(config.parent / "labels.yaml")
    atr_period = load_patterns(config.parent / "patterns.yaml").atr_period
    for sym in _symbols_with(uni, symbol, uni.data_root / split):
        lab = build_labels_for(sym, split, uni.data_root, cfg, atr_period)
        for h in cfg.horizons:
            n = lab[f"dir_{h}"].is_not_null().sum()
            typer.echo(f"{sym} {split} h={h}: {n:,} of {lab.height:,} bars labelled")


@app.command()
def stats(
    config: ConfigOpt = Path("config/instruments.yaml"),
    symbol: SymbolsOpt = None,
    split: SplitOpt = "discovery",
    results: Annotated[Path, typer.Option("--results", help="Results folder")] = Path("results"),
) -> None:
    """Hit-rate table per pattern; every test is logged to the test registry."""
    uni = load_universe(config)
    pat = load_patterns(config.parent / "patterns.yaml")
    lab_cfg = load_labels(config.parent / "labels.yaml")
    config_files = [config] + [config.parent / n for n in ("splits.yaml", "patterns.yaml", "labels.yaml")]
    for sym in _symbols_with(uni, symbol, uni.data_root / "features" / split):
        f_path = features_path(uni.data_root, split, sym)
        l_path = labels_path(uni.data_root, split, sym)
        if not l_path.exists():
            typer.echo(f"skip {sym}: no labels for {split} yet")
            continue
        run_id, config_hash = make_run_id(config_files, [f_path, l_path])
        out = result_path(results, run_id, sym, split)
        if out.exists():
            typer.echo(f"{sym}: run {run_id} already exists at {out.parent}; nothing re-run or re-logged")
            continue
        table = hit_rate_table(pl.read_parquet(f_path), pl.read_parquet(l_path), lab_cfg.horizons, pat.min_occurrences)
        out.parent.mkdir(parents=True, exist_ok=True)
        table.write_parquet(out)
        tests = registry_rows(table, sym, split)
        total = append_tests(results / "test_registry.parquet", tests, run_id, config_hash)

        typer.echo(f"\n{sym} {split}  run {run_id}")
        typer.echo(f"{'pattern':<20}{'h':>3}{'n':>9}{'up':>9}{'down':>9}{'flat':>8}{'up rate':>9}{'edge':>9}{'p':>9}")
        for r in table.iter_rows(named=True):
            rate = f"{r['hit_rate_up']:.2%}" if r["hit_rate_up"] is not None else "-"
            edge = f"{r['edge']:+.2%}" if r["edge"] is not None else "-"
            p = f"{r['p_value']:.4f}" if r["p_value"] is not None else ("-" if r["pattern"] == "ALL_BARS" else "too few")
            typer.echo(
                f"{r['pattern']:<20}{r['horizon']:>3}{r['n']:>9,}{r['n_up']:>9,}{r['n_down']:>9,}"
                f"{r['n_flat']:>8,}{rate:>9}{edge:>9}{p:>9}"
            )
        typer.echo(f"{len(tests)} tests logged; registry now holds {total:,} rows. Saved to {out}")


if __name__ == "__main__":
    app()
