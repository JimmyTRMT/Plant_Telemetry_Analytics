with readings as (

    select
        tag_id,
        site_id,
        tag_name,
        date_trunc('hour', reading_ts) as hour_start,
        reading_value,
        is_valid
    from {{ ref('int_readings_validated') }}

),

tags as (

    select tag_name, sampling_seconds from {{ ref('stg_tags') }}

),

hourly as (

    select
        tag_id,
        site_id,
        tag_name,
        hour_start,
        count(*) as sample_count,
        count(*) filter (where is_valid) as valid_sample_count,
        count(*) filter (where not is_valid) as invalid_sample_count,
        avg(reading_value) filter (where is_valid) as avg_value,
        min(reading_value) filter (where is_valid) as min_value,
        max(reading_value) filter (where is_valid) as max_value,
        stddev_pop(reading_value) filter (where is_valid) as stddev_value
    from readings
    group by tag_id, site_id, tag_name, hour_start

)

select
    {{ surrogate_key(['hourly.tag_id', 'hourly.hour_start']) }} as tag_hour_id,
    hourly.tag_id,
    hourly.site_id,
    hourly.tag_name,
    hourly.hour_start,
    hourly.sample_count,
    hourly.valid_sample_count,
    hourly.invalid_sample_count,
    hourly.avg_value,
    hourly.min_value,
    hourly.max_value,
    hourly.stddev_value,
    cast(3600 / tags.sampling_seconds as integer) as expected_sample_count,
    least(hourly.valid_sample_count / (3600 / tags.sampling_seconds), 1.0) as completeness_ratio
from hourly
inner join tags on hourly.tag_name = tags.tag_name
