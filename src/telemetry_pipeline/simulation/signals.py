"""Noise-free signal model: operating state, daily load cycle and per-tag response."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from telemetry_pipeline.catalog import Site, Tag
from telemetry_pipeline.simulation.profiles import SignalProfile
from telemetry_pipeline.simulation.schedule import (
    operating_factor,
    stable_code,
    window_mask,
    windows,
)

EXCURSION_SHARE = 0.9  # excursion height as a share of the alarm threshold


@dataclass(frozen=True)
class PlantState:
    site: Site
    shutdowns: np.ndarray
    excursions: np.ndarray
    phase: float


def build_state(site: Site) -> PlantState:
    shutdowns = np.vstack([windows("maintenance", site.site_id), windows("trip", site.site_id)])
    return PlantState(
        site=site,
        shutdowns=shutdowns,
        excursions=windows("excursion", site.site_id),
        phase=(stable_code(site.site_id) % 1000) / 1000 * 2 * np.pi,
    )


def load_factor(t: np.ndarray, phase: float) -> np.ndarray:
    """Daily cycle plus a slow multi-day drift, centred on 90 % load."""
    daily = 0.06 * np.sin(2 * np.pi * ((t % 24.0) - 15.0) / 24.0 + phase)
    drift = 0.03 * np.sin(2 * np.pi * t / (24.0 * 3.7) + 2 * phase)
    return 0.90 + daily + drift


def clean_signal(state: PlantState, tag: Tag, profile: SignalProfile, t: np.ndarray) -> np.ndarray:
    running = operating_factor(t, state.shutdowns)
    load = load_factor(t, state.phase)
    base = profile.nominal * (state.site.nominal_power_mw if profile.scales_with_capacity else 1.0)
    level = profile.idle_ratio + (1.0 - profile.idle_ratio) * running
    value = base * level * (1.0 + profile.load_sensitivity * (load - 0.90) * running)
    if tag.measurement_category == "emission" and tag.alarm_high is not None:
        value = (
            value + EXCURSION_SHARE * tag.alarm_high * window_mask(t, state.excursions) * running
        )
    return value
