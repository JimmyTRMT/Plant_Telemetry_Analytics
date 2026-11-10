import numpy as np

from telemetry_pipeline.simulation.faults import SENTINEL_VALUE, FaultRates, apply_sample_faults
from telemetry_pipeline.simulation.generator import generate_day
from telemetry_pipeline.simulation.schedule import operating_factor, window_mask, windows


def test_generation_is_deterministic(sites, tags, sample_day):
    first = generate_day(sample_day, sites, tags)
    second = generate_day(sample_day, sites, tags)
    assert first.equals(second)


def test_schema_and_coverage(sites, tags, sample_day):
    table = generate_day(sample_day, sites, tags)
    assert table.column_names == ["site_id", "tag_name", "ts_utc", "value", "quality"]
    assert set(table["site_id"].to_pylist()) == {site.site_id for site in sites}
    assert set(table["tag_name"].to_pylist()) == {tag.tag_name for tag in tags}
    assert set(table["quality"].to_pylist()) <= {"GOOD", "UNCERTAIN", "BAD"}


def test_timestamps_stay_inside_the_requested_day(sites, tags, sample_day):
    table = generate_day(sample_day, sites, tags)
    days = {ts.date() for ts in table["ts_utc"].to_pylist()}
    assert days == {sample_day}


def test_event_windows_are_ordered_and_disjoint():
    for kind in ("maintenance", "trip", "excursion", "comm_outage"):
        wins = windows(kind, "SITE_01")
        assert (wins[:, 0] < wins[:, 1]).all()
        assert (wins[1:, 0] >= wins[:-1, 1]).all()


def test_operating_factor_is_zero_inside_a_shutdown_and_one_far_away():
    shutdowns = np.array([[100.0, 120.0]])
    t = np.array([50.0, 99.5, 110.0, 122.5, 200.0])
    factor = operating_factor(t, shutdowns)
    assert factor[0] == 1.0
    assert 0.0 < factor[1] < 1.0
    assert factor[2] == 0.0
    assert 0.0 < factor[3] < 1.0
    assert factor[4] == 1.0


def test_window_mask_matches_half_open_interval():
    wins = np.array([[10.0, 12.0]])
    mask = window_mask(np.array([9.99, 10.0, 11.99, 12.0]), wins)
    assert mask.tolist() == [False, True, True, False]


def test_fault_injection_flags_sentinels_and_keeps_good_values_untouched():
    rng = np.random.default_rng(1)
    values = np.full(50_000, 10.0)
    rates = FaultRates(sentinel=0.01, spike=0.0)
    faulted, quality = apply_sample_faults(rng, values, rates)
    assert (faulted == SENTINEL_VALUE).any()
    untouched = (faulted == 10.0) & (quality == "GOOD")
    assert untouched.mean() > 0.95
