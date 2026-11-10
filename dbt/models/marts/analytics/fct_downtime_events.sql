-- Gaps and islands: consecutive stopped hours share the same island key.
with stopped as (

    select
        site_id,
        hour_start,
        local_hour_start,
        hour_start - interval 1 hour * row_number() over (
            partition by site_id order by hour_start
        ) as island_key
    from {{ ref('int_site_hourly_status') }}
    where hourly_status = 'stopped'

),

observed as (

    select
        min(hour_start) as first_hour,
        max(hour_start) as last_hour
    from {{ ref('int_site_hourly_status') }}

),

events as (

    select
        site_id,
        min(hour_start) as started_at,
        max(hour_start) + interval 1 hour as ended_at,
        min(local_hour_start) as local_started_at,
        cast(count(*) as integer) as duration_hours
    from stopped
    group by site_id, island_key

)

select
    {{ surrogate_key(['events.site_id', 'events.started_at']) }} as downtime_event_id,
    events.site_id,
    events.started_at,
    events.ended_at,
    events.local_started_at,
    cast(events.local_started_at as date) as local_start_date,
    events.duration_hours,
    case
        when events.duration_hours < {{ var('downtime_short_trip_max_hours') }} then 'short_trip'
        when events.duration_hours < {{ var('downtime_maintenance_min_hours') }} then 'extended_stop'
        else 'long_shutdown'
    end as event_category,
    -- Events touching the edge of the observed period may be longer than they look.
    (events.started_at = observed.first_hour or events.ended_at > observed.last_hour) as is_censored
from events
cross join observed
