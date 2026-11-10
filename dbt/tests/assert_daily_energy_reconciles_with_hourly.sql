-- Daily energy must equal the sum of hourly mean power over the same hours.
with daily as (
    select sum(energy_mwh) as total_mwh
    from {{ ref('fct_site_daily_kpis') }}
),

hourly as (
    select sum(avg_value) as total_mwh
    from {{ ref('fct_readings_hourly') }}
    where tag_name = '{{ var("power_tag_name") }}'
)

select
    daily.total_mwh as daily_total_mwh,
    hourly.total_mwh as hourly_total_mwh
from daily
cross join hourly
where abs(daily.total_mwh - hourly.total_mwh) > 1e-6 * greatest(abs(hourly.total_mwh), 1)
