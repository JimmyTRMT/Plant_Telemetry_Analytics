-- A running plant never produces a perfectly constant signal: flag stuck sensors.
with candidate_hours as (

    select
        hourly.tag_id,
        hourly.site_id,
        hourly.tag_name,
        hourly.hour_start,
        hourly.avg_value,
        hourly.hour_start - interval 1 hour * row_number() over (
            partition by hourly.tag_id order by hourly.hour_start
        ) as island_key
    from {{ ref('fct_readings_hourly') }} as hourly
    inner join {{ ref('int_site_hourly_status') }} as status
        on hourly.site_id = status.site_id
        and hourly.hour_start = status.hour_start
    where status.hourly_status = 'running'
        and hourly.valid_sample_count >= hourly.expected_sample_count * 0.5
        and hourly.stddev_value <= {{ var('flatline_stddev_epsilon') }}

),

episodes as (

    select
        tag_id,
        site_id,
        tag_name,
        min(hour_start) as started_at,
        max(hour_start) + interval 1 hour as ended_at,
        cast(count(*) as integer) as duration_hours,
        avg(avg_value) as stuck_value
    from candidate_hours
    group by tag_id, site_id, tag_name, island_key

)

select
    {{ surrogate_key(['tag_id', 'started_at']) }} as flatline_id,
    *
from episodes
where duration_hours >= {{ var('flatline_min_hours') }}
