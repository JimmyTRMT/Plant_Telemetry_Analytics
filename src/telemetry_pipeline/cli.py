"""Command line entry point: simulate, ingest, transform, dashboard, serve, run."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from telemetry_pipeline.catalog import load_sites, load_tags
from telemetry_pipeline.dashboard.render import build_dashboard
from telemetry_pipeline.ingestion.loader import load_readings
from telemetry_pipeline.settings import Paths
from telemetry_pipeline.simulation.generator import simulate

LOGGER = logging.getLogger("telemetry")


def _yesterday_utc() -> date:
    return datetime.now(timezone.utc).date() - timedelta(days=1)


def _simulate(args: argparse.Namespace, paths: Paths) -> None:
    end = args.end_date or _yesterday_utc()
    start = end - timedelta(days=args.days - 1)
    files = simulate(start, end, paths.raw_dir, load_sites(), load_tags())
    LOGGER.info("simulated %d days (%s to %s)", len(files), start, end)


def _ingest(_: argparse.Namespace, paths: Paths) -> None:
    summary = load_readings(paths.warehouse, paths.raw_dir)
    LOGGER.info(
        "ingested %d/%d files, %d rows",
        summary.files_loaded,
        summary.files_seen,
        summary.rows_loaded,
    )


def _run_dbt(arguments: list[str], paths: Paths) -> None:
    from dbt.cli.main import dbtRunner

    os.environ["DUCKDB_PATH"] = str(paths.warehouse)
    result = dbtRunner().invoke(
        [*arguments, "--project-dir", str(paths.dbt_dir), "--profiles-dir", str(paths.dbt_dir)]
    )
    if not result.success:
        if result.exception:
            LOGGER.error("dbt failed: %s", result.exception)
        raise SystemExit(1)


def _transform(args: argparse.Namespace, paths: Paths) -> None:
    command = ["build"]
    if args.select:
        command += ["--select", args.select]
    _run_dbt(command, paths)
    if args.docs:
        _run_dbt(["docs", "generate"], paths)


def _dashboard(args: argparse.Namespace, paths: Paths) -> None:
    pages = build_dashboard(
        paths.warehouse, args.output, args.window_days, paths.dbt_dir / "target"
    )
    LOGGER.info("dashboard written to %s (%d pages)", args.output, len(pages))


def _serve(args: argparse.Namespace, _: Paths) -> None:
    """Serve the built site. A local server is needed because the dbt docs load JSON files,
    which browsers refuse to read from a file:// address."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(args.directory))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        LOGGER.info("serving %s at http://127.0.0.1:%d (Ctrl+C to stop)", args.directory, args.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            LOGGER.info("stopped")


def _run(args: argparse.Namespace, paths: Paths) -> None:
    _simulate(args, paths)
    _ingest(args, paths)
    _transform(args, paths)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="telemetry", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    def add_simulation_options(command: argparse.ArgumentParser) -> None:
        command.add_argument("--days", type=int, default=45, help="Number of days to generate")
        command.add_argument(
            "--end-date",
            type=date.fromisoformat,
            help="Last day to generate, YYYY-MM-DD (default: yesterday, UTC)",
        )

    add_simulation_options(commands.add_parser("simulate", help="Generate raw parquet files"))
    commands.add_parser("ingest", help="Load raw files into DuckDB")

    transform = commands.add_parser("transform", help="Run dbt build")
    transform.add_argument("--select", help="dbt node selection")
    transform.add_argument("--docs", action="store_true", help="Also generate dbt docs")

    dashboard = commands.add_parser("dashboard", help="Build the static dashboard")
    dashboard.add_argument("--output", type=Path, default=Path("site"), help="Output folder")
    dashboard.add_argument("--window-days", type=int, default=30, help="Days shown on the pages")

    serve = commands.add_parser("serve", help="Serve the built dashboard on localhost")
    serve.add_argument("--directory", type=Path, default=Path("site"), help="Folder to serve")
    serve.add_argument("--port", type=int, default=8000, help="Port to listen on")

    run = commands.add_parser("run", help="simulate, ingest and transform in one go")
    add_simulation_options(run)
    run.add_argument("--select", help="dbt node selection")
    run.add_argument("--docs", action="store_true", help="Also generate dbt docs")
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = _build_parser().parse_args(argv)
    handlers = {
        "simulate": _simulate,
        "ingest": _ingest,
        "transform": _transform,
        "dashboard": _dashboard,
        "serve": _serve,
        "run": _run,
    }
    handlers[args.command](args, Paths())
    return 0


if __name__ == "__main__":
    sys.exit(main())
