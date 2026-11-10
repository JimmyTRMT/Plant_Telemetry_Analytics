-- Deduplication guarantees at most one sample per tag and timestamp.
select *
from {{ ref('fct_readings_hourly') }}
where valid_sample_count > expected_sample_count
