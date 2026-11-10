from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from telemetry_pipeline import cli
from telemetry_pipeline.settings import Paths


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    """Point every stage at a throwaway folder so no test touches the real warehouse."""
    paths = Paths(root=tmp_path)
    monkeypatch.setattr(cli, "Paths", lambda: paths)
    monkeypatch.setenv("DUCKDB_PATH", str(tmp_path / "warehouse.duckdb"))
    return paths


def test_simulate_then_ingest_is_repeatable(workspace):
    cli.main(["simulate", "--days", "2", "--end-date", "2026-03-14"])
    files = sorted(workspace.raw_dir.glob("*.parquet"))
    assert [file.stem for file in files] == ["readings_2026-03-13", "readings_2026-03-14"]

    cli.main(["ingest"])
    cli.main(["ingest"])
    assert workspace.warehouse.exists()


def test_transform_builds_then_generates_docs_when_asked(workspace, monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run_dbt", lambda arguments, paths: calls.append(arguments))

    cli.main(["transform", "--select", "stg_readings", "--docs"])

    assert calls == [["build", "--select", "stg_readings"], ["docs", "generate"]]


def test_run_chains_simulation_ingestion_and_transform(workspace, monkeypatch):
    steps = []
    monkeypatch.setattr(cli, "_simulate", lambda args, paths: steps.append("simulate"))
    monkeypatch.setattr(cli, "_ingest", lambda args, paths: steps.append("ingest"))
    monkeypatch.setattr(cli, "_transform", lambda args, paths: steps.append("transform"))

    cli.main(["run", "--days", "1"])

    assert steps == ["simulate", "ingest", "transform"]


def test_dashboard_receives_the_dbt_target_for_the_docs(workspace, monkeypatch):
    received = {}

    def fake_build(warehouse, output, window_days, dbt_target):
        received.update(warehouse=warehouse, output=output, days=window_days, target=dbt_target)
        return []

    monkeypatch.setattr(cli, "build_dashboard", fake_build)

    cli.main(["dashboard", "--output", "out", "--window-days", "14"])

    assert received == {
        "warehouse": workspace.warehouse,
        "output": Path("out"),
        "days": 14,
        "target": workspace.dbt_dir / "target",
    }


def test_serve_stops_cleanly_on_ctrl_c(workspace, monkeypatch):
    created = {}

    class FakeServer:
        def __init__(self, address, handler):
            created["address"] = address

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(cli, "ThreadingHTTPServer", FakeServer)

    assert cli.main(["serve", "--port", "8123"]) == 0
    assert created["address"] == ("127.0.0.1", 8123)


def test_a_failed_dbt_run_stops_the_pipeline(workspace, monkeypatch):
    class FailingRunner:
        def invoke(self, arguments):
            return SimpleNamespace(success=False, exception=RuntimeError("model failed"))

    monkeypatch.setattr("dbt.cli.main.dbtRunner", FailingRunner)

    with pytest.raises(SystemExit) as stopped:
        cli.main(["transform"])
    assert stopped.value.code == 1


def test_simulation_ends_yesterday_when_no_date_is_given(workspace, monkeypatch):
    window = {}

    def fake_simulate(start, end, out_dir, sites, tags):
        window.update(start=start, end=end)
        return []

    monkeypatch.setattr(cli, "simulate", fake_simulate)
    monkeypatch.setattr(cli, "_yesterday_utc", lambda: date(2026, 3, 31))

    cli.main(["simulate", "--days", "3"])

    assert window == {"start": date(2026, 3, 29), "end": date(2026, 3, 31)}
