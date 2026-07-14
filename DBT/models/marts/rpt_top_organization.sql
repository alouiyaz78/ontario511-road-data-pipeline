
SELECT
    organization,
    COUNT(*) AS nb_evenements
FROM {{ ref('stg_evenements') }}
WHERE source_id IS NOT NULL
GROUP BY organization
ORDER BY nb_evenements DESC
LIMIT 1
