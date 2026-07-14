
SELECT
    organization,
    COUNT(*) AS nb_evenements
FROM {{ ref('stg_evenements') }}
WHERE organization IS NOT NULL
GROUP BY organization
ORDER BY nb_evenements DESC, organization ASC
LIMIT 1
