"""
Onglet Alerts : table combinée de toutes les alertes actives (events,
constructions, road conditions dégradées), avec export Excel — destiné
à un usage direct par des usagers de la route ou des sociétés de
transport souhaitant vérifier l'état d'un trajet avant de partir.
"""

import tempfile
from pathlib import Path

import gradio as gr
import pandas as pd

from db import get_active_alerts

ALERT_TYPE_CHOICES = ["All", "Event", "Construction", "Road Condition"]


def _filtered(alert_type: str, roadway_search: str) -> pd.DataFrame:
    df = get_active_alerts()
    if df.empty:
        return df
    if alert_type != "All":
        df = df[df["alert_type"] == alert_type]
    if roadway_search:
        df = df[df["roadway_name"].fillna("").str.contains(roadway_search, case=False, na=False)]
    return df


def _export_excel(alert_type: str, roadway_search: str) -> str:
    """
    Génère un fichier Excel à la demande à partir des alertes filtrées.
    Export de données brutes (pas de formules) : pandas.to_excel suffit,
    pas besoin de recalcul openpyxl puisqu'il n'y a rien à recalculer.
    """
    df = _filtered(alert_type, roadway_search)
    tmp_dir = Path(tempfile.gettempdir())
    out_path = tmp_dir / "ontario511_active_alerts.xlsx"
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Active Alerts", index=False)
        worksheet = writer.sheets["Active Alerts"]
        for i, col in enumerate(df.columns, start=1):
            max_len = max(df[col].astype(str).map(len).max() if not df.empty else 0, len(col))
            worksheet.column_dimensions[worksheet.cell(row=1, column=i).column_letter].width = min(max_len + 2, 50)
    return str(out_path)


def _update_table(alert_type: str, roadway_search: str) -> pd.DataFrame:
    return _filtered(alert_type, roadway_search)


def build_alerts_tab() -> None:
    gr.Markdown(
        "Combined view of currently active road events, construction "
        "projects, and degraded road conditions. Filter and export to "
        "check your route before heading out."
    )

    with gr.Row():
        alert_type = gr.Radio(
            choices=ALERT_TYPE_CHOICES, value="All", label="Alert type",
        )
        roadway_search = gr.Textbox(
            label="Search roadway", placeholder="e.g. 401, QEW, HWY 11",
        )

    initial_df = _filtered("All", "")
    alerts_table = gr.Dataframe(value=initial_df, label="Active alerts", wrap=True)

    export_button = gr.DownloadButton(label="Download as Excel")

    alert_type.change(fn=_update_table, inputs=[alert_type, roadway_search], outputs=alerts_table)
    roadway_search.change(fn=_update_table, inputs=[alert_type, roadway_search], outputs=alerts_table)
    export_button.click(fn=_export_excel, inputs=[alert_type, roadway_search], outputs=export_button)