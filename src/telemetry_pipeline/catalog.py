"""Typed access to the reference data that dbt also loads as seeds."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from telemetry_pipeline.settings import Paths


@dataclass(frozen=True)
class Site:
    site_id: str
    site_name: str
    country: str
    timezone: str
    nominal_power_mw: float
    commissioned_year: int


@dataclass(frozen=True)
class Tag:
    tag_name: str
    description: str
    unit: str
    measurement_category: str
    sampling_seconds: int
    min_valid: float
    max_valid: float
    alarm_high: float | None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_sites(seeds_dir: Path | None = None) -> list[Site]:
    rows = _read_csv((seeds_dir or Paths().seeds_dir) / "sites.csv")
    return [
        Site(
            site_id=row["site_id"],
            site_name=row["site_name"],
            country=row["country"],
            timezone=row["timezone"],
            nominal_power_mw=float(row["nominal_power_mw"]),
            commissioned_year=int(row["commissioned_year"]),
        )
        for row in rows
    ]


def load_tags(seeds_dir: Path | None = None) -> list[Tag]:
    rows = _read_csv((seeds_dir or Paths().seeds_dir) / "tag_catalog.csv")
    return [
        Tag(
            tag_name=row["tag_name"],
            description=row["description"],
            unit=row["unit"],
            measurement_category=row["measurement_category"],
            sampling_seconds=int(row["sampling_seconds"]),
            min_valid=float(row["min_valid"]),
            max_valid=float(row["max_valid"]),
            alarm_high=float(row["alarm_high"]) if row["alarm_high"] else None,
        )
        for row in rows
    ]
