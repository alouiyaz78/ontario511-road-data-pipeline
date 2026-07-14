
SELECT
    segmentname AS segment_name,
    routedescription AS route_description,
    status,
    restriction_date,
    latitude,
    longitude,
    (status ILIKE '%restriction%') AS has_active_restriction
FROM {{ source('bronze', 'seasonalloads') }}
