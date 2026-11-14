"""Samples tab: three seeded review sets, previews and send-to-analyzer."""

from __future__ import annotations

import gradio as gr

from ...services import sample_service
from ..render import empty_result, esc, render_sample_reviews, section_label
from ..session import require_user

SWITCH_TO_ANALYZE_JS = """() => {
  try {
    const tabs = document.querySelectorAll('#rl-tabs button[role="tab"]');
    if (tabs && tabs.length > 0) { tabs[0].click(); }
  } catch (err) {
    /* the review is loaded either way - never break the handler */
  }
}"""


def build(analyze: dict) -> dict:
    sets = sample_service.list_sets()

    with gr.Column(elem_classes="rl-tab-panel"):
        gr.HTML(section_label("Sample review sets"))
        gr.HTML(
            '<p class="rl-body" style="max-width:70ch;margin-bottom:12px">'
            "Seeded review sets so you can see the analyzer work without preparing data. "
            "Open a set to read the reviews, then send one to the Analyze tab.</p>"
        )
        if not sets:
            gr.HTML(
                '<div class="rl-card"><div class="rl-empty"><strong>No sample sets available</strong>'
                "Seeding did not run - restart the app to recreate the demo review sets.</div></div>"
            )
            return {"buttons": []}

        buttons = []
        for index, entry in enumerate(sets):
            detail = sample_service.get_set(int(entry["id"])) or {**entry, "reviews": []}
            reviews = detail.get("reviews") or []
            with gr.Accordion(
                f"{entry['name']} · {entry['review_count']} reviews",
                open=index == 0,
                elem_classes=["rl-sample-accordion"],
            ):
                gr.HTML(
                    f'<p class="rl-body" style="max-width:74ch">{esc(entry["description"])}</p>'
                    + render_sample_reviews(reviews)
                )
                first_review = reviews[0] if reviews else ""
                with gr.Row():
                    button = gr.Button("Send first review to analyzer", variant="secondary", scale=2)
                button.click(
                    _send_factory(first_review),
                    inputs=None,
                    outputs=[analyze["review_box"], analyze["result_panel"], analyze["message"]],
                    queue=False,
                    show_progress="hidden",
                    js=SWITCH_TO_ANALYZE_JS,
                )
                buttons.append(button)

        gr.HTML(
            '<p class="rl-note">Need your own data instead? The Batch tab scores a whole CSV export.</p>'
        )

    return {"buttons": buttons}


def _send_factory(review_text: str):
    def _send(request: gr.Request):
        require_user(request)
        note = (
            '<div class="rl-note">Loaded from the sample set into the Analyze tab - press Analyze review.</div>'
        )
        return review_text, empty_result(), note

    return _send
