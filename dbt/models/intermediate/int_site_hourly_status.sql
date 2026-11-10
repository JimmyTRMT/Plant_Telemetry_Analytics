-- One row per site and hour between the first and last reading, including hours without data.
with bounds as (

    select
        min(hour_start) as first_hour,
        max(hour_start) as last_hour
    from {{ ref('int_readings_hourly') }}

),

hours as (

    select unnest(generate_series(first_hour, last_hour, interval 1 hour)) as hour_start
    from bounds

),

grid as (

    select
        sites.site_id,
        sites.timezone,
        sites.nominal_power_mw,
        hours.hour_start
    from {{ ref('stg_sites') }} as sites
    cross join hours

),

power as (

    select
        site_id,
        hour_start,
        avg_value as avg_power_mw
    from {{ ref('int_readings_hourly') }}
    where tag_name = '{{ var("power_tag_name") }}'

)

select
    grid.site_id,
    grid.hour_start,
    {{ to_local_time('grid.hour_start', 'grid.timezone') }} as local_hour_start,
    power.avg_power_mw,
    case
        when power.avg_power_mw is null then 'no_data'
        when power.avg_power_mw >= grid.nominal_power_mw * {{ var('running_threshold_ratio') }} then 'running'
        else 'stopped'
    end as hourly_status
from grid
left join power
    on grid.site_id = power.site_id
    and grid.hour_start = power.hour_start
