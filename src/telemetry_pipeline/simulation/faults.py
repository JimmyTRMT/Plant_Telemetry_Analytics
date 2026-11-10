"""Sample-level data defects that the transformation layer is expected to absorb."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SENTINEL_VALUE = -9999.0


@dataclass(frozen=True)
class FaultRates:
    missing: float = 0.004
    bad_quality: float = 0.008
    uncertain_quality: float = 0.007
    sentinel: float = 0.001
    spike: float = 0.001
    duplicate: float = 0.003


def apply_sample_faults(
    rng: np.random.Generator, values: np.ndarray, rates: FaultRates
) -> tuple[np.ndarray, np.ndarray]:
    """Inject spikes, sentinel values and quality flags. Returns (values, quality)."""
    n = values.size
    draws = rng.random((4, n))

    values = np.where(draws[0] < rates.spike, values * rng.uniform(3.0, 6.0, n), values)

    sentinel = draws[1] < rates.sentinel
    values = np.where(sentinel, SENTINEL_VALUE, values)

    bad = draws[2] < rates.bad_quality
    uncertain = ~bad & (draws[2] < rates.bad_quality + rates.uncertain_quality)
    quality = np.where(bad, "BAD", np.where(uncertain, "UNCERTAIN", "GOOD"))

    # Devices flag only half of their sentinel values; the rest slip through as GOOD.
    quality = np.where(sentinel & (draws[3] < 0.5), "BAD", quality)
    return values, quality
