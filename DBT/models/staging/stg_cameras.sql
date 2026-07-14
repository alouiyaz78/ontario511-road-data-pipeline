SELECT
    baseid AS base_id,
    source,
    sourceid AS source_id,
    roadway AS roadway_name,
    direction,
    location,
    latitude,
    longitude,
    viewid AS view_id,
    url,
    status,
    description
FROM {{ source('bronze', 'cameras') }}
WHERE viewid IS NOT NULL
