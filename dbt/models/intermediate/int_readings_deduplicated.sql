-- Keep one row per tag and timestamp: best quality first, then the latest load.
with ranked as (

    select
        *,
        row_number() over (
            partition by tag_id, reading_ts
            order by
                case quality_code when 'GOOD' then 1 when 'UNCERTAIN' then 2 else 3 end,
                ingested_at desc,
                reading_value
        ) as row_rank
    from {{ ref('stg_readings') }}

)

select * exclude (row_rank)
from ranked
where row_rank = 1
