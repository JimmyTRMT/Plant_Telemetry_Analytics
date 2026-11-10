"""Daily parquet generator: turns the plant model into historian-style raw exports."""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from telemetry_pipeline.catalog import Tag
from telemetry_pipeline.simulation.faults import FaultRates, apply_sample_faults
from telemetry_pipeline.simulation.profiles import PROFILES
from telemetry_pipeline.simulation.schedule import (
    MASTER_SEED,
    hours_since_epoch,
    stable_code,
    window_mask,
    windows,
)
from telemetry_pipeline.simulation.signals import PlantState, build_state, clean_signal

LOGGER = logging.getLogger(__name__)
SECONDS_PER_DAY = 86_400


def _hold_flatlines(
    values: np.ndarray,
    t: np.ndarray,
    flat_windows: np.ndarray,
    value_at: Callable[[np.ndarray], np.ndarray],
) -> np.ndarray:
    """A stuck sensor repeats the value it had when the window opened."""
    for start, end in flat_windows[
        (flat_windows[:, 1] > t.min()) & (flat_windows[:, 0] <= t.max())
    ]:
        inside = (t >= start) & (t < end)
        if inside.any():
            values[inside] = value_at(np.array([start]))[0]
    return values


def _generate_series(day: date, state: PlantState, tag: Tag, rates: FaultRates) -> pa.Table:
    site_id = state.site.site_id
    profile = PROFILES[tag.tag_name]
    steps = SECONDS_PER_DAY // tag.sampling_seconds

    day_start = np.datetime64(day.isoformat(), "s")
    ts = day_start + np.arange(steps) * np.timedelta64(tag.sampling_seconds, "s")
    t = hours_since_epoch(ts)
    rng = np.random.default_rng([MASTER_SEED, stable_code(site_id, tag.tag_name), day.toordinal()])

    values = clean_signal(state, tag, profile, t)
    values = values * (1.0 + rng.normal(0.0, profile.noise_ratio, steps))
    values = _hold_flatlines(
        values,
        t,
        windows("flatline", site_id, tag.tag_name),
        lambda at: clean_signal(state, tag, profile, at),
    )
    values = np.maximum(values, 0.0)
    values, quality = apply_sample_faults(rng, values, rates)

    outage = window_mask(t, windows("comm_outage", site_id))
    keep = ~outage & (rng.random(steps) >= rates.missing)
    ts, values, quality = ts[keep], values[keep], quality[keep]

    resent = rng.random(ts.size) < rates.duplicate
    ts = np.concatenate([ts, ts[resent]])
    values = np.concatenate([values, values[resent]])
    quality = np.concatenate([quality, np.full(int(resent.sum()), "UNCERTAIN")])

    return pa.table(
        {
            "site_id": pa.array(np.full(ts.size, site_id)),
            "tag_name": pa.array(np.full(ts.size, tag.tag_name)),
            "ts_utc": pa.array(ts, type=pa.timestamp("s")),
            "value": pa.array(values, type=pa.float64()),
            "quality": pa.array(quality),
        }
    )


def generate_day(
    day: date,
    sites: Sequence,
    tags: Sequence[Tag],
    rates: FaultRates | None = None,
) -> pa.Table:
    rates = rates or FaultRates()
    chunks = [
        _generate_series(day, build_state(site), tag, rates) for site in sites for tag in tags
    ]
    return pa.concat_tables(chunks)


def write_day(table: pa.Table, out_dir: Path, day: date) -> Path:
    """Write atomically so a half-written file is never picked up by the loader."""
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / f"readings_{day.isoformat()}.parquet"
    temporary = final.with_name(final.name + ".tmp")
    pq.write_table(table, temporary, compression="zstd")
    temporary.replace(final)
    return final


def simulate(
    start: date, end: date, out_dir: Path, sites: Sequence, tags: Sequence[Tag]
) -> list[Path]:
    paths: list[Path] = []
    day = start
    while day <= end:
        table = generate_day(day, sites, tags)
        paths.append(write_day(table, out_dir, day))
        LOGGER.info("generated %s (%d rows)", day.isoformat(), table.num_rows)
        day += timedelta(days=1)
    return paths
