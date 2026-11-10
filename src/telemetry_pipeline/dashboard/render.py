"""Turn DashboardData into a folder of static HTML files."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import duckdb
import plotly.offline
from jinja2 import Environment, FileSystemLoader, select_autoescape

from telemetry_pipeline.dashboard.data import DashboardData, fetch_dashboard_data

PACKAGE_DIR = Path(__file__).parent
DBT_DOCS_FILES = ("index.html", "manifest.json", "catalog.json")


@dataclass(frozen=True)
class Page:
    key: str
    filename: str
    template: str
    label: str
    title: str
    has_filters: bool


PAGES = [
    Page("overview", "index.html", "overview.html.j2", "Overview", "Fleet performance", True),
    Page(
        "operations",
        "operations.html",
        "operations.html.j2",
        "Operations",
        "Plant operations",
        True,
    ),
    Page(
        "quality", "data-quality.html", "data_quality.html.j2", "Data quality", "Data quality", True
    ),
    Page("about", "about.html", "about.html.j2", "About", "About this dashboard", False),
]


def repository_url() -> str | None:
    """Link shown in the header. GitHub Actions provides GITHUB_REPOSITORY, so the published
    site links to the right repository and a local build shows no link at all."""
    explicit = os.environ.get("TELEMETRY_REPOSITORY_URL")
    if explicit:
        return explicit
    repository = os.environ.get("GITHUB_REPOSITORY")
    return f"https://github.com/{repository}" if repository else None


def _environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(PACKAGE_DIR / "templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def _payload_json(data: DashboardData) -> str:
    # "</" would end the script element early, so it is escaped.
    return json.dumps(data.to_payload(), separators=(",", ":")).replace("</", "<\\/")


def _copy_assets(out_dir: Path) -> None:
    assets = out_dir / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    (assets / "plotly.min.js").write_text(plotly.offline.get_plotlyjs(), encoding="utf-8")
    for source in (PACKAGE_DIR / "static").iterdir():
        shutil.copy(source, assets / source.name)
    (out_dir / ".nojekyll").touch()


def _copy_dbt_docs(dbt_target: Path | None, out_dir: Path) -> bool:
    """Bundle the dbt docs next to the dashboard. They are only linked when they exist."""
    if dbt_target is None or not (dbt_target / "index.html").exists():
        return False
    docs_dir = out_dir / "dbt-docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for name in DBT_DOCS_FILES:
        if (dbt_target / name).exists():
            shutil.copy(dbt_target / name, docs_dir / name)
    return True


def render_site(
    data: DashboardData,
    out_dir: Path,
    repository: str | None = None,
    dbt_target: Path | None = None,
) -> list[Path]:
    _copy_assets(out_dir)
    has_docs = _copy_dbt_docs(dbt_target, out_dir)
    env = _environment()
    payload = _payload_json(data)

    written = []
    for page in PAGES:
        html = env.get_template(page.template).render(
            page=page,
            pages=PAGES,
            data=data,
            payload=payload,
            repository_url=repository,
            has_docs=has_docs,
        )
        target = out_dir / page.filename
        target.write_text(html, encoding="utf-8")
        written.append(target)
    return written


def build_dashboard(
    warehouse: Path,
    out_dir: Path,
    window_days: int = 30,
    dbt_target: Path | None = None,
) -> list[Path]:
    with duckdb.connect(str(warehouse), read_only=True) as con:
        data = fetch_dashboard_data(con, window_days)
    return render_site(data, out_dir, repository_url(), dbt_target)
