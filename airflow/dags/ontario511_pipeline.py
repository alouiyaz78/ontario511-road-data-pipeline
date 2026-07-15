"""
DAG Ontario 511 : cycle complet de collecte et transformation, toutes les
2h. Reprend le pattern déjà en place manuellement (ingestion/main.py puis
dbt run/test), automatisé ici pour que l'historique s'accumule réellement
dans le temps sans intervention manuelle.

Un seul DAG avec 3 tâches séquentielles plutôt que plusieurs DAGs chaînés :
le fetch et les transformations dbt ne font sens que l'un après l'autre
(dbt lit ce que le fetch vient d'insérer), donc les garder dans un DAG
unique avec dépendances explicites est plus simple à monitorer qu'un
déclenchement inter-DAG.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "ontario511",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="ontario511_pipeline",
    default_args=default_args,
    description="Collecte Ontario 511 + transformations dbt, toutes les 2h",
    schedule_interval=timedelta(hours=2),
    start_date=datetime(2026, 7, 15),
    catchup=False,
    tags=["ontario511"],
) as dag:

    fetch_data = BashOperator(
        task_id="fetch_ontario511_data",
        bash_command="cd /opt/airflow/ingestion && uv run python main.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/dbt_project && uv run dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/dbt_project && uv run dbt test",
    )

    fetch_data >> dbt_run >> dbt_test