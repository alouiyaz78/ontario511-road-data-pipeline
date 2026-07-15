"""
Onglet Exploration : filtres interactifs + carte + tableau détaillé.

Gestalt appliqué :
- Continuité : la carte et le tableau partagent la même source filtrée —
  sélectionner une source/un statut/une route met à jour les deux en même
  temps, pas des composants indépendants qui se désynchronisent.
- Similarité : couleur d'intensité sur la carte (ambre = actif, bleu =
  inactif) reprend le même code couleur que l'onglet Vue d'ensemble.

Carte en style clair (carto-positron) : les marqueurs se distinguent mieux
sur fond clair que sur fond noir. Le tooltip est explicitement forcé en
fond blanc/texte sombre (le défaut Plotly est un jaune peu lisible avec
du texte noir dessus).
"""

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

from db import get_events_geo, get_constructions_geo

SOURCE_CHOICES = ["Events", "Constructions"]
ALL_ROADWAYS = "All roadways"

MAP_ACTIVE_COLOR = "#D4901F"
MAP_INACTIVE_COLOR = "#2E5EAA"


def _fetch(source: str, active_only: bool) -> pd.DataFrame:
    if source == "Events":
        df = get_events_geo(active_only=active_only)
        df = df.rename(columns={"event_id": "id"})
    else:
        df = get_constructions_geo(active_only=active_only)
        df = df.rename(columns={"construction_id": "id"})
    return df


def _roadway_choices(df: pd.DataFrame) -> list[str]:
    if df.empty or "roadway_name" not in df.columns:
        return [ALL_ROADWAYS]
    counts = df["roadway_name"].value_counts()
    return [ALL_ROADWAYS] + counts.index.tolist()


def _map_figure(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if df.empty:
        fig.add_annotation(
            text="No results for this filter",
            showarrow=False, font=dict(color="#6B6E76", size=14),
        )
        fig.update_layout(
            mapbox=dict(style="carto-positron", center=dict(lat=45, lon=-84), zoom=4),
        )
    else:
        colors = [
            MAP_ACTIVE_COLOR if a else MAP_INACTIVE_COLOR
            for a in df["is_active"]
        ]
        fig.add_trace(go.Scattermapbox(
            lat=df["latitude"], lon=df["longitude"],
            mode="markers",
            marker=dict(size=11, color=colors),
            text=df["roadway_name"].fillna("") + " — " + df["description"].fillna("").str.slice(0, 80),
            hoverinfo="text",
        ))

        lat_range = df["latitude"].max() - df["latitude"].min()
        lon_range = df["longitude"].max() - df["longitude"].min()
        span = max(lat_range, lon_range, 0.05)
        zoom = max(3.5, min(13, 8.3 - (span ** 0.45)))

        fig.update_layout(
            mapbox=dict(
                style="carto-positron",
                center=dict(lat=df["latitude"].mean(), lon=df["longitude"].mean()),
                zoom=zoom,
            ),
        )
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        height=480,
        hoverlabel=dict(
            bgcolor="white",
            font_size=13,
            font_color="#1C1E24",
            bordercolor="#2E5EAA",
        ),
    )
    return fig


def _table_columns(source: str) -> list[str]:
    if source == "Events":
        return ["id", "organization", "roadway_name", "event_type",
                "is_active", "last_updated", "description"]
    return ["id", "organization", "roadway_name", "event_type",
            "is_full_closure", "is_active", "last_updated", "description"]


def _apply_roadway_filter(df: pd.DataFrame, roadway: str) -> pd.DataFrame:
    if roadway == ALL_ROADWAYS or not roadway or df.empty:
        return df
    return df[df["roadway_name"] == roadway]


def _update(source: str, active_only: bool, roadway: str):
    df = _fetch(source, active_only)
    df = _apply_roadway_filter(df, roadway)
    cols = [c for c in _table_columns(source) if c in df.columns]
    table_df = df[cols] if not df.empty else pd.DataFrame(columns=cols)
    return _map_figure(df), table_df


def _update_source(source: str, active_only: bool):
    """Source ou 'actif seulement' change : repeuple aussi les routes disponibles."""
    df = _fetch(source, active_only)
    choices = _roadway_choices(df)
    cols = [c for c in _table_columns(source) if c in df.columns]
    table_df = df[cols] if not df.empty else pd.DataFrame(columns=cols)
    return gr.update(choices=choices, value=ALL_ROADWAYS), _map_figure(df), table_df


def build_explore_tab() -> None:
    initial_df = _fetch("Events", True)

    with gr.Row():
        source = gr.Radio(
            choices=SOURCE_CHOICES, value="Events", label="Data source",
        )
        active_only = gr.Checkbox(value=True, label="Active only")
        roadway = gr.Dropdown(
            choices=_roadway_choices(initial_df), value=ALL_ROADWAYS,
            label="Roadway", filterable=True,
        )

    map_plot = gr.Plot(label="Map")
    result_table = gr.Dataframe(label="Details", wrap=True)

    map_plot.value = _map_figure(initial_df)
    cols = [c for c in _table_columns("Events") if c in initial_df.columns]
    result_table.value = initial_df[cols] if not initial_df.empty else pd.DataFrame(columns=cols)

    source.change(
        fn=_update_source, inputs=[source, active_only],
        outputs=[roadway, map_plot, result_table],
    )
    active_only.change(
        fn=_update_source, inputs=[source, active_only],
        outputs=[roadway, map_plot, result_table],
    )
    roadway.change(
        fn=_update, inputs=[source, active_only, roadway],
        outputs=[map_plot, result_table],
    )