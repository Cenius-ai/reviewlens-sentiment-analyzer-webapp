"""Analyze tab: one review in, label + score + words + aspects out."""

from __future__ import annotations

import gradio as gr

from ... import config
from ...services import analyze_service
from ..render import counter_html, empty_result, esc, human_timestamp, render_result_card, section_label
from ..session import require_user

MAX_CHARS = config.MAX_REVIEW_CHARS

EXAMPLES = [
    "Absolutely love it, great quality and fast delivery.",
    "Cheapest price around, but the quality is awful and shipping took three weeks.",
    "Not good at all - the zipper jammed on day two and support ignored me.",
]


def build() -> dict:
    with gr.Column(elem_classes="rl-tab-panel"):
        gr.HTML(section_label("Analyze one review"))
        with gr.Row(equal_height=False):
            with gr.Column(scale=6, min_width=320):
                review_box = gr.Textbox(
                    label="Review text",
                    placeholder="Paste a product review here…",
                    lines=8,
                    max_lines=18,
                    show_label=True,
                    elem_id="rl-review-input",
                )
                counter = gr.HTML(counter_html(0, MAX_CHARS))
                with gr.Row():
                    analyze_btn = gr.Button("Analyze review", variant="primary", scale=2)
                    clear_btn = gr.Button("Clear", variant="secondary", scale=1)
                message = gr.HTML("")
                gr.Examples(
                    examples=[[text] for text in EXAMPLES],
                    inputs=[review_box],
                    label="Try one of these",
                )
            with gr.Column(scale=6, min_width=320):
                result_panel = gr.HTML(empty_result())

    # Keep the counter honest for every way text arrives: typing/pasting (``input``),
    # a committed change, and the Analyze round-trip itself.
    for trigger in (review_box.input, review_box.change):
        trigger(_update_counter, inputs=review_box, outputs=[counter], queue=False, show_progress="hidden")
    analyze_btn.click(
        _analyze,
        inputs=[review_box],
        outputs=[result_panel, message, counter],
        api_name="analyze_ui",
    )
    clear_btn.click(
        _clear,
        inputs=None,
        outputs=[review_box, counter, message, result_panel],
        queue=False,
        show_progress="hidden",
    )

    return {
        "review_box": review_box,
        "counter": counter,
        "message": message,
        "result_panel": result_panel,
        "analyze_btn": analyze_btn,
    }


def _update_counter(text: str) -> str:
    length = len(text or "")
    if length > MAX_CHARS:
        over = length - MAX_CHARS
        return (
            f'<div class="rl-error" role="status" aria-live="polite">'
            f"{length:,} / {MAX_CHARS:,} characters - remove {over:,} to score it.</div>"
        )
    return counter_html(length, MAX_CHARS)


def _analyze(text: str, request: gr.Request) -> tuple[str, str, str]:
    user = require_user(request)
    counter = _update_counter(text)
    try:
        result = analyze_service.analyze_review(int(user["id"]), text)
    except analyze_service.ReviewValidationError as exc:
        return empty_result(), f'<div class="rl-error" role="alert">{esc(exc)}</div>', counter

    note = f"Saved to your history · {human_timestamp(result['created_at'])}"
    return render_result_card(result, note), "", counter


def _clear():
    return "", counter_html(0, MAX_CHARS), "", empty_result()
