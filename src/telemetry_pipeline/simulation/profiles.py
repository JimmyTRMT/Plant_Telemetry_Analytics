"""Physical behaviour of each tag. Adding a tag to the catalog means adding a profile here."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalProfile:
    nominal: float  # value at full load; per MW of site capacity when scales_with_capacity
    idle_ratio: float  # share of nominal kept while the plant is stopped
    load_sensitivity: float  # how strongly the signal follows the load factor
    noise_ratio: float  # relative gaussian noise
    scales_with_capacity: bool = False


PROFILES: dict[str, SignalProfile] = {
    "STEAM_PRESSURE": SignalProfile(62.0, 0.08, 0.10, 0.004),
    "STEAM_TEMPERATURE": SignalProfile(420.0, 0.25, 0.05, 0.004),
    "FLUE_GAS_TEMPERATURE": SignalProfile(950.0, 0.30, 0.08, 0.006),
    "TURBINE_POWER": SignalProfile(0.96, 0.0, 1.0, 0.006, scales_with_capacity=True),
    "WASTE_FEED_RATE": SignalProfile(1.6, 0.0, 1.0, 0.015, scales_with_capacity=True),
    "FEEDWATER_FLOW": SignalProfile(3.9, 0.0, 0.9, 0.010, scales_with_capacity=True),
    "STACK_NOX": SignalProfile(120.0, 0.0, 0.35, 0.030),
    "STACK_CO": SignalProfile(18.0, 0.0, 0.50, 0.060),
}
