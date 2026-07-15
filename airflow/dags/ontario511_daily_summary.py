"""
DAG de résumé quotidien Ontario 511 : envoie un email une fois par jour
avec le nombre de nouvelles lignes insérées dans chaque table bronze au
cours des dernières 24h, plus le nombre de runs dbt réussis/échoués.

Séparé du DAG principal (ontario511_pipeline) plutôt qu'ajouté comme
tâche conditionnelle dedans : un DAG = une responsabilité, plus simple à
monitorer et à faire évoluer indépendamment (fréquence différente : 2h
pour le pipeline, 24h pour le résumé).
"""

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.smtp.operators.smtp import EmailOperator

ALERT_EMAIL = os.environ.get("AIRFLOW_ALERT_EMAIL")

default_args = {
    "owner": "ontario511",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _build_summary(**context) -> None:
    """Interroge bronze/gold pour compter les insertions des dernières 24h."""
    import psycopg2

    conn = psycopg2.connect(
        host=os.environ["POSTGRES_HOST"],
        port=os.environ["POSTGRES_PORT"],
        user=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        dbname=os.environ["POSTGRES_DB"],
    )
    tables = [
        ("evenements", "ingested_at"),
        ("constructions", "ingested_at"),
        ("cameras", "ingested_at"),
        ("roadconditions", "ingested_at"),
        ("seasonalloads", "ingested_at"),
        ("alerts", "ingested_at"),
    ]
    lines = []
    with conn.cursor() as cur:
        for table, ts_col in tables:
            cur.execute(
                f"SELECT COUNT(*) FROM bronze.{table} WHERE {ts_col} >= NOW() - INTERVAL '24 hours'"
            )
            count = cur.fetchone()[0]
            lines.append(f"  - {table}: {count} nouvelles lignes")
    conn.close()

    summary = "Résumé Ontario 511 — dernières 24h\n\n" + "\n".join(lines)
    context["ti"].xcom_push(key="summary_text", value=summary)


with DAG(
    dag_id="ontario511_daily_summary",
    default_args=default_args,
    description="Résumé quotidien des insertions Ontario 511, envoyé par email",
    schedule_interval="0 8 * * *",
    start_date=datetime(2026, 7, 15),
    catchup=False,
    tags=["ontario511", "reporting"],
) as dag:

    build_summary = PythonOperator(
        task_id="build_summary",
        python_callable=_build_summary,
    )

    send_summary_email = EmailOperator(
        task_id="send_summary_email",
        to=ALERT_EMAIL,
        subject="Ontario 511 — Résumé quotidien {{ ds }}",
        html_content="<pre>{{ ti.xcom_pull(task_ids='build_summary', key='summary_text') }}</pre>",
    )

    build_summary >> send_summary_email
