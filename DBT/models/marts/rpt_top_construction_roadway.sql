SELECT
    roadway_name,
    COUNT(*) AS nb_constructions_actives
FROM {{ ref('stg_constructions') }}
WHERE is_active
GROUP BY roadway_name
ORDER BY nb_constructions_actives DESC, roadway_name ASC
LIMIT 1