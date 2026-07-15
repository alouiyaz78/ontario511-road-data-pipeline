"""
Onglet Vue d'ensemble : lecture directe des marts gold, aucune logique
métier recalculée ici (is_active, disruption_score, etc. viennent de dbt).

Note : le graphique "KPI trend over time" a été retiré — avec seulement
quelques points accumulés manuellement (pas encore d'Airflow tournant en
continu), il montrait des micro-variations trompeuses plutôt qu'une vraie
tendance. À réintroduire une fois qu'Airflow aura accumulé plusieurs jours
de snapshots réels via fct_kpi_statistics (toujours incrémental, toujours
alimenté en arrière-plan).

Gestalt appliqué :
- Proximité : les 4 KPI de tête sont groupés dans une seule Row, avec un
  espacement serré entre eux et plus large avant/après le bloc.
- Similarité : tout ce qui représente une "perturbation active" (barres du
  disruption index) utilise systématiquement SIGNAL_AMBER.
- Figure/fond : la route la plus perturbée se détache en couleur pleine,
  les suivantes en couleur atténuée, plutôt qu'un dégradé continu.
"""

import gradio as gr
import plotly.graph_objects as go

from db import (
    get_latest_kpi,
    get_disruption_index,
    get_top_summary,
    get_condition_by_region,
)
from theme import PLOTLY_COLORS


def _base_layout(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        title=title,
        paper_bgcolor=PLOTLY_COLORS["paper"],
        plot_bgcolor=PLOTLY_COLORS["background"],
        font=dict(color=PLOTLY_COLORS["text"], family="Inter"),
        xaxis=dict(gridcolor=PLOTLY_COLORS["grid"]),
        yaxis=dict(gridcolor=PLOTLY_COLORS["grid"]),
        margin=dict(l=40, r=20, t=50, b=40),
    )
    return fig


def _disruption_figure() -> go.Figure:
    df = get_disruption_index(limit=15)
    fig = go.Figure()
    if not df.empty:
        max_score = df["disruption_score"].max()
        colors = [
            PLOTLY_COLORS["active"] if s == max_score else PLOTLY_COLORS["neutral"]
            for s in df["disruption_score"]
        ]
        fig.add_trace(go.Bar(
            x=df["disruption_score"], y=df["roadway_name"],
            orientation="h", marker_color=colors,
        ))
        fig.update_yaxes(autorange="reversed")
    return _base_layout(fig, "Most disrupted roadways")


def _condition_figure() -> go.Figure:
    """
    Une seule barre par région : total d'observations de conditions
    problématiques (tout sauf "No Report"), triée décroissante.
    """
    df = get_condition_by_region()
    fig = go.Figure()
    if df.empty:
        return _base_layout(fig, "Road conditions by region")

    reported = df[df["condition"].str.strip().str.lower() != "no report"]
    region_totals = (
        reported.groupby("region")["occurrences"].sum()
        .sort_values(ascending=False).head(15)
    )

    if region_totals.empty:
        total_obs = df["occurrences"].sum()
        fig.add_annotation(
            text=f"No adverse road conditions reported<br>"
                 f"({total_obs} observations across {df['region'].nunique()} regions, all clear)",
            showarrow=False, font=dict(color=PLOTLY_COLORS["muted"], size=14),
        )
        return _base_layout(fig, "Road conditions by region")

    max_val = region_totals.max()
    colors = [
        PLOTLY_COLORS["active"] if v == max_val else PLOTLY_COLORS["neutral"]
        for v in region_totals.values
    ]
    fig.add_trace(go.Bar(
        x=region_totals.values, y=region_totals.index,
        orientation="h", marker_color=colors,
    ))
    fig.update_yaxes(autorange="reversed")
    return _base_layout(fig, "Reported road conditions by region (excl. 'No Report')")


def _kpi_card_value(kpi: dict, key: str, fmt: str = "{}") -> str:
    val = kpi.get(key)
    if val is None:
        return "—"
    return fmt.format(val)


def build_overview_tab() -> None:
    kpi = get_latest_kpi()
    tops = get_top_summary()

    with gr.Row(elem_classes=["kpi-row"]):
        gr.Markdown(
            f"### {_kpi_card_value(kpi, 'nombre_evenements_actifs')}\n**Active events**",
            elem_classes=["kpi-card"],
        )
        gr.Markdown(
            f"### {_kpi_card_value(kpi, 'nombre_total_cameras')}\n**Cameras tracked**",
            elem_classes=["kpi-card"],
        )
        gr.Markdown(
            f"### {_kpi_card_value(kpi, 'duree_moyenne_evenements_heures', '{:.1f}h')}\n"
            f"**Avg. event duration**",
            elem_classes=["kpi-card"],
        )
        gr.Markdown(
            f"### {_kpi_card_value(kpi, 'nombre_moyen_constructions_par_jour', '{:.1f}')}\n"
            f"**Avg. constructions/day**",
            elem_classes=["kpi-card"],
        )

    gr.Plot(value=_disruption_figure(), label="Disruption")
    gr.Plot(value=_condition_figure(), label="Conditions")

    with gr.Row():
        org = tops.get("organization") or {}
        cam = tops.get("camera_roadway") or {}
        con = tops.get("construction_roadway") or {}
        gr.Markdown(
            f"**Top reporting org**\n\n{org.get('organization', '—')} "
            f"({org.get('nb_evenements', 0)} events)"
        )
        gr.Markdown(
            f"**Most camera-covered roadway**\n\n{cam.get('roadway_name', '—')} "
            f"({cam.get('nb_cameras', 0)} views)"
        )
        gr.Markdown(
            f"**Most active construction roadway**\n\n{con.get('roadway_name', '—')} "
            f"({con.get('nb_constructions_actives', 0)} active)"
        )