from datetime import date

import pytest

from telemetry_pipeline.catalog import load_sites, load_tags


@pytest.fixture(scope="session")
def sites():
    return load_sites()


@pytest.fixture(scope="session")
def tags():
    return load_tags()


@pytest.fixture
def sample_day() -> date:
    return date(2026, 3, 14)
