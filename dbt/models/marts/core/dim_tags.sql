-- Every site exposes every tag of the catalog.
select
    sites.site_id || '.' || tags.tag_name as tag_id,
    sites.site_id,
    tags.tag_name,
    tags.description,
    tags.unit,
    tags.measurement_category,
    tags.sampling_seconds,
    tags.min_valid,
    tags.max_valid,
    tags.alarm_high
from {{ ref('stg_sites') }} as sites
cross join {{ ref('stg_tags') }} as tags
