{{ config(materialized='table') }}

-- Table d'alertes actives, tous types confondus, une ligne par incident.
-- Destinée à un usage direct (export Excel) par des usagers de la route
-- ou des sociétés de transport planifiant un trajet : chaque ligne reste
-- actionnable (route, description, localisation), contrairement à un
-- score agrégé par route qui perdrait le détail nécessaire à la décision.
--
-- region n'existe que pour road conditions dans les données sources ;
-- laissée vide pour events/constructions plutôt que d'inventer un mapping
-- approximatif entre coordonnées et région administrative.

WITH active_events AS (
    SELECT
        'Event' AS alert_type,
        event_id::text AS source_record_id,
        organization,
        roadway_name,
        NULL::text AS region,
        description,
        event_type AS category,
        NULL::boolean AS is_full_closure,
        reported AS reported_since,
        last_updated,
        latitude,
        longitude
    FROM {{ ref('stg_evenements') }}
    WHERE is_active
),

active_constructions AS (
    SELECT
        'Construction' AS alert_type,
        construction_id::text AS source_record_id,
        organization,
        roadway_name,
        NULL::text AS region,
        description,
        event_type AS category,
        is_full_closure,
        reported AS reported_since,
        last_updated,
        latitude,
        longitude
    FROM {{ ref('stg_constructions') }}
    WHERE is_active
),

active_conditions AS (
    SELECT
        'Road Condition' AS alert_type,
        NULL AS source_record_id,
        NULL::text AS organization,
        roadway_name,
        region,
        location_description AS description,
        condition AS category,
        NULL::boolean AS is_full_closure,
        NULL::timestamptz AS reported_since,
        last_updated,
        NULL::double precision AS latitude,
        NULL::double precision AS longitude
    FROM {{ ref('stg_roadconditions') }}
    WHERE condition != 'No Report'
)

SELECT * FROM active_events
UNION ALL
SELECT * FROM active_constructions
UNION ALL
SELECT * FROM active_conditions
ORDER BY roadway_name, alert_type
