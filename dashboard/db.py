"""
Couche d'accès aux données pour le dashboard Ontario 511.

Lecture seule : ce module n'exécute jamais d'INSERT/UPDATE/DELETE.
Toutes les requêtes ciblent les schémas silver (staging) et gold (marts)
déjà construits et testés par dbt — le dashboard ne réimplémente aucune
logique métier (is_active, disruption_score, etc.), il consomme des
résultats déjà calculés en amont.
"""

import psycopg2
import psycopg2.extras
import pandas as pd

from config import settings

# Toutes les colonnes datetime sont stockées en UTC (TIMESTAMPTZ) — c'est
# la bonne pratique de stockage, qui évite les ambiguïtés lors des
# changements d'heure (EST/EDT). La conversion en heure Ontario se fait
# uniquement à l'affichage, ici au niveau SQL plutôt qu'en post-traitement
# pandas : Postgres gère nativement les règles DST, pas besoin de les
# réimplémenter en Python.
ONTARIO_TZ = "America/Toronto"


def _to_ontario_time(column: str, alias: str | None = None) -> str:
    """Génère le fragment SQL convertissant une colonne UTC en heure Ontario."""
    alias = alias or column
    return f"{column} AT TIME ZONE 'UTC' AT TIME ZONE '{ONTARIO_TZ}' AS {alias}"


def _get_connection():
    return psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )


def _query_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Exécute une requête et retourne un DataFrame pandas."""
    with _get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
    return pd.DataFrame(rows)


# ─── Vue d'ensemble ─────────────────────────────────────────────────────────

def get_latest_kpi() -> dict:
    """Dernier snapshot de KPI globaux (gold.fct_kpi_statistics)."""
    df = _query_df(f"""
        SELECT {_to_ontario_time('date_calcul')}, nombre_evenements_actifs,
               nombre_moyen_evenements_par_jour, duree_moyenne_evenements_heures,
               nombre_total_cameras, nombre_moyen_constructions_par_jour
        FROM gold.fct_kpi_statistics
        ORDER BY date_calcul DESC
        LIMIT 1
    """)
    return df.iloc[0].to_dict() if not df.empty else {}


def get_kpi_history() -> pd.DataFrame:
    """Historique complet des KPI, pour le graphique de tendance."""
    return _query_df(f"""
        SELECT {_to_ontario_time('date_calcul')}, nombre_evenements_actifs, nombre_total_cameras,
               nombre_moyen_evenements_par_jour, nombre_moyen_constructions_par_jour
        FROM gold.fct_kpi_statistics
        ORDER BY date_calcul ASC
    """)


def get_disruption_index(limit: int = 15) -> pd.DataFrame:
    """Top N des routes les plus perturbées (gold.fct_road_disruption_index)."""
    return _query_df("""
        SELECT roadway_name, active_events, active_constructions,
               active_seasonal_restrictions, disruption_score
        FROM gold.fct_road_disruption_index
        ORDER BY disruption_score DESC
        LIMIT %s
    """, (limit,))


def get_top_summary() -> dict:
    """Les 3 rapports 'top 1' combinés en un seul dict pour affichage rapide."""
    org = _query_df("SELECT * FROM gold.rpt_top_organization")
    cam = _query_df("SELECT * FROM gold.rpt_top_camera_roadway")
    con = _query_df("SELECT * FROM gold.rpt_top_construction_roadway")
    return {
        "organization": org.iloc[0].to_dict() if not org.empty else None,
        "camera_roadway": cam.iloc[0].to_dict() if not cam.empty else None,
        "construction_roadway": con.iloc[0].to_dict() if not con.empty else None,
    }


def get_condition_by_region() -> pd.DataFrame:
    """Répartition des conditions routières par région (gold.rpt_condition_by_region)."""
    return _query_df("""
        SELECT region, condition, occurrences
        FROM gold.rpt_condition_by_region
        ORDER BY region, occurrences DESC
    """)


def get_active_alerts() -> pd.DataFrame:
    """
    Table combinée de toutes les alertes actives (events, constructions,
    road conditions dégradées) — gold.fct_active_alerts. Destinée à un
    export direct pour usagers de la route / sociétés de transport.
    """
    return _query_df(f"""
        SELECT alert_type, roadway_name, region, organization, category,
               description, is_full_closure,
               {_to_ontario_time('reported_since')}, {_to_ontario_time('last_updated')},
               latitude, longitude
        FROM gold.fct_active_alerts
        ORDER BY roadway_name, alert_type
    """)


# ─── Exploration ────────────────────────────────────────────────────────────

def get_events_geo(active_only: bool = True) -> pd.DataFrame:
    """
    Événements géolocalisés (silver.stg_evenements), pour la carte.
    Pas de filtre par région : cette source n'a pas de colonne region
    (contrairement à stg_roadconditions) — seulement latitude/longitude.
    """
    sql = f"""
        SELECT event_id, organization, roadway_name, description,
               event_type, latitude, longitude, is_active,
               {_to_ontario_time('last_updated')}
        FROM silver.stg_evenements
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    if active_only:
        sql += " AND is_active"
    return _query_df(sql)


def get_constructions_geo(active_only: bool = True) -> pd.DataFrame:
    """Constructions géolocalisées (silver.stg_constructions), pour la carte."""
    sql = f"""
        SELECT construction_id, organization, roadway_name, description,
               event_type, is_full_closure, latitude, longitude, is_active,
               {_to_ontario_time('last_updated')}
        FROM silver.stg_constructions
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
    """
    if active_only:
        sql += " AND is_active"
    return _query_df(sql)


def get_regions() -> list[str]:
    """Liste des régions distinctes, pour peupler le filtre."""
    df = _query_df("""
        SELECT DISTINCT region
        FROM silver.stg_roadconditions
        WHERE region IS NOT NULL
        ORDER BY region
    """)
    return df["region"].tolist() if not df.empty else []


def get_organizations() -> list[str]:
    """Liste des organisations distinctes, pour peupler le filtre."""
    df = _query_df("""
        SELECT DISTINCT organization
        FROM silver.stg_evenements
        WHERE organization IS NOT NULL
        ORDER BY organization
    """)
    return df["organization"].tolist() if not df.empty else []