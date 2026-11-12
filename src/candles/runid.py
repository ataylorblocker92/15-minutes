"""Run IDs: config hash + git commit + data checksum (CLAUDE.md conventions).

Two runs with the same settings, code and data get the same ID. If the code
has uncommitted changes the commit can't vouch for it, so the ID is marked
"dirty" and gets a timestamp to keep it from colliding with anything.
"""

from __future__ import annotations

import hashlib
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def hash_files(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sorted(Path(x) for x in paths):
        h.update(p.name.encode())
        h.update(p.read_bytes())
    return h.hexdigest()


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def git_state() -> tuple[str, bool]:
    """(short commit, has uncommitted changes). ("nogit", True) outside a repo."""
    commit = _git("rev-parse", "--short", "HEAD")
    if not commit:
        return "nogit", True
    return commit, bool(_git("status", "--porcelain"))


def make_run_id(config_files: list[Path], data_files: list[Path]) -> tuple[str, str]:
    """Returns (run_id, config_hash)."""
    config_hash = hash_files(config_files)
    commit, dirty = git_state()
    run_id = f"{config_hash[:8]}-{commit}-{hash_files(data_files)[:8]}"
    if dirty:
        run_id += "-dirty-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return run_id, config_hash
