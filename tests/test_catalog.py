from telemetry_pipeline.simulation.profiles import PROFILES


def test_every_catalog_tag_has_a_signal_profile(tags):
    assert {tag.tag_name for tag in tags} <= set(PROFILES)


def test_catalog_ranges_are_coherent(tags):
    for tag in tags:
        assert tag.min_valid < tag.max_valid
        assert 86_400 % tag.sampling_seconds == 0
        if tag.alarm_high is not None:
            assert tag.min_valid < tag.alarm_high < tag.max_valid


def test_site_ids_are_unique(sites):
    assert len({site.site_id for site in sites}) == len(sites)
