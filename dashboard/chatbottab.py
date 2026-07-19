"""
Chatbot tab: lets the user pick an LLM provider (Claude / OpenAI / Gemini),
enter their own API key, and chat with the Ontario 511 assistant.

The API key lives only in browser session memory for the duration of the
tab session — never written to disk, never sent anywhere except directly
to the chosen provider's API.

A small map below the chat shows the locations of any incidents the
agent looked up while answering the latest question (extracted from the
tool call results, not asked of the model directly).
"""

import gradio as gr
import plotly.graph_objects as go
import traceback

from chatbot_agent import build_agent, extract_locations, PROVIDER_CHOICES, _detect_language_instruction

DISCLAIMER = (
    "Choose a provider and enter your own API key to start chatting. "
    "Your key is kept in this browser session only (never written to "
    "disk) and is used solely to call your provider's API directly. "
    "Each message may incur costs on your account."
)


def _empty_map() -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text="No locations to show yet — ask about a specific incident or roadway.",
        showarrow=False, font=dict(color="#6B6E76", size=13),
    )
    fig.update_layout(
        mapbox=dict(style="carto-positron", center=dict(lat=45, lon=-84), zoom=4),
        paper_bgcolor="#FFFFFF", margin=dict(l=0, r=0, t=0, b=0), showlegend=False, height=280,
    )
    return fig


def _locations_map(locations: list[dict]) -> go.Figure:
    fig = go.Figure()
    if not locations:
        return _empty_map()

    lats = [loc["lat"] for loc in locations]
    lons = [loc["lon"] for loc in locations]
    labels = [loc.get("label", "") for loc in locations]

    fig.add_trace(go.Scattermapbox(
        lat=lats, lon=lons, mode="markers",
        marker=dict(size=12, color="#D4901F"),
        text=labels, hoverinfo="text",
    ))

    span = max(max(lats) - min(lats), max(lons) - min(lons), 0.05)
    zoom = max(3.5, min(12, 8.3 - (span ** 0.45)))

    fig.update_layout(
        mapbox=dict(
            style="carto-positron",
            center=dict(lat=sum(lats) / len(lats), lon=sum(lons) / len(lons)),
            zoom=zoom,
        ),
        paper_bgcolor="#FFFFFF", margin=dict(l=0, r=0, t=0, b=0), showlegend=False, height=280,
        hoverlabel=dict(bgcolor="white", font_size=12, font_color="#1C1E24"),
    )
    return fig
def history_to_text(history) -> str:
    """
    Convert Gradio chat history to plain text.
    Compatible with both old and new Chatbot formats.
    """
    texts = []

    if not history:
        return ""

    for turn in history:
        if not isinstance(turn, dict):
            continue

        content = turn.get("content", "")

        if isinstance(content, str):
            texts.append(content)

        elif isinstance(content, list):
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        texts.append(text)

                elif isinstance(item, str):
                    texts.append(item)

    return " ".join(texts)

def _respond(message: str, history: list, provider: str, api_key: str):
    if not message or not message.strip():
        return history, "", _empty_map()

    if not api_key or not api_key.strip():
        history.append({"role": "user", "content": message})
        history.append({
            "role": "assistant",
            "content": "Please enter an API key for the selected provider before chatting.",
        })
        return history, "", _empty_map()

    try:
        agent = build_agent(provider, api_key)

        history_text = history_to_text(history)

        language_instruction = _detect_language_instruction(
            message,
            history_text
        )

        result = agent.invoke(
            {
                "input": message,
                "language_instruction": language_instruction,
            }
        )

        print("=" * 80)
        print("RESULT:")
        print(result)
        print("=" * 80)

        answer = result["output"]
        locations = extract_locations(result.get("intermediate_steps", []))

    except Exception as exc:
        import traceback
        traceback.print_exc()

        answer = f"{type(exc).__name__}: {exc}"
        locations = []

    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": answer})

    return history, "", _locations_map(locations)

def build_chatbot_tab() -> None:
    gr.Markdown(DISCLAIMER)

    with gr.Row():
        provider = gr.Dropdown(
            choices=PROVIDER_CHOICES, value="Claude", label="Provider",
            scale=1,
        )
        api_key = gr.Textbox(
            label="API Key", type="password",
            placeholder="Paste your API key here (kept in this session only)",
            scale=2,
        )

    with gr.Row():
        with gr.Column(scale=2):
            chatbot = gr.Chatbot(
                label="Ontario 511 Assistant", height=450,
                elem_classes=["chatbot-frame"], avatar_images=(None, "logo.png"),
            )
            with gr.Row():
                message = gr.Textbox(
                    label="Your question",
                    placeholder="e.g. Is there an incident mentioning a collision?",
                    scale=5, show_label=False,
                )
                send_button = gr.Button("Send", variant="primary", scale=1)
            clear_button = gr.Button("Clear conversation")

        with gr.Column(scale=1):
            gr.Markdown("**Mentioned locations**")
            location_map = gr.Plot(value=_empty_map(), label=None, show_label=False)

    message.submit(
        fn=_respond,
        inputs=[message, chatbot, provider, api_key],
        outputs=[chatbot, message, location_map],
    )
    send_button.click(
        fn=_respond,
        inputs=[message, chatbot, provider, api_key],
        outputs=[chatbot, message, location_map],
    )
    clear_button.click(
        fn=lambda: ([], "", _empty_map()), inputs=None,
        outputs=[chatbot, message, location_map],
    )