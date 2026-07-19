"""
Ontario 511 chatbot agent: combines Text-to-SQL (precise figures from
gold/silver schemas) and RAG (semantic search over active event and
construction descriptions).

The chat model is provided dynamically by the user through the
interface: choice of provider (Claude / OpenAI / Gemini) plus their own
API key. The key is never persisted server-side — it is only used to
build the agent for the current request.

Embeddings (semantic search) stay on local Ollama (nomic-embed-text):
free, lightweight, and there's no need to expose this internal step to
a third-party API key since it is invisible to the user.
"""

import json
import logging

import psycopg2
import psycopg2.extras
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings

from config import settings

logger = logging.getLogger(__name__)

ALLOWED_SCHEMAS = ("silver", "gold")

PROVIDER_CHOICES = ["Claude", "OpenAI", "Gemini"]

# Marker used to embed machine-readable coordinates at the end of a tool's
# text output, without asking the LLM to handle or repeat coordinates
# itself (which would be fragile and error-prone). The chatbot tab parses
# this block out of the agent's intermediate steps to draw the mini-map,
# while the LLM only ever sees and summarizes the human-readable part.
LOCATIONS_MARKER = "\n---LOCATIONS_JSON---\n"

DATABASE_SCHEMA_DESCRIPTION = """
Available tables (schema.table):

gold.fct_kpi_statistics — time-series snapshots of global KPIs, one row per
  collection cycle (every 2h). ALWAYS use ORDER BY date_calcul DESC LIMIT 1
  to get the current/latest value — this table accumulates historical rows,
  it is not a single current snapshot.
  columns: date_calcul, nombre_evenements_actifs, nombre_moyen_evenements_par_jour,
           duree_moyenne_evenements_heures, nombre_total_cameras, nombre_moyen_constructions_par_jour

gold.fct_road_disruption_index — disruption score per roadway (current snapshot, one row per roadway)
  columns: roadway_name, active_events, active_constructions, active_seasonal_restrictions, disruption_score

gold.fct_active_alerts — all currently active incidents (events, constructions, road conditions)
  columns: alert_type, roadway_name, region, organization, category, description,
           is_full_closure, reported_since, last_updated, latitude, longitude

gold.rpt_condition_by_region — road condition counts by region
  columns: region, condition, occurrences

gold.rpt_top_organization, gold.rpt_top_camera_roadway, gold.rpt_top_construction_roadway
  — single-row "top 1" reports (already pre-aggregated, no further sorting needed)

silver.stg_evenements — cleaned active/inactive road events
  columns: event_id, organization, roadway_name, description, event_type,
           latitude, longitude, is_active, reported, last_updated, start_date, planned_end_date

silver.stg_constructions — cleaned active/inactive construction projects
  columns: construction_id, organization, roadway_name, description, event_type,
           is_full_closure, latitude, longitude, is_active, start_date, planned_end_date

silver.stg_cameras — camera views
  columns: base_id, roadway_name, direction, view_id, status

silver.stg_roadconditions — road condition observations
  columns: location_description, condition, visibility, region, roadway_name, last_updated
"""

SYSTEM_PROMPT = f"""You are a helpful assistant for the Ontario 511 road data platform.
You answer questions about road events, constructions, cameras, and conditions
in Ontario using two tools:

- query_database: for counts, statistics, and factual lookups (SQL on silver/gold schemas)
- search_active_alerts: for finding incidents by description/topic (semantic search)

{DATABASE_SCHEMA_DESCRIPTION}

Always answer in the same language as the question. Be concise and factual —
cite actual numbers and roadway names from tool results, never invent data.
If a tool returns an error or no results, say so plainly rather than guessing.
"""


def _get_connection():
    return psycopg2.connect(
        host=settings.postgres_host,
        port=settings.postgres_port,
        user=settings.postgres_user,
        password=settings.postgres_password,
        dbname=settings.postgres_db,
    )


def _is_safe_select(sql: str) -> bool:
    """
    Basic but strict validation: SELECT only, whitelisted schemas only,
    no modification keywords. This is not a full SQL parser — for a
    portfolio/local project with a reasonably trusted LLM, keyword-based
    validation is an honest and sufficient safety net.
    """
    normalized = sql.strip().lower()
    if not normalized.startswith("select"):
        return False
    forbidden = ("insert", "update", "delete", "drop", "alter", "truncate", "grant", "create")
    if any(kw in normalized for kw in forbidden):
        return False
    if not any(f"{schema}." in normalized for schema in ALLOWED_SCHEMAS):
        return False
    return True


@tool
def query_database(sql_query: str) -> str:
    """
    Execute a read-only SQL SELECT query against the Ontario 511 database
    (silver/gold schemas only) and return the results. Use this for
    questions asking for counts, statistics, specific roadway data, or
    any factual/numeric answer. The query must be valid PostgreSQL SQL,
    referencing tables with their full schema.table name (e.g.
    gold.fct_active_alerts, not just fct_active_alerts).
    """
    if not _is_safe_select(sql_query):
        return "Error: only SELECT queries on silver/gold schemas are allowed."

    try:
        conn = _get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql_query)
            rows = cur.fetchmany(50)
        conn.close()
        if not rows:
            return "No results found."

        text_result = str(rows)

        # If the query happened to select latitude/longitude, surface
        # them as a machine-readable block for the mini-map, without
        # asking the model to repeat or interpret coordinates itself.
        locations = [
            {"lat": r["latitude"], "lon": r["longitude"], "label": r.get("roadway_name") or r.get("description", "")}
            for r in rows
            if r.get("latitude") is not None and r.get("longitude") is not None
        ]
        if locations:
            text_result += LOCATIONS_MARKER + json.dumps(locations)

        return text_result
    except Exception as exc:
        logger.exception("SQL execution error")
        return f"Query error: {exc}"


@tool
def search_active_alerts(query: str) -> str:
    """
    Semantic search over active event and construction descriptions.
    Use this for questions about specific incident types, descriptions,
    or free-text content (e.g. "collision", "lane closure", "bridge
    work") rather than for counts or statistics — for those, use
    query_database instead.
    """
    try:
        embedder = OllamaEmbeddings(model=settings.ollama_embedding_model, base_url=settings.ollama_host)
        query_vector = embedder.embed_query(query)

        conn = _get_connection()
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT source_table, source_id, description,
                       1 - (embedding <=> %s::vector) AS similarity
                FROM bronze.description_embeddings
                ORDER BY embedding <=> %s::vector
                LIMIT 5
                """,
                (query_vector, query_vector),
            )
            matches = cur.fetchall()

            # Look up coordinates for each match from its source table —
            # description_embeddings only stores the text, not the
            # location, so a follow-up lookup is needed per source.
            locations = []
            for m in matches:
                if m["source_table"] == "evenements":
                    cur.execute(
                        "SELECT roadway_name, latitude, longitude FROM silver.stg_evenements WHERE event_id = %s",
                        (m["source_id"],),
                    )
                else:
                    cur.execute(
                        "SELECT roadway_name, latitude, longitude FROM silver.stg_constructions WHERE construction_id = %s",
                        (m["source_id"],),
                    )
                loc = cur.fetchone()
                if loc and loc["latitude"] is not None and loc["longitude"] is not None:
                    locations.append({
                        "lat": loc["latitude"], "lon": loc["longitude"],
                        "label": loc["roadway_name"] or m["description"][:40],
                    })
        conn.close()

        if not matches:
            return "No matching descriptions found."

        text_result = "\n".join(
            f"[{m['source_table']}#{m['source_id']}] (similarity: {m['similarity']:.2f}) {m['description']}"
            for m in matches
        )
        if locations:
            text_result += LOCATIONS_MARKER + json.dumps(locations)
        return text_result
    except Exception as exc:
        logger.exception("Semantic search error")
        return f"Search error: {exc}"


def _build_llm(provider: str, api_key: str):
    """
    Instantiate the right chat client based on the provider chosen by
    the user. The key is only used for this instantiation — never
    written to disk or logged.

    Lightweight/economical models are deliberately chosen over each
    provider's most capable option: the task at hand (picking a tool,
    generating a simple SQL query, summarizing a result) doesn't need
    maximum power, and it keeps the per-question cost low for the user
    supplying their own key.
    """
    if provider == "Claude":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(model="claude-haiku-4-5", api_key=api_key, temperature=0)
    elif provider == "OpenAI":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o-mini", api_key=api_key, temperature=0)
    elif provider == "Gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=api_key, temperature=0)
    else:
        raise ValueError(f"Unknown provider: {provider}")


def extract_locations(intermediate_steps: list) -> list[dict]:
    """
    Pulls out the LOCATIONS_JSON block appended by query_database/
    search_active_alerts to any tool output in this run, for the mini-map.
    Returns an empty list if no tool call in this turn produced coordinates.
    """
    locations = []
    for _, tool_output in intermediate_steps:
        if isinstance(tool_output, str) and LOCATIONS_MARKER in tool_output:
            _, _, json_part = tool_output.partition(LOCATIONS_MARKER)
            try:
                locations.extend(json.loads(json_part))
            except (json.JSONDecodeError, ValueError):
                logger.warning("Failed to parse locations block from tool output")
    return locations


def build_agent(provider: str, api_key: str) -> AgentExecutor:
    if not api_key or not api_key.strip():
        raise ValueError("An API key is required to use the chatbot.")

    llm = _build_llm(provider, api_key.strip())

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    tools = [query_database, search_active_alerts]
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent, tools=tools, verbose=True, max_iterations=5,
        return_intermediate_steps=True,
    )