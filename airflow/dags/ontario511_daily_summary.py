"""
DAG de résumé quotidien Ontario 511 : envoie un email une fois par jour
avec le nombre de nouvelles lignes insérées dans chaque table bronze au
cours des dernières 24h.

Fuseau horaire : Airflow utilise UTC par défaut pour tout planifier. Le
DAG est explicitement rattaché à America/Toronto (via pendulum) pour que
"8h" reste 8h heure de l'Ontario toute l'année, y compris après les
changements d'heure (EST/EDT) — sans ça, le cron UTC dériverait de 4h à
5h de décalage selon la saison.
"""

import os
from datetime import timedelta

import pendulum
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.smtp.operators.smtp import EmailOperator

ALERT_EMAIL = os.environ.get("AIRFLOW_ALERT_EMAIL")
ONTARIO_TZ = pendulum.timezone("America/Toronto")

default_args = {
    "owner": "ontario511",
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}


def _build_summary(**context) -> None:
    """Interroge bronze pour compter les insertions des dernières 24h."""
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
    description="Résumé quotidien des insertions Ontario 511, envoyé par email (8h heure Ontario)",
    schedule_interval="0 8 * * *",
    start_date=pendulum.datetime(2026, 7, 15, tz=ONTARIO_TZ),
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