"""
Point d'entrée du dashboard Ontario 511.

FastAPI sert de backend (routes API possibles plus tard), Gradio est monté
dessus via mount_gradio_app pour l'interface — un seul processus, un seul
port. mount_gradio_app exige une app FastAPI (ASGI), pas Flask (WSGI),
d'où ce choix plutôt que Flask.
"""

import uvicorn
from fastapi import FastAPI
import gradio as gr

from theme import ontario511_theme, ASPHALT_900, ASPHALT_700, SIGNAL_AMBER, FROST_WHITE, CONCRETE_500
from overviewtab import build_overview_tab
from exploretab import build_explore_tab
from alertstab import build_alerts_tab
from config import settings

CUSTOM_CSS = f"""
/* Gestalt — proximité : les cartes KPI sont visuellement groupées,
   espacement serré à l'intérieur, marge nette entre le bloc et le reste. */
.kpi-row {{
    gap: 12px;
}}
.kpi-card {{
    background: {ASPHALT_700};
    border: 1px solid #2E313A;
    border-left: 3px solid {SIGNAL_AMBER};
    border-radius: 6px;
    padding: 16px 20px !important;
    text-align: left;
}}
.kpi-card h3 {{
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem;
    color: {FROST_WHITE};
    margin: 0 0 4px 0;
}}
.kpi-card strong {{
    color: {CONCRETE_500};
    font-size: 0.85rem;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
body, .gradio-container {{
    background: {ASPHALT_900} !important;
}}
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(theme=ontario511_theme, css=CUSTOM_CSS, title="Ontario 511 Dashboard") as demo:
        gr.Markdown("# Ontario 511 — Road Data Dashboard")
        with gr.Tabs():
            with gr.Tab("Overview"):
                build_overview_tab()
            with gr.Tab("Explore"):
                build_explore_tab()
            with gr.Tab("Alerts"):
                build_alerts_tab()
    return demo


fastapi_app = FastAPI()


@fastapi_app.get("/health")
def health():
    return {"status": "ok"}


gradio_app = build_app()
app = gr.mount_gradio_app(fastapi_app, gradio_app, path="/")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.dashboard_port)