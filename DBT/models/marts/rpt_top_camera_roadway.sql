SELECT
    roadway_name,
    COUNT(*) AS nb_cameras
FROM {{ ref('stg_cameras') }}
GROUP BY roadway_name
ORDER BY nb_cameras DESC, roadway_name ASC
LIMIT 1
