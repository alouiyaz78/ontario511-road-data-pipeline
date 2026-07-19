# Ontario 511 Road Data Pipeline

An end-to-end data engineering and analytics platform built on top of Ontario's public 511 traffic API. The project ingests real-time road event, construction, camera, and condition data, transforms it through a bronze/silver/gold pipeline, orchestrates the whole cycle automatically, and exposes it through an interactive dashboard with a natural-language chatbot layer.

Built as a portfolio project to demonstrate a realistic, production-shaped data stack: ingestion, orchestration, transformation, visualization, and applied AI, all containerized and reproducible.

## Architecture overview

```
Ontario 511 API
      |
      v
  ingestion/  ---->  Postgres (bronze schema, append-only)
      |
      v
    DBT/     ---->  Postgres (silver: cleaned views, gold: marts)
      |
      v
  dashboard/  ---->  Gradio + FastAPI web app (charts, map, alerts, chatbot)

airflow/  orchestrates ingestion + DBT every 2 hours, plus a daily email summary
```

Each component runs in its own Docker container. Postgres is the single source of truth; every other service reads from or writes to it.

## Components

### Ingestion (`ingestion/`)

A Python service that polls six Ontario 511 REST endpoints (events, construction projects, cameras, road conditions, seasonal load restrictions, alerts) and writes the results into `bronze` tables.

Design choices:
- Append-only tables for time-varying sources (events, constructions, road conditions, seasonal loads), deduplicated on a natural key (typically `id` + `last_updated`) so the full history of changes is preserved natively, without a separate audit table.
- Upsert tables for "current state" sources (cameras, alerts), where historical snapshots would not be meaningful.
- All timestamps are converted from the API's Unix epoch format to `TIMESTAMPTZ` at ingestion time.

### Transformation (`DBT/`)

dbt models organized into three layers:
- **bronze** (source, not modeled): raw ingested data, as described above.
- **silver**: cleaned views per source, with derived fields such as `is_active` computed once and reused everywhere downstream.
- **gold**: analytical marts, including a time-series KPI table (incremental, one row appended per collection cycle), a per-roadway disruption index, a combined active-alerts table, and several "top N" reports.

`fct_kpi_statistics` is deliberately incremental rather than a single overwritten snapshot: preserving history is what makes trend analysis and any future ML work possible. Everything else in gold is fully rebuilt on each run, since those marts represent current state rather than a time series.

### Orchestration (`airflow/`)

Two DAGs:
- `ontario511_pipeline`: runs ingestion, then `dbt run`, then `dbt test`, every two hours. Sends an email alert on task failure.
- `ontario511_daily_summary`: once a day, emails a summary of how many new rows landed in each bronze table over the previous 24 hours.

The daily summary DAG is pinned to `America/Toronto` time explicitly (via `pendulum`), since Airflow's default scheduling timezone is UTC and a naive cron expression would drift relative to local time across DST changes.

### Dashboard (`dashboard/`)

A Gradio application mounted on FastAPI, with four tabs:
- **Overview**: current KPIs, the most disrupted roadways, and road conditions by region.
- **Explore**: an interactive map of active events and constructions, filterable by source and roadway.
- **Alerts**: a combined table of all active incidents (events, constructions, degraded road conditions), exportable to Excel.
- **Chatbot**: a natural-language assistant over the same data (see below).

The visual theme is a custom palette (asphalt, signal amber, route blue) rather than a default Gradio theme, designed around the subject matter rather than generic dashboard conventions.

### Chatbot (`dashboard/chatbot_agent.py`, `chatbottab.py`)

A LangChain tool-calling agent combining two capabilities:
- **Text-to-SQL**: the agent writes and executes read-only `SELECT` queries against the `silver`/`gold` schemas to answer factual or numeric questions. Queries are validated before execution (SELECT only, whitelisted schemas, no modification keywords).
- **RAG (semantic search)**: event and construction descriptions are embedded (via a local Ollama `nomic-embed-text` model) into a `pgvector` table, so the agent can find relevant incidents by meaning rather than exact keyword match.

The LLM itself is chosen by the user at runtime, not fixed in the code. The chat tab lets the user pick a provider (Claude, OpenAI, or Gemini) and paste their own API key. The key lives only in the browser session for that tab — it is never written to disk or logged, and is passed straight to the provider's client library on each request. Lightweight, cost-efficient models are used by default for each provider, since the task (tool selection, short SQL generation, brief summarization) does not need maximum model capability.

A small map alongside the chat displays the coordinates of any incidents the agent looked up while answering the current question. Coordinates are extracted directly from tool call results (a structured block appended to the tool's text output) rather than asked of the LLM, since asking a model to repeat numeric coordinates in natural language is unreliable.

Running the chat model locally via Ollama was evaluated first and ultimately abandoned: even a 4B-parameter model took several minutes per response under pure CPU inference on a standard development machine, and briefly exhausted WSL2's memory allocation under load. Ollama is retained solely for the embedding model, which is lightweight and does not need to be fast, since embedding generation happens once per description rather than once per chat message.

## Running the project

Requirements: Docker and Docker Compose.

1. Copy `.env.example` to `.env` (see below for required variables) and fill in the values.
2. Start the core services:
   ```
   docker compose up -d postgres
   ```
3. Run the ingestion service once to populate the database:
   ```
   docker compose run --rm ingestion
   ```
4. Build the dbt models:
   ```
   docker compose run --rm dbt uv run dbt build
   ```
5. Start Airflow (one-time initialization, then the scheduler and webserver):
   ```
   docker compose up airflow-init
   docker compose up -d airflow-webserver airflow-scheduler
   ```
6. Start Ollama and pull the embedding model:
   ```
   docker compose up -d ollama
   docker compose exec ollama ollama pull nomic-embed-text
   ```
7. Generate embeddings for the chatbot's semantic search:
   ```
   docker compose exec dashboard uv run python generate_embeddings.py
   ```
8. Start the dashboard:
   ```
   docker compose up -d dashboard
   ```

The dashboard is then available at `http://localhost:8001`, and the Airflow UI at `http://localhost:8082`.

### Required environment variables

```
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_DB=
POSTGRES_PORT=

AIRFLOW_FERNET_KEY=
AIRFLOW_SECRET_KEY=
AIRFLOW_ADMIN_USER=
AIRFLOW_ADMIN_PASSWORD=

AIRFLOW_SMTP_USER=
AIRFLOW_SMTP_PASSWORD=
AIRFLOW_ALERT_EMAIL=
```

`AIRFLOW_FERNET_KEY` and `AIRFLOW_SECRET_KEY` should be generated freshly for this project rather than reused from another one — they are used to encrypt Airflow's internal credential storage and sign webserver sessions, and should never be shared across separate deployments.

LLM provider API keys are not set as environment variables: they are entered directly in the dashboard's Chatbot tab at runtime.

## Known limitations and deliberately deferred work

- **Weather data**: evaluated (both a generic API and Environment and Climate Change Canada's official SWOB feed) but not integrated. Ontario's territory is large enough that a handful of fixed weather stations would misrepresent conditions across most of the province — a station 300+ km from an incident is not a meaningful signal. Revisiting this would require weather data anchored to specific roadway corridors or individual incident coordinates, not a fixed set of regional points.
- **Static infrastructure data** (HOT/HOV lanes, carpool lots, transit hubs, rest areas, and several other endpoints available from the Ontario 511 API): identified as available but not ingested. These are reference data rather than time-varying signals, and would need a different storage pattern (a simple reference table, not an append-only bronze table) than the rest of the pipeline.
- **File permission handling**: Airflow's containers run as a non-root user by design (a security default of the base image), which initially caused permission conflicts with Docker's anonymous volumes for `.venv` and `target` directories. This was resolved by pre-creating and chowning those directories in the Dockerfile before switching to the non-root user, so Docker respects the existing ownership when mounting over them instead of defaulting to root.
- **`roadconditions` deduplication**: this source has no natural identifier in the API, so deduplication relies on a composite key (`location_description`, `roadway_name`, `last_updated`). This is the best available approximation given the fields the API provides, but it is a documented limitation rather than an ideal design.

## Tech stack

Python, PostgreSQL with pgvector, dbt, Apache Airflow, Gradio, FastAPI, LangChain, Ollama, Docker Compose.