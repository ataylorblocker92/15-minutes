"""Loads and checks config/instruments.yaml before anything runs."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

AssetClass = Literal["stock", "etf", "future", "fx", "crypto"]
Source = Literal["coinbase", "massive", "dukascopy"]


class Instrument(BaseModel):
    symbol: str
    asset_class: AssetClass
    source: Source
    exchange_tz: str = "UTC"
    session: str
    history_start: date


class UniverseConfig(BaseModel):
    data_root: Path = Path("data")
    bar_minutes: int = Field(15, gt=0)
    instruments: list[Instrument]

    @field_validator("instruments")
    @classmethod
    def symbols_unique(cls, v: list[Instrument]) -> list[Instrument]:
        seen = [i.symbol for i in v]
        dupes = {s for s in seen if seen.count(s) > 1}
        if dupes:
            raise ValueError(f"duplicate symbols in config: {sorted(dupes)}")
        return v

    def select(self, symbols: list[str] | None = None, source: str | None = None) -> list[Instrument]:
        """Instruments filtered by symbol list and/or source. Unknown symbols are an error."""
        chosen = self.instruments
        if symbols:
            known = {i.symbol for i in chosen}
            missing = [s for s in symbols if s not in known]
            if missing:
                raise ValueError(f"not in config: {missing}")
            chosen = [i for i in chosen if i.symbol in symbols]
        if source:
            chosen = [i for i in chosen if i.source == source]
        return chosen


def load_universe(path: str | Path = "config/instruments.yaml") -> UniverseConfig:
    with open(path) as f:
        return UniverseConfig.model_validate(yaml.safe_load(f))
