"""Idempotent loader: raw parquet files to the DuckDB raw schema.

Each file is tracked by name and checksum. An unchanged file is skipped, a changed file
replaces the rows it previously contributed, so reruns never create duplicates.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb

LOGGER = logging.getLogger(__name__)

DDL = """
create schema if not exists raw;

create table if not exists raw.readings (
    site_id varchar,
    tag_name varchar,
    ts_utc timestamp,
    value double,
    quality varchar,
    _source_file varchar,
    _ingested_at timestamp
);

create table if not exists raw.load_log (
    source_file varchar,
    file_md5 varchar,
    row_count bigint,
    loaded_at timestamp
);
"""


@dataclass(frozen=True)
class LoadSummary:
    files_seen: int
    files_loaded: int
    rows_loaded: int


def _md5(path: Path) -> str:
    digest = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _replace_file(con: duckdb.DuckDBPyConnection, path: Path, checksum: str) -> int:
    loaded_at = datetime.now(timezone.utc).replace(tzinfo=None)
    con.execute("begin")
    try:
        con.execute("delete from raw.readings where _source_file = ?", [path.name])
        con.execute(
            """
            insert into raw.readings
            select
                site_id,
                tag_name,
                cast(ts_utc as timestamp),
                cast(value as double),
                quality,
                cast(? as varchar),
                cast(? as timestamp)
            from read_parquet(?)
            """,
            [path.name, loaded_at, path.as_posix()],
        )
        counted = con.execute(
            "select count(*) from raw.readings where _source_file = ?", [path.name]
        ).fetchone()
        row_count = counted[0] if counted else 0
        con.execute("delete from raw.load_log where source_file = ?", [path.name])
        con.execute(
            "insert into raw.load_log values (?, ?, ?, ?)",
            [path.name, checksum, row_count, loaded_at],
        )
        con.execute("commit")
    except Exception:
        con.execute("rollback")
        raise
    return row_count


def load_readings(db_path: Path, raw_dir: Path) -> LoadSummary:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    files = sorted(raw_dir.glob("readings_*.parquet"))
    loaded = rows = 0
    with duckdb.connect(str(db_path)) as con:
        con.execute(DDL)
        known = dict(con.execute("select source_file, file_md5 from raw.load_log").fetchall())
        for path in files:
            checksum = _md5(path)
            if known.get(path.name) == checksum:
                continue
            rows += _replace_file(con, path, checksum)
            loaded += 1
            LOGGER.info("loaded %s", path.name)
    return LoadSummary(files_seen=len(files), files_loaded=loaded, rows_loaded=rows)
