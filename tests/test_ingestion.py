from datetime import date

import duckdb
import pyarrow.parquet as pq

from telemetry_pipeline.ingestion.loader import load_readings
from telemetry_pipeline.simulation.generator import generate_day, simulate, write_day


def _count(db_path) -> int:
    with duckdb.connect(str(db_path)) as con:
        return con.execute("select count(*) from raw.readings").fetchone()[0]


def test_load_is_idempotent(tmp_path, sites, tags):
    raw_dir, db_path = tmp_path / "raw", tmp_path / "wh.duckdb"
    simulate(date(2026, 3, 1), date(2026, 3, 2), raw_dir, sites, tags)

    first = load_readings(db_path, raw_dir)
    rows_after_first = _count(db_path)
    second = load_readings(db_path, raw_dir)

    assert first.files_loaded == 2 and first.rows_loaded == rows_after_first
    assert second.files_loaded == 0
    assert _count(db_path) == rows_after_first


def test_changed_file_replaces_its_previous_rows(tmp_path, sites, tags):
    raw_dir, db_path = tmp_path / "raw", tmp_path / "wh.duckdb"
    day = date(2026, 3, 1)
    simulate(day, day, raw_dir, sites, tags)
    load_readings(db_path, raw_dir)

    smaller = generate_day(day, sites[:1], tags)
    write_day(smaller, raw_dir, day)
    summary = load_readings(db_path, raw_dir)

    assert summary.files_loaded == 1
    assert _count(db_path) == smaller.num_rows


def test_raw_table_keeps_lineage_columns(tmp_path, sites, tags):
    raw_dir, db_path = tmp_path / "raw", tmp_path / "wh.duckdb"
    simulate(date(2026, 3, 1), date(2026, 3, 1), raw_dir, sites, tags)
    load_readings(db_path, raw_dir)
    with duckdb.connect(str(db_path)) as con:
        source, loaded = con.execute(
            "select min(_source_file), count(distinct _ingested_at) from raw.readings"
        ).fetchone()
    assert source == "readings_2026-03-01.parquet"
    assert loaded == 1
    assert pq.read_table(raw_dir / source).num_rows > 0
