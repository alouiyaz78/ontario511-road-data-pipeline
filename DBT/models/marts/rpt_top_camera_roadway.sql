
SELECT
    roadway,
    COUNT(*) AS nb_cameras
FROM {{ ref('stg_cameras') }}
GROUP BY roadway
ORDER BY nb_cameras DESC
LIMIT 1
