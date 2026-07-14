
SELECT
    locationdescription AS location_description,
    condition,
    visibility,
    drifting,
    region,
    roadwayname AS roadway_name,
    lastupdated AS last_updated
FROM {{ source('bronze', 'roadconditions') }}
