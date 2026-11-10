"""Deterministic event calendars per site: shutdowns, trips, excursions, outages, flatlines.

Windows are expressed in hours since EPOCH and derived from a seeded generator, so any
day can be generated independently and still agree with its neighbours.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass
from functools import cache

import numpy as np

EPOCH = np.datetime64("2024-01-01T00:00:00")
HORIZON_HOURS = 24 * 365 * 6
MASTER_SEED = 20240101


@dataclass(frozen=True)
class EventSpec:
    min_gap_h: float
    max_gap_h: float
    min_len_h: float
    max_len_h: float


SPECS: dict[str, EventSpec] = {
    "maintenance": EventSpec(18 * 24, 35 * 24, 36, 90),
    "trip": EventSpec(3 * 24, 10 * 24, 1.5, 7),
    "excursion": EventSpec(4 * 24, 12 * 24, 1, 3),
    "comm_outage": EventSpec(10 * 24, 25 * 24, 2, 10),
    "flatline": EventSpec(45 * 24, 120 * 24, 6, 14),
}


def stable_code(*parts: str) -> int:
    """Process-independent integer for seeding (the built-in hash() is salted)."""
    return zlib.crc32("|".join(parts).encode())


@cache
def windows(kind: str, site_id: str, tag_name: str = "") -> np.ndarray:
    """Return an (n, 2) array of [start, end) windows in hours since EPOCH."""
    spec = SPECS[kind]
    rng = np.random.default_rng([MASTER_SEED, stable_code(kind, site_id, tag_name)])
    found: list[tuple[float, float]] = []
    cursor = 0.0
    while cursor < HORIZON_HOURS:
        cursor += rng.uniform(spec.min_gap_h, spec.max_gap_h)
        length = rng.uniform(spec.min_len_h, spec.max_len_h)
        found.append((cursor, cursor + length))
        cursor += length
    return np.asarray(found)


def hours_since_epoch(timestamps: np.ndarray) -> np.ndarray:
    return (timestamps - EPOCH) / np.timedelta64(1, "h")


def _near(t: np.ndarray, wins: np.ndarray, margin: float = 0.0) -> np.ndarray:
    keep = (wins[:, 1] + margin > t.min()) & (wins[:, 0] - margin <= t.max())
    return wins[keep]


def window_mask(t: np.ndarray, wins: np.ndarray) -> np.ndarray:
    near = _near(t, wins)
    if near.size == 0:
        return np.zeros(t.shape, dtype=bool)
    return ((t[:, None] >= near[:, 0]) & (t[:, None] < near[:, 1])).any(axis=1)


def operating_factor(
    t: np.ndarray, shutdowns: np.ndarray, ramp_down_h: float = 1.0, ramp_up_h: float = 5.0
) -> np.ndarray:
    """1.0 when fully running, 0.0 inside a shutdown, linear ramps on both sides."""
    factor = np.ones_like(t)
    for start, end in _near(t, shutdowns, margin=max(ramp_down_h, ramp_up_h)):
        factor = np.where((t >= start) & (t < end), 0.0, factor)
        ramp_up = (t >= end) & (t < end + ramp_up_h)
        factor = np.where(ramp_up, np.minimum(factor, (t - end) / ramp_up_h), factor)
        ramp_down = (t >= start - ramp_down_h) & (t < start)
        factor = np.where(ramp_down, np.minimum(factor, (start - t) / ramp_down_h), factor)
    return factor
