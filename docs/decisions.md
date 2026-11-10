# Design decisions

Short notes on the choices that shaped the project and what each one costs.

## DuckDB as the warehouse

One file, no server, full SQL with window functions and time zone support. It lets the whole
pipeline run in CI and on a laptop with the same commands. The price is a single writer, so the
loader and dbt must not run at the same time.

## Files first, then a loader

The simulator writes one parquet file per day, like a historian export. The loader tracks each
file by name and checksum, so a rerun is harmless and a corrected file replaces what it loaded
before. Raw rows keep `_source_file` and `_ingested_at` for lineage.

## Validation as data, not as deletion

Rows are never dropped by the pipeline. Each reading gets a `validation_status`, and hourly
statistics use valid samples only. Rejected samples stay countable, which is what the data quality
page of the dashboard shows.

## Catalog-driven rules

Validity ranges, sampling periods and alarm thresholds live in `tag_catalog.csv`. Site level KPIs
read the power and feed tags from two project variables. Adding a plant or a tag does not touch
the SQL, apart from the simulator profile when the tag is synthetic.

## Local days and complete days

Operators read their plant by local calendar day, so daily figures use the site timezone. Because
the data window starts and ends on UTC boundaries, the first and last local days are partial. They
are kept in the table and flagged with `is_complete_day` instead of being hidden.

## Incremental hourly fact

`fct_readings_hourly` is incremental with `delete+insert` and a three day lookback. At this
volume a full rebuild would be as fast. The model exists to show the pattern for late-arriving
data, and the lookback is a project variable.

## Static dashboard

The dashboard is plain HTML generated from the marts, with Plotly bundled in the output folder.
Python reads the marts once and embeds the result as JSON in each page. A small script computes
the figures and draws the charts in the browser, which is what lets the period and plant filters
answer instantly with no server. The theme and the filters are remembered in the browser only.
No server, no account, no external script at view time. I first considered an SQL-in-Markdown
reporting framework, but the one I looked at moved to a hosted product and its open source
package has had no release since February 2026, which is not a base for a site that has to keep
working.

## Scheduled refresh

GitHub disables scheduled workflows on public repositories after 60 days without activity. The
published site is static and stays online, it only stops refreshing. Any push restarts the
schedule.
