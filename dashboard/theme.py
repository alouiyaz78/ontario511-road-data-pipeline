"""
Thème visuel du dashboard Ontario 511.

Palette ancrée dans le sujet (signalisation routière, asphalte, hiver
ontarien) plutôt que dans les défauts Gradio : voir la discussion de
design pour la justification de chaque teinte.
"""

import gradio as gr

ASPHALT_900 = "#14161B"
ASPHALT_700 = "#22252C"
SIGNAL_AMBER = "#F0A93A"
ROUTE_BLUE = "#3D6FB4"
FROST_WHITE = "#E8EAED"
CONCRETE_500 = "#6B6E76"

ontario511_theme = gr.themes.Base(
    primary_hue=gr.themes.colors.Color(
        name="signal_amber",
        c50="#FEF6E9", c100="#FCE9C7", c200="#F9D89A", c300="#F5C56D",
        c400="#F2B750", c500=SIGNAL_AMBER, c600="#D4901F", c700="#A8721A",
        c800="#7C5514", c900="#50370D", c950="#2E1F07",
    ),
    secondary_hue=gr.themes.colors.Color(
        name="route_blue",
        c50="#EAF0F9", c100="#C9D9EE", c200="#A3BFE1", c300="#7CA5D4",
        c400="#5A8CC8", c500=ROUTE_BLUE, c600="#325A94", c700="#274670",
        c800="#1C334F", c900="#111F30", c950="#0A121C",
    ),
    neutral_hue=gr.themes.colors.Color(
        name="asphalt",
        c50=FROST_WHITE, c100="#C7CACF", c200="#A5A8AF", c300="#83868F",
        c400=CONCRETE_500, c500="#54565D", c600=ASPHALT_700, c700="#1C1E24",
        c800=ASPHALT_900, c900="#0D0E11", c950="#08090B",
    ),
    font=(gr.themes.GoogleFont("Inter"), "ui-sans-serif", "sans-serif"),
    font_mono=(gr.themes.GoogleFont("JetBrains Mono"), "ui-monospace", "monospace"),
).set(
    body_background_fill=ASPHALT_900,
    body_background_fill_dark=ASPHALT_900,
    background_fill_primary=ASPHALT_700,
    background_fill_primary_dark=ASPHALT_700,
    block_background_fill=ASPHALT_700,
    block_background_fill_dark=ASPHALT_700,
    block_border_color="#2E313A",
    block_border_color_dark="#2E313A",
    body_text_color=FROST_WHITE,
    body_text_color_dark=FROST_WHITE,
    body_text_color_subdued=CONCRETE_500,
    body_text_color_subdued_dark=CONCRETE_500,
    button_primary_background_fill=SIGNAL_AMBER,
    button_primary_background_fill_hover="#D4901F",
    button_primary_text_color=ASPHALT_900,
    block_title_text_color=FROST_WHITE,
    block_title_text_color_dark=FROST_WHITE,
    block_label_text_color=CONCRETE_500,
    block_label_text_color_dark=CONCRETE_500,
)

# Couleurs exposées pour usage direct dans les graphiques Plotly
# (Gestalt — similarité : ces couleurs identifient la même catégorie
# "perturbation active" partout dans le dashboard, carte comme graphiques)
PLOTLY_COLORS = {
    "background": ASPHALT_700,
    "paper": ASPHALT_700,
    "text": FROST_WHITE,
    "grid": "#2E313A",
    "active": SIGNAL_AMBER,
    "neutral": ROUTE_BLUE,
    "muted": CONCRETE_500,
}