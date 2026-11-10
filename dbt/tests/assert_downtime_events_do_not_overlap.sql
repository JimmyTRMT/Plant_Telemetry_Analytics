select
    earlier.site_id,
    earlier.downtime_event_id as earlier_event_id,
    later.downtime_event_id as later_event_id
from {{ ref('fct_downtime_events') }} as earlier
inner join {{ ref('fct_downtime_events') }} as later
    on earlier.site_id = later.site_id
    and earlier.downtime_event_id < later.downtime_event_id
    and earlier.started_at < later.ended_at
    and later.started_at < earlier.ended_at
