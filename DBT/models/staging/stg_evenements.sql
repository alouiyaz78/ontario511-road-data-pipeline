
SELECT
    id AS event_id,
    sourceid AS source_id,
    organization,
    roadwayname AS roadway_name,
    direction,
    description,
    reported,
    lastupdated AS last_updated,
    startdate AS start_date,
    plannedenddate AS planned_end_date,
    eventtype AS event_type,
    latitude,
    longitude,
    (plannedenddate IS NULL OR plannedenddate >= NOW()) AS is_active
FROM {{ source('bronze', 'evenements') }}
