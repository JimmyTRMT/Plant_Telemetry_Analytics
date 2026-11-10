"""Filesystem layout shared by every pipeline stage."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(os.environ.get("TELEMETRY_HOME", Path(__file__).resolve().parents[2]))


@dataclass(frozen=True)
class Paths:
    root: Path = ROOT

    @property
    def dbt_dir(self) -> Path:
        return self.root / "dbt"

    @property
    def seeds_dir(self) -> Path:
        return self.dbt_dir / "seeds"

    @property
    def raw_dir(self) -> Path:
        return self.root / "data" / "raw" / "readings"

    @property
    def warehouse(self) -> Path:
        override = os.environ.get("DUCKDB_PATH")
        return Path(override) if override else self.root / "warehouse" / "telemetry.duckdb"
