{{
    config(
        materialized='incremental',
        unique_key='tag_hour_id',
        incremental_strategy='delete+insert',
        on_schema_change='append_new_columns'
    )
}}

with hourly as (

    select * from {{ ref('int_readings_hourly') }}

    {% if is_incremental() %}
    where hour_start >= (
        select coalesce(max(hour_start), timestamp '1970-01-01') - interval {{ var('incremental_lookback_days') }} day
        from {{ this }}
    )
    {% endif %}

),

localised as (

    select
        hourly.*,
        {{ to_local_time('hourly.hour_start', 'sites.timezone') }} as local_hour_start
    from hourly
    inner join {{ ref('stg_sites') }} as sites on hourly.site_id = sites.site_id

)

select
    tag_hour_id,
    tag_id,
    site_id,
    tag_name,
    hour_start,
    local_hour_start,
    cast(local_hour_start as date) as local_date,
    sample_count,
    valid_sample_count,
    invalid_sample_count,
    expected_sample_count,
    completeness_ratio,
    avg_value,
    min_value,
    max_value,
    stddev_value
from localised
