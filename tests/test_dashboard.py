import json
import re
from datetime import date, datetime, timezone

import duckdb
import pytest

from telemetry_pipeline.dashboard.data import DashboardData, fetch_dashboard_data
from telemetry_pipeline.dashboard.render import PAGES, render_site, repository_url


def _fake_data() -> DashboardData:
    day = date(2026, 3, 2)
    start = datetime(2026, 3, 2, 8, 0)
    return DashboardData(
        generated_at=datetime(2026, 3, 3, tzinfo=timezone.utc),
        window_days=30,
        first_day=day,
        last_day=date(2026, 3, 3),
        sites=[
            {
                "site_id": "SITE_01",
                "site_name": "Aurora",
                "country": "France",
                "nominal_power_mw": 24.0,
            }
        ],
        daily=[
            {
                "site_id": "SITE_01",
                "local_date": day,
                "energy_mwh": 500.0,
                "running_hours": 23,
                "stopped_hours": 1,
                "emission_exceedance_hours": 0,
                "data_completeness_ratio": 0.98,
            }
        ],
        downtime=[
            {
                "site_id": "SITE_01",
                "started_at": start,
                "ended_at": datetime(2026, 3, 2, 12, 0),
                "local_started_at": datetime(2026, 3, 2, 9, 0),
                "duration_hours": 4,
                "event_category": "short_trip",
                "is_censored": False,
            }
        ],
        tag_daily=[
            {
                "site_id": "SITE_01",
                "tag_name": "STEAM_PRESSURE",
                "local_date": day,
                "valid_sample_count": 1400,
                "invalid_sample_count": 12,
                "completeness_ratio": 0.98,
            }
        ],
        flatlines=[
            {
                "site_id": "SITE_01",
                "tag_name": "STEAM_PRESSURE",
                "started_at": start,
                "duration_hours": 6,
                "stuck_value": 61.5,
            }
        ],
    )


def _embedded_payload(html: str) -> dict:
    match = re.search(
        r'<script type="application/json" id="dashboard-data">(.*?)</script>', html, re.S
    )
    assert match, "payload script not found"
    return json.loads(match.group(1).replace("<\\/", "</"))


@pytest.fixture
def site(tmp_path):
    render_site(_fake_data(), tmp_path)
    return tmp_path


def test_every_page_and_asset_is_written(site):
    assert {page.filename for page in PAGES} == {
        "index.html",
        "operations.html",
        "data-quality.html",
        "about.html",
    }
    for page in PAGES:
        assert (site / page.filename).exists()
    for asset in ("app.js", "charts.js", "pages.js", "style.css", "plotly.min.js"):
        assert (site / "assets" / asset).stat().st_size > 0
    assert (site / ".nojekyll").exists()


def test_payload_is_embedded_with_camel_case_keys(site):
    payload = _embedded_payload((site / "index.html").read_text(encoding="utf-8"))

    assert set(payload) == {"meta", "sites", "daily", "downtime", "tagDaily", "flatlines"}
    assert payload["sites"][0] == {
        "id": "SITE_01",
        "name": "Aurora",
        "country": "France",
        "nominalPowerMw": 24.0,
    }
    assert payload["daily"][0]["date"] == "2026-03-02"
    assert payload["downtime"][0]["localStart"] == "2026-03-02T09:00:00"
    assert payload["flatlines"][0]["value"] == 61.5


def test_about_page_has_no_payload_and_filters(site):
    html = (site / "about.html").read_text(encoding="utf-8")
    assert "dashboard-data" not in html
    assert 'id="period"' not in html


def test_pages_load_no_external_resources(site):
    for page in PAGES:
        html = (site / page.filename).read_text(encoding="utf-8")
        assert not re.search(r'(?:src|href)="https?://', html), page.filename


def test_repository_link_only_when_known(tmp_path):
    render_site(_fake_data(), tmp_path)
    assert "Source code" not in (tmp_path / "index.html").read_text(encoding="utf-8")

    linked = tmp_path / "linked"
    render_site(_fake_data(), linked, repository="https://github.com/example/plant-telemetry")
    html = (linked / "index.html").read_text(encoding="utf-8")
    assert 'href="https://github.com/example/plant-telemetry"' in html


def test_repository_url_reads_the_environment(monkeypatch):
    monkeypatch.delenv("TELEMETRY_REPOSITORY_URL", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert repository_url() is None

    monkeypatch.setenv("GITHUB_REPOSITORY", "example/plant-telemetry")
    assert repository_url() == "https://github.com/example/plant-telemetry"

    monkeypatch.setenv("TELEMETRY_REPOSITORY_URL", "https://example.org/code")
    assert repository_url() == "https://example.org/code"


def test_dbt_docs_are_linked_only_when_generated(tmp_path):
    target = tmp_path / "target"
    target.mkdir()

    bare = tmp_path / "bare"
    render_site(_fake_data(), bare, dbt_target=target)
    assert "dbt-docs" not in (bare / "index.html").read_text(encoding="utf-8")
    assert not (bare / "dbt-docs").exists()

    (target / "index.html").write_text("<html>docs</html>", encoding="utf-8")
    (target / "manifest.json").write_text("{}", encoding="utf-8")
    bundled = tmp_path / "bundled"
    render_site(_fake_data(), bundled, dbt_target=target)
    assert 'href="dbt-docs/index.html"' in (bundled / "index.html").read_text(encoding="utf-8")
    assert (bundled / "dbt-docs" / "manifest.json").exists()


def test_fetch_keeps_only_complete_days_inside_the_window():
    con = duckdb.connect(":memory:")
    con.execute("create schema marts")
    con.execute(
        "create table marts.dim_sites as select 'S1' as site_id, 'Aurora' as site_name, "
        "'France' as country, 24.0 as nominal_power_mw"
    )
    con.execute(
        """
        create table marts.fct_site_daily_kpis as
        select 'S1' as site_id, d::date as local_date, 100.0 as energy_mwh,
            20 as running_hours, 4 as stopped_hours, 0 as emission_exceedance_hours,
            0.99 as data_completeness_ratio,
            d::date <> date '2026-03-10' as is_complete_day
        from generate_series(date '2026-03-01', date '2026-03-10', interval 1 day) as t(d)
        """
    )
    con.execute(
        """
        create table marts.fct_downtime_events as
        select 'S1' as site_id, ts as started_at, ts + interval 3 hour as ended_at,
            ts as local_started_at, 3 as duration_hours, 'short_trip' as event_category,
            false as is_censored
        from (values (timestamp '2026-03-01 05:00'), (timestamp '2026-03-08 05:00')) as t(ts)
        """
    )
    con.execute(
        """
        create table marts.fct_tag_daily_stats as
        select 'S1' as site_id, 'STEAM_PRESSURE' as tag_name, local_date,
            1400 as valid_sample_count, 10 as invalid_sample_count, 0.98 as completeness_ratio
        from marts.fct_site_daily_kpis
        """
    )
    con.execute(
        "create table marts.fct_sensor_flatlines as select 'S1' as site_id, "
        "'STEAM_PRESSURE' as tag_name, timestamp '2026-03-05 01:00' as started_at, "
        "5 as duration_hours, 12.5 as stuck_value"
    )

    data = fetch_dashboard_data(con, window_days=3)

    assert [row["local_date"] for row in data.daily] == [
        date(2026, 3, 7),
        date(2026, 3, 8),
        date(2026, 3, 9),
    ]
    assert (data.first_day, data.last_day) == (date(2026, 3, 7), date(2026, 3, 9))
    assert [row["started_at"] for row in data.downtime] == [datetime(2026, 3, 8, 5, 0)]
    assert len(data.tag_daily) == 3
    assert len(data.flatlines) == 1
