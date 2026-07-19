"""
Génère les embeddings vectoriels des descriptions d'événements et
constructions actifs, pour la recherche sémantique du chatbot RAG.

Ne traite que les lignes actives et pas déjà encodées (ou dont la
description a changé depuis le dernier passage) — pas besoin de
régénérer l'embedding d'une description qui n'a pas bougé, ce qui
économise des appels au modèle à chaque cycle.
"""

import logging

import psycopg2
import psycopg2.extras
from langchain_ollama import OllamaEmbeddings

from config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "nomic-embed-text"


def _get_connection():
    return psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )


def _fetch_pending_descriptions(conn) -> list[dict]:
    """
    Récupère les descriptions d'événements/constructions actifs qui n'ont
    pas encore d'embedding, ou dont la description en base a changé
    depuis le dernier embedding généré (comparaison directe du texte,
    plus simple qu'un hash pour ce volume de données).
    """
    query = """
        WITH active_descriptions AS (
            SELECT 'evenements' AS source_table, event_id AS source_id, description
            FROM silver.stg_evenements
            WHERE is_active AND description IS NOT NULL AND description != ''
            UNION ALL
            SELECT 'constructions' AS source_table, construction_id AS source_id, description
            FROM silver.stg_constructions
            WHERE is_active AND description IS NOT NULL AND description != ''
        )
        SELECT ad.source_table, ad.source_id, ad.description
        FROM active_descriptions ad
        LEFT JOIN bronze.description_embeddings de
            ON de.source_table = ad.source_table AND de.source_id = ad.source_id
        WHERE de.row_id IS NULL OR de.description != ad.description
    """
    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(query)
        return cur.fetchall()


def _upsert_embedding(conn, source_table: str, source_id: int, description: str, embedding: list[float]) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO bronze.description_embeddings (source_table, source_id, description, embedding, generated_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT ON CONSTRAINT uq_description_embeddings_source
            DO UPDATE SET description = EXCLUDED.description,
                          embedding = EXCLUDED.embedding,
                          generated_at = NOW()
            """,
            (source_table, source_id, description, embedding),
        )
    conn.commit()


def run() -> None:
    logger.info("Démarrage de la génération d'embeddings…")
    embedder = OllamaEmbeddings(model=EMBEDDING_MODEL, base_url=settings.ollama_host)

    conn = _get_connection()
    try:
        pending = _fetch_pending_descriptions(conn)
        logger.info("%d descriptions à encoder", len(pending))

        for row in pending:
            try:
                vector = embedder.embed_query(row["description"])
                _upsert_embedding(conn, row["source_table"], row["source_id"], row["description"], vector)
            except Exception:
                logger.exception(
                    "Échec de l'embedding pour %s/%s", row["source_table"], row["source_id"]
                )

        logger.info("✓ Génération d'embeddings terminée")
    finally:
        conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run()