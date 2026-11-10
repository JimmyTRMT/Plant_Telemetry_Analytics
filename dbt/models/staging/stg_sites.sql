select
    site_id,
    site_name,
    country,
    timezone,
    cast(nominal_power_mw as double) as nominal_power_mw,
    cast(commissioned_year as integer) as commissioned_year
from {{ ref('sites') }}
