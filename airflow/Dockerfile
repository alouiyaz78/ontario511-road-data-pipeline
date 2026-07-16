FROM apache/airflow:2.10.3-python3.12

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Pré-créer les dossiers qui recevront des volumes anonymes, avec les
# bonnes permissions, AVANT le montage — sinon Docker crée ces points de
# montage en root par défaut au moment du "docker compose up", peu
# importe l'utilisateur défini plus bas avec USER.
RUN mkdir -p /opt/airflow/ingestion/.venv /opt/airflow/dbt_project/.venv /opt/airflow/dbt_project/target && \
    chown -R airflow:root /opt/airflow/ingestion/.venv /opt/airflow/dbt_project/.venv /opt/airflow/dbt_project/target

USER airflow

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/airflow/.local/bin:${PATH}"

RUN pip install --no-cache-dir psycopg2-binary