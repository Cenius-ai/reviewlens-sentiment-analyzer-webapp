"""Gradio theme bound to the committed design tokens."""

from __future__ import annotations

import gradio as gr

from .. import config

FONT_STACK = [
    "Atkinson Hyperlegible",
    "Helvetica Neue",
    "Arial",
    "sans-serif",
]

FONT_MONO = ["SFMono-Regular", "JetBrains Mono", "Consolas", "monospace"]

# Hex twins of the committed tokens. Chart and library code only ever sees these
# (never oklch()/var() strings, which canvas/SVG chart APIs cannot parse).
CHART_COLORS = {
    "positive": "#0b7a5c",
    "neutral": "#6b7780",
    "negative": "#b8322f",
    "accent": "#009494",
    "grid": "#0b1418",
}


def stylesheet() -> str:
    """The one stylesheet, served inline to Gradio and linked by the login page."""
    return (config.static_dir() / "app.css").read_text(encoding="utf-8")


def build_theme() -> gr.themes.Base:
    return gr.themes.Base(
        font=FONT_STACK,
        font_mono=FONT_MONO,
        primary_hue=gr.themes.colors.teal,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
        radius_size=gr.themes.sizes.radius_sm,
        spacing_size=gr.themes.sizes.spacing_sm,
        text_size=gr.themes.sizes.text_sm,
    ).set(
        body_background_fill="#f5fbff",
        body_text_color="#0b1418",
        body_text_color_subdued="#5a656b",
        background_fill_primary="#f5fbff",
        background_fill_secondary="#e8eef1",
        block_background_fill="#fdffff",
        block_border_color="#d9dfe2",
        block_label_text_color="#5a656b",
        block_title_text_color="#0b1418",
        panel_background_fill="#fdffff",
        panel_border_color="#d9dfe2",
        input_background_fill="#ffffff",
        input_border_color="#d9dfe2",
        input_placeholder_color="#7d888e",
        color_accent="#009494",
        color_accent_soft="#e2f2f1",
        link_text_color="#046d6c",
        button_primary_background_fill="#009494",
        button_primary_background_fill_hover="#00a0a0",
        button_primary_text_color="#111111",
        button_primary_border_color="#00807f",
        button_secondary_background_fill="#e8eef1",
        button_secondary_background_fill_hover="#dfe6ea",
        button_secondary_text_color="#0b1418",
        button_secondary_border_color="#d9dfe2",
        border_color_primary="#d9dfe2",
        table_odd_background_fill="#fbfeff",
        table_even_background_fill="#fdffff",
    )
