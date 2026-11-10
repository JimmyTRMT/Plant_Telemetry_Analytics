{% docs validation_status %}
Verdict of the validation rules, evaluated in this order:
`missing_value`, `bad_quality` (device flag), `sentinel_value` (placeholder such as -9999),
`out_of_range` (outside the limits of the tag catalog), otherwise `valid`.
{% enddocs %}

{% docs local_date %}
Calendar date in the local timezone of the site, so daily figures match plant shifts rather than UTC days.
{% enddocs %}

{% docs __overview__ %}
# Plant telemetry

Sensor readings from four fictional energy-from-waste plants, from the raw historian export to
the marts that feed the dashboard.

| Layer | Schema | What happens there |
| --- | --- | --- |
| Source | `raw` | Parquet exports landed by the ingestion step |
| Staging | `staging` | Typing, renaming, one model per source |
| Intermediate | `intermediate` | Deduplication, validation, hourly aggregation, site status |
| Marts | `marts` | Dimensions and facts consumed by the dashboard |

Business rules live in the project variables (`dbt_project.yml`): validity ranges come from the
tag catalog, the running threshold and the downtime categories are variables.
{% enddocs %}
