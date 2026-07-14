
SELECT
    NOW() AS date_calcul,
    (SELECT COUNT(*) FROM {{ ref('stg_evenements') }} WHERE is_active) AS nombre_evenements_actifs,
    (SELECT ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT start_date::date), 0), 2)
     FROM {{ ref('stg_evenements') }} WHERE start_date IS NOT NULL) AS nombre_moyen_evenements_par_jour,
    (SELECT ROUND(AVG(EXTRACT(EPOCH FROM (planned_end_date - start_date)) / 3600)::numeric, 2)
     FROM {{ ref('stg_evenements') }}
     WHERE start_date IS NOT NULL AND planned_end_date IS NOT NULL) AS duree_moyenne_evenements_heures,
    (SELECT COUNT(*) FROM {{ ref('stg_cameras') }}) AS nombre_total_cameras,
    (SELECT ROUND(COUNT(*)::numeric / NULLIF(COUNT(DISTINCT start_date::date), 0), 2)
     FROM {{ ref('stg_constructions') }} WHERE start_date IS NOT NULL) AS nombre_moyen_constructions_par_jour
