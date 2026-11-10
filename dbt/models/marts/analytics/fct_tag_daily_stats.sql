-- Alarm exceedances use the hourly mean, as emission limits apply to averaged values.
with hourly as (

    select * from {{ ref('fct_readings_hourly') }}

),

tags as (

    select * from {{ ref('dim_tags') }}

),

site_days as (

    select
        site_id,
        cast(local_hour_start as date) as local_date,
        count(*) as observed_hours
    from {{ ref('int_site_hourly_status') }}
    group by site_id, cast(local_hour_start as date)

),

daily as (

    select
        hourly.tag_id,
        hourly.site_id,
        hourly.tag_name,
        hourly.local_date,
        cast(sum(hourly.valid_sample_count) as bigint) as valid_sample_count,
        cast(sum(hourly.invalid_sample_count) as bigint) as invalid_sample_count,
        avg(hourly.avg_value) as avg_value,
        min(hourly.min_value) as min_value,
        max(hourly.max_value) as max_value,
        count(*) filter (
            where tags.alarm_high is not null and hourly.avg_value > tags.alarm_high
        ) as alarm_exceedance_hours
    from hourly
    inner join tags on hourly.tag_id = tags.tag_id
    group by hourly.tag_id, hourly.site_id, hourly.tag_name, hourly.local_date

)

select
    daily.tag_id,
    daily.site_id,
    daily.tag_name,
    tags.measurement_category,
    daily.local_date,
    daily.valid_sample_count,
    daily.invalid_sample_count,
    site_days.observed_hours * cast(3600 / tags.sampling_seconds as integer) as expected_sample_count,
    least(
        daily.valid_sample_count / (site_days.observed_hours * (3600 / tags.sampling_seconds)),
        1.0
    ) as completeness_ratio,
    daily.avg_value,
    daily.min_value,
    daily.max_value,
    daily.alarm_exceedance_hours
from daily
inner join tags on daily.tag_id = tags.tag_id
inner join site_days
    on daily.site_id = site_days.site_id
    and daily.local_date = site_days.local_date
