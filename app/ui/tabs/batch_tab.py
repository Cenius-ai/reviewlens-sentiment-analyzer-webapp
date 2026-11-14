"""Batch tab: upload a review CSV, score every row, chart it, download it."""

from __future__ import annotations

import json

import gradio as gr
import pandas as pd

from ... import config
from ...services import batch_service
from ..render import (
    batch_charts_html,
    batch_summary_html,
    batch_table_rows,
    esc,
    render_recent_batches,
    render_sentiment_chart,
    section_label,
)
from ..session import require_user

MAX_ROWS = config.MAX_BATCH_ROWS
TABLE_HEADERS = ["Row", "Label", "Score", "Review", "Price", "Quality", "Shipping"]
TABLE_TYPES = ["number", "str", "number", "str", "str", "str", "str"]

EMPTY_CHARTS = render_sentiment_chart({})
EMPTY_TABLE: list[list] = []
EMPTY_RECENT = render_recent_batches([])
INITIAL_STATUS = (
    '<div class="rl-card"><span class="rl-section-label">Upload</span>'
    '<div class="rl-empty"><strong>Upload a CSV of reviews to score them all at once</strong>'
    "Expected: a header row with at least one text column (for example "
    "<code>order_id,review,customer</code>). Blank review rows are skipped and reported."
    f" Each batch is capped at {MAX_ROWS:,} rows.</div></div>"
)


def build() -> dict:
    with gr.Column(elem_classes="rl-tab-panel"):
        gr.HTML(section_label("Batch CSV scoring"))
        with gr.Row(equal_height=False):
            with gr.Column(scale=5, min_width=300):
                upload = gr.File(
                    label="Review export (.csv)",
                    file_count="single",
                    type="filepath",
                    elem_id="rl-batch-upload",
                )
                column_dd = gr.Dropdown(
                    label="Column holding the review text",
                    choices=[],
                    value=None,
                    interactive=True,
                    elem_id="rl-batch-column",
                )
                score_btn = gr.Button("Score reviews", variant="primary")
                status = gr.HTML(INITIAL_STATUS)
            with gr.Column(scale=7, min_width=320):
                charts = gr.HTML(EMPTY_CHARTS)
        with gr.Column():
            table = gr.Dataframe(
                headers=TABLE_HEADERS,
                datatype=TABLE_TYPES,
                value=EMPTY_TABLE,
                interactive=False,
                wrap=True,
                label="Scored rows",
                elem_id="rl-batch-table",
            )
            recent = gr.HTML(EMPTY_RECENT)

    upload.change(_on_upload, inputs=[upload], outputs=[column_dd, status], queue=False, show_progress="hidden")
    score_btn.click(
        _score,
        inputs=[upload, column_dd],
        outputs=[status, charts, table, recent],
        api_name="batch_ui",
    )

    return {
        "upload": upload,
        "column_dd": column_dd,
        "score_btn": score_btn,
        "status": status,
        "charts": charts,
        "table": table,
        "recent": recent,
    }


def _columns_of(file_path: str) -> list[str]:
    frame = pd.read_csv(file_path, dtype=str, keep_default_na=False, nrows=0)
    frame.columns = [str(column).strip() for column in frame.columns]
    return list(frame.columns)


def _on_upload(file_path: str | None):
    if not file_path:
        return gr.Dropdown(choices=[], value=None), INITIAL_STATUS
    if not str(file_path).lower().endswith(".csv"):
        return gr.skip(), (
            '<div class="rl-error" role="alert">That file is not a .csv. Export your reviews as CSV and try again.</div>'
        )
    try:
        columns = _columns_of(file_path)
    except Exception:  # noqa: BLE001 - any parse failure is a plain message to the user
        return gr.skip(), (
            '<div class="rl-error" role="alert">That file could not be read as CSV. '
            "Check the delimiter and that the first row is a header.</div>"
        )
    if not columns:
        return gr.skip(), '<div class="rl-error" role="alert">That CSV has no columns.</div>'
    guess = batch_service.guess_text_column(columns)
    hint = (
        '<div class="rl-card"><p class="rl-body">'
        f"Found {len(columns)} columns: {esc(', '.join(columns))}. "
        "Pick the one holding the review text, then press Score reviews.</p></div>"
    )
    return gr.Dropdown(choices=columns, value=guess), hint


def _score(file_path: str | None, text_column: str | None, request: gr.Request):
    user = require_user(request)
    if not file_path:
        return (
            '<div class="rl-error" role="alert">Choose a CSV file first.</div>',
            gr.skip(),
            gr.skip(),
            gr.skip(),
        )
    with open(file_path, "rb") as handle:
        content = handle.read()
    filename = str(file_path).split("/")[-1]
    try:
        result = batch_service.score_csv(int(user["id"]), filename, text_column or "", content)
    except batch_service.BatchValidationError as exc:
        return (
            f'<div class="rl-error" role="alert">{esc(exc)}</div>',
            gr.skip(),
            gr.skip(),
            gr.skip(),
        )

    status = batch_summary_html(result)
    charts = batch_charts_html(result)
    table = batch_table_rows(result)
    recent = render_recent_batches(batch_service.list_batches(int(user["id"])))
    return status, charts, table, recent


def load_for(request: gr.Request):
    """Populate the tab with the signed-in user's most recent batch."""
    user = require_user(request)
    batches = batch_service.list_batches(int(user["id"]))
    if not batches:
        return EMPTY_CHARTS, EMPTY_TABLE, EMPTY_RECENT
    latest = batches[0]
    rows = batch_service.get_batch_rows(int(user["id"]), int(latest["id"]))
    summary = {
        "id": latest["id"],
        "filename": latest["filename"],
        "text_column": latest["text_column"],
        "row_count": latest["row_count"],
        "skipped_count": latest["skipped_count"],
        "counts": latest["counts"],
        "aspect_summary": _aspect_summary_from_rows(rows),
        "rows": [_table_row(row) for row in rows],
    }
    return batch_charts_html(summary), batch_table_rows(summary), render_recent_batches(batches)


def _table_row(row) -> dict:
    aspects = json.loads(row["aspects_json"])
    labels = {item["aspect"]: item["label"] for item in aspects.get("aspects", [])}
    return {
        "row_index": int(row["row_index"]) + 1,
        "label": row["sentiment_label"],
        "score": row["sentiment_score"],
        "review_text": row["review_text"],
        "price_label": labels.get("price", "neutral"),
        "quality_label": labels.get("quality", "neutral"),
        "shipping_label": labels.get("shipping", "neutral"),
    }


def _aspect_summary_from_rows(rows) -> dict:
    summary = {aspect: {"mentions": 0, "positive": 0, "neutral": 0, "negative": 0} for aspect in batch_service.ASPECTS}
    for row in rows:
        aspects = json.loads(row["aspects_json"])
        for item in aspects.get("aspects", []):
            if item["mentions"]:
                summary[item["aspect"]]["mentions"] += int(item["mentions"])
                summary[item["aspect"]][item["label"]] += 1
    return summary
