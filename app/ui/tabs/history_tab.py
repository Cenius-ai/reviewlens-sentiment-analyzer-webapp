"""History tab: newest-first analyses, reload into Analyze, confirmed clear."""

from __future__ import annotations

import gradio as gr

from ...services import history_service
from ..render import (
    history_rows,
    human_timestamp,
    render_history_summary,
    render_result_card,
    section_label,
)
from ..session import require_user

SWITCH_TO_ANALYZE_JS = """() => {
  try {
    const tabs = document.querySelectorAll('#rl-tabs button[role="tab"]');
    if (tabs && tabs.length > 0) { tabs[0].click(); }
  } catch (err) {
    /* the review is loaded either way - never break the handler */
  }
}"""

HEADERS = ["When", "Label", "Score", "Review"]
TYPES = ["str", "str", "number", "str"]


def build(analyze: dict) -> dict:
    with gr.Column(elem_classes="rl-tab-panel"):
        gr.HTML(section_label("History"))
        summary = gr.HTML(render_history_summary(0, {}))
        state = gr.State([])
        table = gr.Dataframe(
            headers=HEADERS,
            datatype=TYPES,
            value=[],
            interactive=False,
            wrap=True,
            label="Stored analyses - click a row to reload it into Analyze",
            elem_id="rl-history-table",
        )
        with gr.Row():
            confirm = gr.Checkbox(
                label="I understand this deletes every stored analysis for my account",
                value=False,
                scale=4,
            )
            clear_btn = gr.Button("Clear history", variant="secondary", scale=1)
        clear_message = gr.HTML("")

    table.select(
        _reload_row,
        inputs=[state],
        outputs=[analyze["review_box"], analyze["result_panel"], analyze["message"]],
        js=SWITCH_TO_ANALYZE_JS,
    )
    clear_btn.click(
        _clear,
        inputs=[confirm],
        outputs=[table, summary, state, clear_message, confirm],
        api_name="clear_history_ui",
    )

    return {
        "summary": summary,
        "table": table,
        "state": state,
        "confirm": confirm,
        "clear_btn": clear_btn,
        "clear_message": clear_message,
    }


def load_for(request: gr.Request):
    """Populate the history table for the signed-in user."""
    user = require_user(request)
    analyses = history_service.list_analyses(int(user["id"]))
    counts = history_service.label_counts(int(user["id"]))
    return analyses, history_rows(analyses), render_history_summary(len(analyses), counts)


def _reload_row(analyses: list[dict], evt: gr.SelectData):
    if not analyses or evt is None or evt.index is None:
        return gr.skip(), gr.skip(), gr.skip()
    row_index = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
    try:
        item = analyses[int(row_index)]
    except (IndexError, TypeError, ValueError):
        return gr.skip(), gr.skip(), gr.skip()
    note = f"Loaded from history · {human_timestamp(item.get('created_at'))}"
    return item.get("review_text", ""), render_result_card(item, note), ""


def _clear(confirmed: bool, request: gr.Request):
    user = require_user(request)
    if not confirmed:
        return (
            gr.skip(),
            gr.skip(),
            gr.skip(),
            '<div class="rl-note">Tick the confirmation box first - nothing was deleted.</div>',
            gr.skip(),
        )
    removed = history_service.clear_analyses(int(user["id"]))
    message = (
        f'<div class="rl-note">Cleared {removed:,} analyses. New analyses will save normally.</div>'
    )
    return [], render_history_summary(0, history_service.label_counts(int(user["id"]))), [], message, False
