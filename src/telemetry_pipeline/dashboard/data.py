"""Read-only queries against the marts schema, shaped for the dashboard pages."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

import duckdb

Row = dict[str, Any]

# Complete local days inside the requested window. The window length is a session variable,
# so no query below is assembled from text.
RECENT_DAYS_VIEW = """
    create or replace temp view recent_days as
    select kpis.*, sites.site_name, sites.nominal_power_mw
    from marts.fct_site_daily_kpis as kpis
    inner join marts.dim_sites as sites using (site_id)
    where kpis.is_complete_day
        and kpis.local_date > (
            select max(local_date) from marts.fct_site_daily_kpis where is_complete_day
        ) - to_days(getvariable('window_days')::int)
"""


@dataclass(frozen=True)
class DashboardData:
    generated_at: datetime
    window_days: int
    first_day: date
    last_day: date
    sites: list[Row]
    daily: list[Row]
    downtime: list[Row]
    tag_daily: list[Row]
    flatlines: list[Row]

    def to_payload(self) -> dict[str, Any]:
        """JSON-ready dictionary read by the page scripts. Keys are camelCase on purpose."""
        return {
            "meta": {
                "generatedAt": _json_value(self.generated_at),
                "windowDays": self.window_days,
                "firstDay": _json_value(self.first_day),
                "lastDay": _json_value(self.last_day),
            },
            "sites": [
                {
                    "id": row["site_id"],
                    "name": row["site_name"],
                    "country": row["country"],
                    "nominalPowerMw": _json_value(row["nominal_power_mw"]),
                }
                for row in self.sites
            ],
            "daily": [
                {
                    "site": row["site_id"],
                    "date": _json_value(row["local_date"]),
                    "energyMwh": _json_value(row["energy_mwh"]),
                    "runningHours": row["running_hours"],
                    "stoppedHours": row["stopped_hours"],
                    "exceedanceHours": row["emission_exceedance_hours"],
                    "completeness": _json_value(row["data_completeness_ratio"]),
                }
                for row in self.daily
            ],
            "downtime": [
                {
                    "site": row["site_id"],
                    "start": _json_value(row["started_at"]),
                    "end": _json_value(row["ended_at"]),
                    "localStart": _json_value(row["local_started_at"]),
                    "hours": row["duration_hours"],
                    "category": row["event_category"],
                    "censored": bool(row["is_censored"]),
                }
                for row in self.downtime
            ],
            "tagDaily": [
                {
                    "site": row["site_id"],
                    "tag": row["tag_name"],
                    "date": _json_value(row["local_date"]),
                    "valid": row["valid_sample_count"],
                    "invalid": row["invalid_sample_count"],
                    "completeness": _json_value(row["completeness_ratio"]),
                }
                for row in self.tag_daily
            ],
            "flatlines": [
                {
                    "site": row["site_id"],
                    "tag": row["tag_name"],
                    "start": _json_value(row["started_at"]),
                    "hours": row["duration_hours"],
                    "value": _json_value(row["stuck_value"]),
                }
                for row in self.flatlines
            ],
        }


def _json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[Row]:
    cursor = con.execute(sql)
    names = [column[0] for column in cursor.description]
    return [dict(zip(names, values, strict=True)) for values in cursor.fetchall()]


def fetch_dashboard_data(con: duckdb.DuckDBPyConnection, window_days: int = 30) -> DashboardData:
    con.execute("set variable window_days = ?", [int(window_days)])
    con.execute(RECENT_DAYS_VIEW)

    sites = _rows(
        con,
        "select site_id, site_name, country, nominal_power_mw from marts.dim_sites order by site_id",
    )

    daily = _rows(
        con,
        """
        select
            site_id, local_date, energy_mwh, running_hours, stopped_hours,
            emission_exceedance_hours, data_completeness_ratio
        from recent_days
        order by site_id, local_date
        """,
    )

    # Stops that start inside the window. The rest of the page ignores older events.
    downtime = _rows(
        con,
        """
        with bounds as (select min(local_date) as first_day from recent_days)
        select
            events.site_id, events.started_at, events.ended_at, events.local_started_at,
            events.duration_hours, events.event_category, events.is_censored
        from marts.fct_downtime_events as events
        cross join bounds
        where cast(events.local_started_at as date) >= bounds.first_day
        order by events.started_at
        """,
    )

    tag_daily = _rows(
        con,
        """
        select
            stats.site_id, stats.tag_name, stats.local_date,
            stats.valid_sample_count, stats.invalid_sample_count, stats.completeness_ratio
        from marts.fct_tag_daily_stats as stats
        inner join recent_days using (site_id, local_date)
        order by stats.site_id, stats.tag_name, stats.local_date
        """,
    )

    flatlines = _rows(
        con,
        """
        select site_id, tag_name, started_at, duration_hours, stuck_value
        from marts.fct_sensor_flatlines
        order by started_at desc
        limit 50
        """,
    )

    days = sorted({row["local_date"] for row in daily})
    return DashboardData(
        generated_at=datetime.now(timezone.utc),
        window_days=window_days,
        first_day=days[0],
        last_day=days[-1],
        sites=sites,
        daily=daily,
        downtime=downtime,
        tag_daily=tag_daily,
        flatlines=flatlines,
    )
