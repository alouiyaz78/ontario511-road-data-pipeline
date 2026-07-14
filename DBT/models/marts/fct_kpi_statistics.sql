{{ config(
    materialized='incremental',
    unique_key='date_calcul'
) }}

-- Snapshot horodaté des KPI globaux Ontario 511.
-- Matérialisé en incremental : chaque run insère une nouvelle ligne
-- plutôt que d'écraser la précédente, pour conserver un historique
-- exploitable (dashboard de tendance, ou base pour du ML plus tard).
--
-- date_calcul est arrondi à la minute pour rester lisible et facilement
-- agrégeable (par heure / par jour) sans perdre la granularité utile
-- vu que ce modèle tourne toutes les 2h via Airflow.

SELECT
    date_trunc('minute', NOW()) AS date_calcul,

    (SELECT COUNT(*)
     FROM {{ ref('stg_evenements') }}
     WHERE is_active) AS nombre_evenements_actifs,

    (SELECT ROUND(
         COUNT(*)::numeric / NULLIF(COUNT(DISTINCT start_date::date), 0), 2
     )
     FROM {{ ref('stg_evenements') }}
     WHERE start_date IS NOT NULL) AS nombre_moyen_evenements_par_jour,

    (SELECT ROUND(
         AVG(EXTRACT(EPOCH FROM (planned_end_date - start_date)) / 3600)::numeric, 2
     )
     FROM {{ ref('stg_evenements') }}
     WHERE start_date IS NOT NULL
       AND planned_end_date IS NOT NULL) AS duree_moyenne_evenements_heures,

    (SELECT COUNT(*)
     FROM {{ ref('stg_cameras') }}) AS nombre_total_cameras,

    (SELECT ROUND(
         COUNT(*)::numeric / NULLIF(COUNT(DISTINCT start_date::date), 0), 2
     )
     FROM {{ ref('stg_constructions') }}
     WHERE start_date IS NOT NULL) AS nombre_moyen_constructions_par_jour

{% if is_incremental() %}
-- En mode incrémental, dbt ne recalcule que si on insère une ligne
-- vraiment nouvelle (par minute). Cette clause évite les inserts
-- redondants si le modèle est relancé plusieurs fois dans la même minute.
WHERE date_trunc('minute', NOW()) NOT IN (SELECT date_calcul FROM {{ this }})
{% endif %}