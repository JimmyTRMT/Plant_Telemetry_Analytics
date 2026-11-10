with source as (

    select * from {{ source('raw', 'readings') }}

),

renamed as (

    select
        site_id,
        tag_name,
        site_id || '.' || tag_name as tag_id,
        cast(ts_utc as timestamp) as reading_ts,
        cast(value as double) as reading_value,
        upper(trim(quality)) as quality_code,
        _source_file as source_file,
        cast(_ingested_at as timestamp) as ingested_at
    from source

)

select * from renamed
