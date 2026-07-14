SELECT
    id AS construction_id,
    sourceid AS source_id,
    organization,
    roadwayname AS roadway_name,
    directionoftravel AS direction_of_travel,
    description,
    reported,
    lastupdated AS last_updated,
    startdate AS start_date,
    plannedenddate AS planned_end_date,
    lanesaffected AS lanes_affected,
    latitude,
    longitude,
    eventtype AS event_type,
    isfullclosure AS is_full_closure,
    comment,
    (startdate IS NULL OR startdate <= NOW())
        AND (plannedenddate IS NULL OR plannedenddate >= NOW()) AS is_active
FROM {{ source('bronze', 'constructions') }}