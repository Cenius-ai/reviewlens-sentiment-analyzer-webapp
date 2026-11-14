"""HTML renderers for the Gradio panels.

Everything that reaches a browser from user or database text is escaped here -
these strings are injected into ``gr.HTML`` components, which render raw markup.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone

from ..nlp.aspects import ASPECT_LABELS
from .theme import CHART_COLORS

LABEL_TEXT = {"positive": "Positive", "neutral": "Neutral", "negative": "Negative"}
LABEL_GLYPH = {"positive": "▲", "neutral": "■", "negative": "▼"}


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


# ----------------------------------------------------------------- time bits
def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def human_timestamp(value: str | None) -> str:
    """Absolute + relative, clamped so it never renders 'in -1 days'."""
    parsed = _parse_iso(value)
    if parsed is None:
        return "unknown time"
    absolute = parsed.strftime("%d %b %Y · %H:%M UTC")
    delta_seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
    if delta_seconds < 60:
        relative = "just now"
    elif delta_seconds < 3600:
        minutes = int(delta_seconds // 60)
        relative = f"{minutes} min ago"
    elif delta_seconds < 86_400:
        hours = int(delta_seconds // 3600)
        relative = f"{hours} h ago"
    elif delta_seconds < 86_400 * 60:
        days = int(delta_seconds // 86_400)
        relative = "yesterday" if days == 1 else f"{days} days ago"
    else:
        relative = parsed.strftime("%d %b %Y")
    return f"{absolute} ({relative})"


# --------------------------------------------------------------------- chips
def chip(label: str) -> str:
    key = label if label in LABEL_TEXT else "neutral"
    glyph = LABEL_GLYPH[key]
    return (
        f'<span class="rl-chip rl-chip--{key}">'
        f'<span aria-hidden="true">{glyph}</span>{LABEL_TEXT[key]}</span>'
    )


def section_label(text: str) -> str:
    return f'<span class="rl-section-label">{esc(text)}</span>'


def format_score(score: float) -> str:
    return f"{score:+.2f}"


def counter_html(length: int, limit: int) -> str:
    return (
        f'<div class="rl-meta rl-num" role="status" aria-live="polite">'
        f"{length:,} / {limit:,} characters</div>"
    )


# ----------------------------------------------------------------- the gauge
def gauge(score: float) -> str:
    score = max(-1.0, min(1.0, float(score)))
    width = abs(score) * 50
    if score >= 0:
        style = f"left:50%;width:{width:.2f}%"
        kind = "positive"
    else:
        style = f"left:{50 - width:.2f}%;width:{width:.2f}%"
        kind = "negative"
    label = f"Sentiment score {format_score(score)} on a -1 to 1 scale"
    return f"""
<div class="rl-gauge">
  <div class="rl-gauge-track" role="img" aria-label="{esc(label)}">
    <div class="rl-gauge-zero" aria-hidden="true"></div>
    <div class="rl-gauge-fill rl-gauge-fill--{kind}" style="{esc(style)}"></div>
  </div>
  <div class="rl-gauge-axis" aria-hidden="true">
    <span>-1 negative</span><span>0</span><span>positive +1</span>
  </div>
</div>"""


# ------------------------------------------------------------------ results
def empty_result() -> str:
    return (
        '<div class="rl-card">'
        f'{section_label("Result")}'
        '<div class="rl-empty"><strong>Paste a review and press Analyze</strong>'
        "You will get a label, a -1 to 1 score, the lexicon words that fired and a"
        " price / quality / shipping breakdown.</div></div>"
    )


def render_words(fired: list[dict]) -> str:
    if not fired:
        return '<p class="rl-meta">No lexicon words fired - the review reads neutral.</p>'
    items = []
    for item in fired:
        word = esc(item.get("word", ""))
        value = float(item.get("value", 0) or 0)
        kind = "positive" if value > 0 else "negative" if value < 0 else "neutral"
        extra = " · negated" if item.get("negated") else ""
        items.append(
            f'<li class="rl-word rl-word--{kind}">{word} '
            f'<small>{format_score(value)}{extra}</small></li>'
        )
    return f'<ul class="rl-words">{"".join(items)}</ul>'


def render_aspects(aspects: dict) -> str:
    items = (aspects or {}).get("aspects") or []
    mentioned = [item for item in items if item.get("mentions")]
    if not mentioned:
        return (
            '<div class="rl-empty"><strong>No aspects detected</strong>'
            "This review did not mention price, quality or shipping.</div>"
        )
    rows = []
    for item in items:
        aspect = item.get("aspect", "")
        label = item.get("label", "neutral")
        mentions = int(item.get("mentions", 0) or 0)
        excerpts = item.get("excerpts") or []
        why = "; ".join(esc(excerpt) for excerpt in excerpts) if excerpts else "—"
        verdict = chip(label) if mentions else '<span class="rl-chip rl-chip--muted">Not mentioned</span>'
        rows.append(
            "<tr>"
            f'<td data-label="Aspect"><strong>{esc(ASPECT_LABELS.get(aspect, aspect))}</strong></td>'
            f'<td data-label="Verdict">{verdict}</td>'
            f'<td data-label="Mentions" class="num">{mentions}</td>'
            f'<td data-label="Why" class="rl-excerpt">{why}</td>'
            "</tr>"
        )
    return (
        '<table class="rl-table rl-table-stacked">'
        "<caption>Aspect breakdown - derived only from the clauses that matched</caption>"
        "<thead><tr><th>Aspect</th><th>Verdict</th><th>Mentions</th><th>Matched clause</th></tr></thead>"
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def render_result_card(result: dict, note: str | None = None) -> str:
    label = result.get("label", "neutral")
    score = float(result.get("score", 0) or 0)
    note_html = f'<p class="rl-meta">{esc(note)}</p>' if note else ""
    review = esc(result.get("review_text", ""))
    return f"""
<section class="rl-card rl-result">
  {section_label("Result")}
  <div class="rl-card-header">
    <div class="rl-score-row">
      {chip(label)}
      <span class="rl-score">{format_score(score)}</span>
      <span class="rl-meta">sentiment score</span>
    </div>
    {note_html}
  </div>
  {gauge(score)}
  <h3 class="rl-h3">Lexicon words that fired</h3>
  {render_words(result.get("fired") or [])}
  <h3 class="rl-h3" style="margin-top:16px">Aspects</h3>
  {render_aspects(result.get("aspects") or {})}
  <h3 class="rl-h3" style="margin-top:16px">Review</h3>
  <p class="rl-body rl-review-text">{review}</p>
</section>"""


# ------------------------------------------------------------- batch charts
def _gridlines(width: int, height: int, left: int, top: int, right: int) -> str:
    """1px gridlines at 8% opacity - one grid style shared by every chart."""
    parts = []
    for fraction in (0, 0.25, 0.5, 0.75, 1.0):
        x = left + fraction * (right - left)
        parts.append(
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{height}" '
            'stroke="#0b1418" stroke-opacity="0.08" stroke-width="1" />'
        )
    return "".join(parts)


def render_sentiment_chart(counts: dict) -> str:
    total = sum(int(counts.get(key, 0)) for key in ("positive", "neutral", "negative"))
    if total == 0:
        return (
            '<div class="rl-card"><div class="rl-empty"><strong>Nothing scored yet</strong>'
            "Upload a CSV of reviews to see the sentiment split.</div></div>"
        )

    left, right = 96, 560
    row_height = 40
    top = 16
    height = top + row_height * 3 + 6
    max_count = max(int(counts.get(key, 0)) for key in ("positive", "neutral", "negative")) or 1

    bars = []
    for index, key in enumerate(("positive", "neutral", "negative")):
        count = int(counts.get(key, 0))
        y = top + index * row_height
        width = (count / max_count) * (right - left)
        share = (count / total) * 100
        bars.append(
            f'<text x="0" y="{y + 17}" font-size="12" font-weight="700" '
            f'fill="#0b1418" font-family="Atkinson Hyperlegible, sans-serif">{LABEL_TEXT[key]}</text>'
            f'<rect x="{left}" y="{y + 2}" width="{max(width, 1):.1f}" height="20" rx="2" '
            f'fill="{CHART_COLORS[key]}" />'
            f'<text x="{left + max(width, 1) + 8:.1f}" y="{y + 17}" font-size="12" '
            f'fill="#5a656b" font-family="Atkinson Hyperlegible, sans-serif" '
            f'font-variant-numeric="tabular-nums">{count:,} · {share:.0f}%</text>'
        )

    ticks = []
    for fraction in (0, 0.25, 0.5, 0.75, 1.0):
        x = left + fraction * (right - left)
        ticks.append(
            f'<text x="{x:.1f}" y="{height + 14}" font-size="11" fill="#5a656b" '
            f'text-anchor="middle">{int(round(fraction * max_count))}</text>'
        )

    return f"""
<div class="rl-chart">
  <div class="rl-chart-head">
    <h3 class="rl-h2">Sentiment split</h3>
    <span class="rl-meta rl-num">{total:,} reviews scored</span>
  </div>
  <svg viewBox="0 0 600 {height + 22}" role="img"
       aria-label="Bar chart of {counts.get('positive', 0)} positive, {counts.get('neutral', 0)} neutral and {counts.get('negative', 0)} negative reviews">
    {_gridlines(600, height, left, top, right)}
    {"".join(bars)}
    {"".join(ticks)}
  </svg>
  <div class="rl-chart-legend">
    <span class="rl-legend-item"><span class="rl-swatch" style="background:{CHART_COLORS['positive']}"></span>▲ Positive</span>
    <span class="rl-legend-item"><span class="rl-swatch" style="background:{CHART_COLORS['neutral']}"></span>■ Neutral</span>
    <span class="rl-legend-item"><span class="rl-swatch" style="background:{CHART_COLORS['negative']}"></span>▼ Negative</span>
  </div>
</div>"""


def render_aspect_chart(aspect_summary: dict) -> str:
    rows = []
    for aspect in ("price", "quality", "shipping"):
        data = aspect_summary.get(aspect) or {}
        mentions = int(data.get("mentions", 0) or 0)
        pos = int(data.get("positive", 0) or 0)
        neu = int(data.get("neutral", 0) or 0)
        neg = int(data.get("negative", 0) or 0)
        total = pos + neu + neg
        if total:
            segments = []
            for value, key in ((pos, "positive"), (neu, "neutral"), (neg, "negative")):
                if value:
                    segments.append(
                        f'<span class="rl-swatch" style="background:{CHART_COLORS[key]};'
                        f'width:{value / total * 100:.1f}%;height:10px;border-radius:2px;'
                        f'display:inline-block"></span>'
                    )
            bar = (
                '<span class="rl-stack" style="display:flex;gap:2px;width:100%;min-width:120px">'
                + "".join(segments)
                + "</span>"
            )
        else:
            bar = '<span class="rl-meta">no mentions</span>'
        rows.append(
            "<tr>"
            f'<td data-label="Aspect"><strong>{esc(ASPECT_LABELS[aspect])}</strong></td>'
            f'<td data-label="Mentions" class="num">{mentions:,}</td>'
            f'<td data-label="Pos / Neu / Neg" class="num">{pos:,} / {neu:,} / {neg:,}</td>'
            f'<td data-label="Mix">{bar}</td>'
            "</tr>"
        )
    return f"""
<div class="rl-chart">
  <div class="rl-chart-head">
    <h3 class="rl-h2">Aspect breakdown</h3>
    <span class="rl-meta">rows whose clause matched each aspect</span>
  </div>
  <table class="rl-table rl-table-stacked">
    <thead><tr><th>Aspect</th><th>Mentions</th><th>Pos / Neu / Neg</th><th>Mix</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</div>"""


def batch_summary_html(result: dict) -> str:
    counts = result.get("counts") or {}
    skipped = int(result.get("skipped_count", 0) or 0)
    row_count = int(result.get("row_count", 0) or 0)
    skipped_note = (
        f'<p class="rl-meta">{skipped:,} blank row{"s" if skipped != 1 else ""} skipped.</p>'
        if skipped
        else ""
    )
    download = result.get("download_url")
    download_html = (
        f'<a class="rl-signout" href="{esc(download)}" download>Download scored CSV</a>'
        if download
        else ""
    )
    return f"""
<div class="rl-card">
  {section_label("Batch result")}
  <div class="rl-card-header">
    <div>
      <h2 class="rl-h2">{esc(result.get("filename", "upload.csv"))}</h2>
      <p class="rl-meta rl-num">{row_count:,} rows scored · text column “{esc(result.get("text_column", ""))}”</p>
      {skipped_note}
    </div>
    {download_html}
  </div>
  <div class="rl-grid-figures">
    <div class="rl-stat"><div class="rl-stat-label">Positive</div>
      <div class="rl-stat-value" style="color:{CHART_COLORS['positive']}">{int(counts.get('positive', 0)):,}</div></div>
    <div class="rl-stat"><div class="rl-stat-label">Neutral</div>
      <div class="rl-stat-value" style="color:{CHART_COLORS['neutral']}">{int(counts.get('neutral', 0)):,}</div></div>
    <div class="rl-stat"><div class="rl-stat-label">Negative</div>
      <div class="rl-stat-value" style="color:{CHART_COLORS['negative']}">{int(counts.get('negative', 0)):,}</div></div>
    <div class="rl-stat"><div class="rl-stat-label">Skipped</div>
      <div class="rl-stat-value">{skipped:,}</div></div>
  </div>
</div>"""


def batch_charts_html(result: dict) -> str:
    return (
        '<div class="rl-stack-vertical">'
        + render_sentiment_chart(result.get("counts") or {})
        + render_aspect_chart(result.get("aspect_summary") or {})
        + "</div>"
    )


def batch_table_rows(result: dict) -> list[list]:
    rows = []
    for row in result.get("rows") or []:
        excerpt = row.get("review_text") or ""
        if len(excerpt) > 120:
            excerpt = excerpt[:119].rstrip() + "…"
        rows.append(
            [
                int(row.get("row_index", 0)),
                row.get("label", "neutral").capitalize(),
                round(float(row.get("score", 0) or 0), 3),
                excerpt,
                row.get("price_label", "neutral").capitalize(),
                row.get("quality_label", "neutral").capitalize(),
                row.get("shipping_label", "neutral").capitalize(),
            ]
        )
    return rows


def render_recent_batches(batches: list[dict]) -> str:
    if not batches:
        return (
            '<div class="rl-card"><div class="rl-empty"><strong>No batches yet</strong>'
            "Score your first CSV and it will appear here with a download link.</div></div>"
        )
    rows = []
    for batch in batches:
        counts = batch.get("counts") or {}
        rows.append(
            "<tr>"
            f'<td data-label="File">{esc(batch.get("filename", ""))}</td>'
            f'<td data-label="Rows" class="num">{int(batch.get("row_count", 0)):,}</td>'
            f'<td data-label="Positive" class="num">{int(counts.get("positive", 0)):,}</td>'
            f'<td data-label="Neutral" class="num">{int(counts.get("neutral", 0)):,}</td>'
            f'<td data-label="Negative" class="num">{int(counts.get("negative", 0)):,}</td>'
            f'<td data-label="When" class="rl-excerpt">{esc(human_timestamp(batch.get("created_at")))}</td>'
            f'<td data-label="Download"><a href="{esc(batch.get("download_url", "#"))}" download>CSV</a></td>'
            "</tr>"
        )
    return f"""
<div class="rl-card">
  <div class="rl-card-header">
    {section_label("Recent batches")}
    <span class="rl-meta">stored in SQLite, downloadable any time</span>
  </div>
  <table class="rl-table rl-table-stacked">
    <thead><tr><th>File</th><th>Rows</th><th>Positive</th><th>Neutral</th><th>Negative</th><th>When</th><th>Download</th></tr></thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
</div>"""


# ------------------------------------------------------------------ samples
def render_sample_reviews(reviews: list[str]) -> str:
    items = "".join(f"<li>{esc(review)}</li>" for review in reviews)
    return f'<ul class="rl-sample-list">{items}</ul>'


# ------------------------------------------------------------------ history
def render_history_summary(total: int, counts: dict) -> str:
    if total == 0:
        return (
            '<div class="rl-empty"><strong>No analyses yet</strong>'
            "Score a review on the Analyze tab and it will be saved here."
            "</div>"
        )
    return f"""
<div class="rl-card">
  <div class="rl-card-header">
    {section_label("History")}
    <span class="rl-meta rl-num">{total:,} stored analyses</span>
  </div>
  <div class="rl-toolbar">
    {chip("positive")} <span class="rl-num rl-meta">{int(counts.get('positive', 0)):,}</span>
    {chip("neutral")} <span class="rl-num rl-meta">{int(counts.get('neutral', 0)):,}</span>
    {chip("negative")} <span class="rl-num rl-meta">{int(counts.get('negative', 0)):,}</span>
  </div>
</div>"""


def history_rows(analyses: list[dict]) -> list[list]:
    rows = []
    for item in analyses:
        excerpt = item.get("review_text", "")
        if len(excerpt) > 90:
            excerpt = excerpt[:89].rstrip() + "…"
        rows.append(
            [
                human_timestamp(item.get("created_at")),
                item.get("label", "neutral").capitalize(),
                round(float(item.get("score", 0) or 0), 3),
                excerpt,
            ]
        )
    return rows
