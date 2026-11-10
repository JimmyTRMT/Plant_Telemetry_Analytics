with hours as (

    select
        *,
        cast(local_hour_start as date) as local_date
    from {{ ref('int_site_hourly_status') }}

),

status as (

    select
        site_id,
        local_date,
        count(*) as observed_hours,
        -- A day is complete when the grid reaches both its first and its last local hour.
        (
            min(local_hour_start) = cast(local_date as timestamp)
            and max(local_hour_start) = cast(local_date as timestamp) + interval 23 hour
        ) as is_complete_day,
        count(*) filter (where hourly_status = 'running') as running_hours,
        count(*) filter (where hourly_status = 'stopped') as stopped_hours,
        count(*) filter (where hourly_status = 'no_data') as no_data_hours,
        -- mean MW over one hour equals MWh
        sum(avg_power_mw) as energy_mwh
    from hours
    group by site_id, local_date

),

feed as (

    select
        hours.site_id,
        hours.local_date,
        avg(hourly.avg_value) as avg_waste_feed_tph
    from hours
    inner join {{ ref('int_readings_hourly') }} as hourly
        on hours.site_id = hourly.site_id
        and hours.hour_start = hourly.hour_start
    where hours.hourly_status = 'running'
        and hourly.tag_name = '{{ var("feed_tag_name") }}'
    group by hours.site_id, hours.local_date

),

quality as (

    select
        site_id,
        local_date,
        cast(
            coalesce(sum(alarm_exceedance_hours) filter (where measurement_category = 'emission'), 0)
            as integer
        ) as emission_exceedance_hours,
        avg(completeness_ratio) as data_completeness_ratio
    from {{ ref('fct_tag_daily_stats') }}
    group by site_id, local_date

)

select
    status.site_id,
    status.local_date,
    cast(status.observed_hours as integer) as observed_hours,
    cast(status.running_hours as integer) as running_hours,
    cast(status.stopped_hours as integer) as stopped_hours,
    cast(status.no_data_hours as integer) as no_data_hours,
    status.is_complete_day,
    status.energy_mwh,
    status.energy_mwh
        / nullif(sites.nominal_power_mw * (status.running_hours + status.stopped_hours), 0) as capacity_factor,
    status.running_hours
        / nullif(status.running_hours + status.stopped_hours, 0) as availability_ratio,
    feed.avg_waste_feed_tph,
    quality.emission_exceedance_hours,
    quality.data_completeness_ratio
from status
inner join {{ ref('dim_sites') }} as sites on status.site_id = sites.site_id
left join feed
    on status.site_id = feed.site_id
    and status.local_date = feed.local_date
left join quality
    on status.site_id = quality.site_id
    and status.local_date = quality.local_date
