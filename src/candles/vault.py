"""The only door to the holdout vault (CLAUDE.md hard rule 1).

Nothing else in the codebase may open files under vault/holdout/. Every
attempt, allowed or refused, is written to an access log so there is a
record of exactly when the holdout was looked at.

The split step WRITES holdout files (it has to put them somewhere) but never
reads them back.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import polars as pl

ACCESS_LOG_NAME = "holdout_access.log"


class HoldoutLockedError(PermissionError):
    """Raised when code tries to read the holdout without the unlock flag."""


def _log_access(log_dir: Path, symbol: str, allowed: bool, reason: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "symbol": symbol,
        "allowed": allowed,
        "reason": reason,
    }
    with open(log_dir / ACCESS_LOG_NAME, "a") as f:
        f.write(json.dumps(entry) + "\n")


def read_holdout(
    vault_root: Path, symbol: str, *, unlock: bool, reason: str, log_dir: Path = Path("results")
) -> pl.DataFrame:
    """Read one instrument's holdout bars. Refuses unless unlock=True.

    `unlock` must come straight from the --unlock-holdout command-line flag,
    never from a default or a config file.
    """
    if unlock is not True:
        _log_access(log_dir, symbol, False, reason)
        raise HoldoutLockedError(
            f"holdout for {symbol} is locked. It may only be read with --unlock-holdout, "
            "after strategy configs are frozen and committed."
        )
    _log_access(log_dir, symbol, True, reason)
    return pl.read_parquet(Path(vault_root) / f"{symbol}.parquet")
