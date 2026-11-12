"""Loads and checks config/instruments.yaml before anything runs."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

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


class SplitsConfig(BaseModel):
    """Date boundaries for discovery / validation / holdout (config/splits.yaml)."""

    discovery_end: date
    validation_end: date
    embargo_days: int = Field(1, ge=1)
    vault_root: Path = Path("vault/holdout")

    @model_validator(mode="after")
    def blocks_in_order(self) -> SplitsConfig:
        if self.validation_start >= self.validation_end:
            raise ValueError("validation_end must come after discovery_end plus the embargo")
        return self

    @property
    def validation_start(self) -> date:
        return self.discovery_end + timedelta(days=self.embargo_days)

    @property
    def holdout_start(self) -> date:
        return self.validation_end + timedelta(days=self.embargo_days)


class PatternsConfig(BaseModel):
    """Which patterns are switched on (config/patterns.yaml)."""

    atr_period: int = Field(14, gt=1)
    min_occurrences: int = Field(300, gt=0)
    two_candle: list[str]


class LabelsConfig(BaseModel):
    """Forward targets (config/labels.yaml)."""

    horizons: list[int]
    flat_atr: float = Field(0.05, ge=0)

    @field_validator("horizons")
    @classmethod
    def horizons_positive(cls, v: list[int]) -> list[int]:
        if not v or any(h < 1 for h in v):
            raise ValueError("horizons must be a non-empty list of positive bar counts")
        return sorted(set(v))


def _load(model: type[BaseModel], path: str | Path):
    with open(path) as f:
        return model.model_validate(yaml.safe_load(f))


def load_splits(path: str | Path = "config/splits.yaml") -> SplitsConfig:
    return _load(SplitsConfig, path)


def load_patterns(path: str | Path = "config/patterns.yaml") -> PatternsConfig:
    return _load(PatternsConfig, path)


def load_labels(path: str | Path = "config/labels.yaml") -> LabelsConfig:
    return _load(LabelsConfig, path)
