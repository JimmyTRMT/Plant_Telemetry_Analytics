select
    site_id,
    site_name,
    country,
    timezone,
    nominal_power_mw,
    commissioned_year
from {{ ref('stg_sites') }}
