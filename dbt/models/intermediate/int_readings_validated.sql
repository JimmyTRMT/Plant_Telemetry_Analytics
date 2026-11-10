with readings as (

    select * from {{ ref('int_readings_deduplicated') }}

),

tags as (

    select * from {{ ref('stg_tags') }}

),

validated as (

    select
        {{ surrogate_key(['readings.tag_id', 'readings.reading_ts']) }} as reading_id,
        readings.tag_id,
        readings.site_id,
        readings.tag_name,
        readings.reading_ts,
        readings.reading_value,
        readings.quality_code,
        case
            when readings.reading_value is null then 'missing_value'
            when readings.quality_code = 'BAD' then 'bad_quality'
            when readings.reading_value in ({{ var('sentinel_values') | join(', ') }}) then 'sentinel_value'
            when readings.reading_value < tags.min_valid
                or readings.reading_value > tags.max_valid then 'out_of_range'
            else 'valid'
        end as validation_status
    from readings
    inner join tags on readings.tag_name = tags.tag_name

)

select
    *,
    validation_status = 'valid' as is_valid
from validated
