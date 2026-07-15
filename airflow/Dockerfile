FROM apache/airflow:2.10.3-python3.12

USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

USER airflow

# uv nécessaire pour exécuter ingestion/ et DBT/ depuis les tâches Airflow,
# exactement comme en local — cohérence avec le reste du projet plutôt que
# de dupliquer les dépendances via pip dans l'image Airflow elle-même.
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/home/airflow/.local/bin:${PATH}"

RUN pip install --no-cache-dir psycopg2-binary