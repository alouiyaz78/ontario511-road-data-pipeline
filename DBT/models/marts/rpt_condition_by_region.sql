
SELECT
    region,
    condition,
    COUNT(*) AS occurrences
FROM {{ ref('stg_roadconditions') }}
GROUP BY region, condition
ORDER BY region, occurrences DESC
