
WITH events_by_road AS (
    SELECT roadway_name, COUNT(*) AS active_events
    FROM {{ ref('stg_evenements') }}
    WHERE is_active AND roadway_name IS NOT NULL
    GROUP BY roadway_name
),
constructions_by_road AS (
    SELECT roadway_name, COUNT(*) AS active_constructions
    FROM {{ ref('stg_constructions') }}
    WHERE is_active AND roadway_name IS NOT NULL
    GROUP BY roadway_name
),
seasonal_by_road AS (
    SELECT segment_name AS roadway_name, COUNT(*) AS active_restrictions
    FROM {{ ref('stg_seasonalloads') }}
    WHERE has_active_restriction
    GROUP BY segment_name
)

SELECT
    COALESCE(e.roadway_name, c.roadway_name, s.roadway_name) AS roadway_name,
    COALESCE(e.active_events, 0) AS active_events,
    COALESCE(c.active_constructions, 0) AS active_constructions,
    COALESCE(s.active_restrictions, 0) AS active_seasonal_restrictions,
    COALESCE(e.active_events, 0) * 2
        + COALESCE(c.active_constructions, 0) * 3
        + COALESCE(s.active_restrictions, 0) AS disruption_score
FROM events_by_road e
FULL OUTER JOIN constructions_by_road c ON e.roadway_name = c.roadway_name
FULL OUTER JOIN seasonal_by_road s ON COALESCE(e.roadway_name, c.roadway_name) = s.roadway_name
ORDER BY disruption_score DESC
