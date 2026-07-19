"""
Ontario 511 dashboard entry point.

FastAPI serves as the backend (room for future API routes), with Gradio
mounted on top via mount_gradio_app for the interface — a single
process, a single port. mount_gradio_app requires a FastAPI app (ASGI),
not Flask (WSGI), hence this choice over Flask.
"""

import uvicorn
from fastapi import FastAPI
import gradio as gr

from theme import ontario511_theme, ASPHALT_900, ASPHALT_700, SIGNAL_AMBER, FROST_WHITE, CONCRETE_500
from overviewtab import build_overview_tab
from exploretab import build_explore_tab
from alertstab import build_alerts_tab
from chatbottab import build_chatbot_tab
from config import settings

CUSTOM_CSS = f"""
/* Gestalt — proximity: the KPI cards are visually grouped, with tight
   spacing between them and a clear gap before/after the block. */
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
.header-row {{
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
}}
.header-logo {{
    flex-grow: 0 !important;
    min-width: 48px !important;
}}
.chatbot-frame {{
    border: 1px solid #2E313A !important;
    border-radius: 8px !important;
    background: {ASPHALT_700} !important;
}}
"""


def build_app() -> gr.Blocks:
    with gr.Blocks(theme=ontario511_theme, css=CUSTOM_CSS, title="Ontario 511 Dashboard") as demo:
        with gr.Row(elem_classes=["header-row"]):
            gr.Image(
                "logo.png", show_label=False, container=False,
                height=48, width=48, elem_classes=["header-logo"],
            )
            gr.Markdown("# Ontario 511 — Road Data Dashboard")
        with gr.Tabs():
            with gr.Tab("Overview"):
                build_overview_tab()
            with gr.Tab("Explore"):
                build_explore_tab()
            with gr.Tab("Alerts"):
                build_alerts_tab()
            with gr.Tab("Chatbot"):
                build_chatbot_tab()
    return demo


fastapi_app = FastAPI()


@fastapi_app.get("/health")
def health():
    return {"status": "ok"}


gradio_app = build_app()
app = gr.mount_gradio_app(fastapi_app, gradio_app, path="/")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.dashboard_port)