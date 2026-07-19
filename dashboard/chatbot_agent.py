

import json
import logging
import re

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

Important, roadway_name format inconsistency: this column is NOT stored
consistently across tables. For example, highway 417 appears as "HWY 417"
in stg_evenements, as "417" in stg_constructions, and as either "417" or
"HWY 417" in fct_active_alerts (which combines both sources). Never filter
on roadway_name with an exact match (=) — always use
roadway_name ILIKE '%417%' (substring match on just the number/name),
which is the only reliable way to match a roadway across all these
formats and tables.
"""

SYSTEM_PROMPT = f"""You are a helpful assistant for the Ontario 511 road data platform.

Language rule (critical, applies above all else): always reply in the
same language the user's most recent message was written in — French in,
French out; English in, English out — for the entire conversation, not
just the first message. Tool outputs (query results, error messages like
"No results found") are always in English regardless of the user's
language; this must NOT influence which language you reply in. If you
are unsure of the language, default to the language used earlier in the
conversation, not English. A "[language_instruction]" tag will accompany
each message telling you explicitly which language to reply in — always
follow it.

You answer questions about road events, constructions, cameras, and conditions
in Ontario using two tools:

- query_database: for counts, statistics, and factual lookups (SQL on silver/gold schemas)
- search_active_alerts: for finding incidents by description/topic (semantic search)

{DATABASE_SCHEMA_DESCRIPTION}

Map display rule: whenever a query_database call targets a table that has
latitude and longitude columns (fct_active_alerts, stg_evenements,
stg_constructions), always include latitude and longitude in the SELECT
list, even if the user didn't ask for coordinates explicitly. These
columns feed a map shown alongside your answer — leaving them out means
the map stays empty even when relevant incidents were found. Do not
mention coordinates in your written answer; just include them in the
query so the map can render.

Be concise and factual — cite actual numbers and roadway names from tool
results, never invent data. If a tool returns an error or no results, say
so plainly (translated into the user's language) rather than guessing.

You do not have access to a routing engine, live travel times, or a map of
alternate roads. If asked to suggest a faster route or estimate time saved
by avoiding a construction zone, say so explicitly rather than offering
generic suggestions like "consider parallel local roads" — that kind of
vague filler is not useful and should not be presented as advice. It is
fine to name the specific roadway or region affected (from tool results)
without inventing an alternative route or time estimate you cannot support.

Critical: you have no built-in knowledge of current Ontario road events,
construction, or conditions — none of that is in your training data, since
it changes constantly. Every specific claim about a roadway's current
state (closures, lane restrictions, dates, locations) MUST come from an
actual query_database or search_active_alerts call made in this turn. If a
question mentions a route, city, or trip (e.g. "Ottawa to Montreal"), you
must call a tool with relevant filters before answering — never answer
from general geographic knowledge. If neither tool returns anything
relevant to the question, say plainly that no matching data was found,
rather than filling the answer with plausible-sounding but unverified detail.
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
    normalized = sql.strip().lower()
    if not normalized.startswith("select"):
        return False
    forbidden = ("insert", "update", "delete", "drop", "alter", "truncate", "grant", "create")
    if any(re.search(rf"\b{kw}\b", normalized) for kw in forbidden):
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


_FRENCH_MARKERS = (
    " le ", " la ", " les ", " des ", " est-ce", "es ce", "qu'est", "es-tu",
    " sur ", " avec ", " pour ", " tu me", "peux-tu", " autre ", " quel ",
    " quelle ", "état", " voie", "eatat",
)


def _detect_language_instruction(text: str, history_text: str = "") -> str:
    combined = f" {text.lower()} {history_text.lower()} "
    if any(marker in combined for marker in _FRENCH_MARKERS):
        return "Reply in French. The user's message (or this conversation) is in French."
    return "Reply in English. The user's message is in English."


def extract_locations(intermediate_steps) -> list[dict]:
    locations = []

    if not intermediate_steps:
        return locations

    for step in intermediate_steps:

        if not isinstance(step, (tuple, list)):
            continue

        if len(step) != 2:
            continue

        _, tool_output = step

        if not isinstance(tool_output, str):
            continue

        if LOCATIONS_MARKER not in tool_output:
            continue

        try:
            _, json_part = tool_output.split(LOCATIONS_MARKER, 1)
            parsed = json.loads(json_part)

            if isinstance(parsed, list):
                for loc in parsed:
                    if (
                        isinstance(loc, dict)
                        and "lat" in loc
                        and "lon" in loc
                    ):
                        locations.append(loc)

        except Exception:
            logger.exception("Failed to parse locations.")

    return locations


def build_agent(provider: str, api_key: str) -> AgentExecutor:
    if not api_key or not api_key.strip():
        raise ValueError("An API key is required to use the chatbot.")

    llm = _build_llm(provider, api_key.strip())

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("placeholder", "{chat_history}"),
        ("human", "[{language_instruction}]\n\n{input}"),
        ("placeholder", "{agent_scratchpad}"),
    ])

    tools = [query_database, search_active_alerts]
    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(
        agent=agent, tools=tools, verbose=True, max_iterations=5,
        return_intermediate_steps=True,
    )
