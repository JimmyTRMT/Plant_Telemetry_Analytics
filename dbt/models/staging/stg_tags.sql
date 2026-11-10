select
    tag_name,
    description,
    unit,
    measurement_category,
    cast(sampling_seconds as integer) as sampling_seconds,
    cast(min_valid as double) as min_valid,
    cast(max_valid as double) as max_valid,
    cast(alarm_high as double) as alarm_high
from {{ ref('tag_catalog') }}
