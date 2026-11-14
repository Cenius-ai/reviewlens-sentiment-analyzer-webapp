"""Batch CSV scoring: parse an upload, score every review row, persist, export."""

from __future__ import annotations

import csv
import io
import json
import sqlite3

import pandas as pd

from .. import config, db
from ..nlp import extract_aspects, get_lexicon, score_text

MAX_BATCH_ROWS = config.MAX_BATCH_ROWS
SENTIMENT_COLUMNS = ("sentiment_label", "sentiment_score")
ASPECT_COLUMNS = ("price_label", "quality_label", "shipping_label")
DERIVED_COLUMNS = SENTIMENT_COLUMNS + ASPECT_COLUMNS
ASPECTS = ("price", "quality", "shipping")


class BatchValidationError(ValueError):
    """An upload that cannot be scored, with a message fit for the UI."""


def score_csv(user_id: int, filename: str, text_column: str, content: bytes) -> dict:
    name = (filename or "upload.csv").split("/")[-1]
    if not name.lower().endswith(".csv"):
        raise BatchValidationError("That file is not a .csv. Export your reviews as CSV and try again.")

    frame = _read_csv(content)
    if len(frame) == 0:
        raise BatchValidationError("That CSV has no data rows.")

    columns = [str(column) for column in frame.columns]
    chosen = (text_column or "").strip()
    if not chosen:
        chosen = guess_text_column(columns)
    if chosen not in columns:
        raise BatchValidationError(
            "Column '{0}' is not in this file. Available columns: {1}".format(
                chosen or "(none)", ", ".join(columns)
            )
        )
    if len(frame) > MAX_BATCH_ROWS:
        raise BatchValidationError(
            f"That upload has {len(frame):,} rows - each batch is capped at {MAX_BATCH_ROWS:,} rows."
        )

    lexicon = get_lexicon()
    scored_rows: list[dict] = []
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    aspect_summary = {aspect: {"mentions": 0, "positive": 0, "neutral": 0, "negative": 0} for aspect in ASPECTS}
    skipped = 0

    for row_index, value in enumerate(frame[chosen].tolist()):
        text = "" if value is None else str(value).strip()
        if not text:
            skipped += 1
            continue
        sentiment = score_text(text, lexicon)
        aspects = extract_aspects(text, lexicon)
        label_by_aspect = {item["aspect"]: item for item in aspects["aspects"]}

        counts[sentiment.label] += 1
        for aspect in ASPECTS:
            item = label_by_aspect[aspect]
            if item["mentions"]:
                aspect_summary[aspect]["mentions"] += item["mentions"]
                aspect_summary[aspect][item["label"]] += 1

        scored_rows.append(
            {
                "row_index": row_index,
                "review_text": text,
                "label": sentiment.label,
                "score": sentiment.score,
                "aspects": aspects,
                "price_label": label_by_aspect["price"]["label"],
                "quality_label": label_by_aspect["quality"]["label"],
                "shipping_label": label_by_aspect["shipping"]["label"],
            }
        )

    if not scored_rows:
        raise BatchValidationError(f"Every row in column '{chosen}' was blank - nothing to score.")

    source = {
        "columns": columns,
        "rows": frame.fillna("").astype(str).values.tolist(),
    }
    batch_id = _persist(user_id, name, chosen, scored_rows, skipped, counts, aspect_summary, source)

    return {
        "id": batch_id,
        "filename": name,
        "text_column": chosen,
        "row_count": len(scored_rows),
        "skipped_count": skipped,
        "counts": counts,
        "aspect_summary": aspect_summary,
        "rows": [
            {
                "row_index": row["row_index"] + 1,
                "review_text": row["review_text"],
                "label": row["label"],
                "score": row["score"],
                "price_label": row["price_label"],
                "quality_label": row["quality_label"],
                "shipping_label": row["shipping_label"],
            }
            for row in scored_rows
        ],
        "download_url": f"/api/batch/{batch_id}/download",
        "created_at": db.utc_now(),
    }


def _read_csv(content: bytes) -> pd.DataFrame:
    if not content or not content.strip():
        raise BatchValidationError("That file is empty.")
    if b"\x00" in content[:2048]:
        raise BatchValidationError("That file is not a text CSV.")
    text = _decode(content)
    delimiter = _detect_delimiter(text)
    try:
        frame = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False, sep=delimiter)
    except pd.errors.EmptyDataError as exc:
        raise BatchValidationError("That CSV has no data rows.") from exc
    except (pd.errors.ParserError, ValueError) as exc:
        raise BatchValidationError(
            "That file could not be read as CSV. Check the delimiter and that the first row is a header."
        ) from exc
    frame.columns = [str(column).strip() for column in frame.columns]
    return frame


def _detect_delimiter(text: str) -> str:
    """Comma by default; accept ; \t and | exports too. Never guess per-character."""
    sample = "\n".join(text.splitlines()[:20])
    if not sample.strip():
        return ","
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        return ","


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8", errors="replace")


def guess_text_column(columns: list[str]) -> str:
    for candidate in columns:
        if candidate.strip().lower() in {"review", "reviews", "review_text", "text", "body", "comment", "comments", "feedback"}:
            return candidate
    return columns[0] if columns else ""


def _persist(
    user_id: int,
    filename: str,
    text_column: str,
    scored_rows: list[dict],
    skipped: int,
    counts: dict,
    aspect_summary: dict,
    source: dict,
) -> int:
    now = db.utc_now()
    with db.get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO batches (user_id, filename, text_column, row_count, skipped_count,"
            " positive_count, neutral_count, negative_count, aspect_summary_json, source_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(user_id),
                filename,
                text_column,
                len(scored_rows),
                skipped,
                counts["positive"],
                counts["neutral"],
                counts["negative"],
                json.dumps(aspect_summary),
                json.dumps(source),
                now,
            ),
        )
        batch_id = int(cursor.lastrowid)
        conn.executemany(
            "INSERT INTO batch_rows (batch_id, row_index, review_text, sentiment_label,"
            " sentiment_score, aspects_json) VALUES (?, ?, ?, ?, ?, ?)",
            [
                (
                    batch_id,
                    row["row_index"],
                    row["review_text"],
                    row["label"],
                    row["score"],
                    json.dumps(row["aspects"]),
                )
                for row in scored_rows
            ],
        )
    return batch_id


def list_batches(user_id: int, limit: int = 6) -> list[dict]:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, text_column, row_count, skipped_count, positive_count,"
            " neutral_count, negative_count, created_at FROM batches WHERE user_id = ?"
            " ORDER BY created_at DESC, id DESC LIMIT ?",
            (int(user_id), int(limit)),
        ).fetchall()
    return [
        {
            "id": int(row["id"]),
            "filename": row["filename"],
            "text_column": row["text_column"],
            "row_count": int(row["row_count"]),
            "skipped_count": int(row["skipped_count"]),
            "counts": {
                "positive": int(row["positive_count"]),
                "neutral": int(row["neutral_count"]),
                "negative": int(row["negative_count"]),
            },
            "created_at": row["created_at"],
            "download_url": f"/api/batch/{int(row['id'])}/download",
        }
        for row in rows
    ]


def build_download_csv(user_id: int, batch_id: int) -> tuple[str, str]:
    """Rebuild the uploaded CSV with sentiment + aspect columns appended."""
    with db.get_conn() as conn:
        batch = conn.execute(
            "SELECT filename, source_json FROM batches WHERE id = ? AND user_id = ?",
            (int(batch_id), int(user_id)),
        ).fetchone()
        if batch is None:
            raise LookupError("Batch not found")
        rows = conn.execute(
            "SELECT row_index, sentiment_label, sentiment_score, aspects_json FROM batch_rows"
            " WHERE batch_id = ? ORDER BY row_index",
            (int(batch_id),),
        ).fetchall()

    source = json.loads(batch["source_json"])
    columns: list[str] = list(source.get("columns") or [])
    source_rows: list[list[str]] = source.get("rows") or []
    scored = {int(row["row_index"]): row for row in rows}

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns + list(DERIVED_COLUMNS))
    for index, row in enumerate(source_rows):
        values = [_csv_safe(cell) for cell in row]
        hit = scored.get(index)
        if hit is None:
            values.extend([""] * len(DERIVED_COLUMNS))
        else:
            aspects = json.loads(hit["aspects_json"])
            labels = {item["aspect"]: item["label"] for item in aspects["aspects"]}
            values.extend(
                [
                    hit["sentiment_label"],
                    f"{float(hit['sentiment_score']):.4f}",
                    labels.get("price", "neutral"),
                    labels.get("quality", "neutral"),
                    labels.get("shipping", "neutral"),
                ]
            )
        writer.writerow(values)

    stem = (batch["filename"] or "reviews.csv").rsplit(".csv", 1)[0]
    return f"reviewlens-scored-{stem}.csv", buffer.getvalue()


def _csv_safe(value: object) -> str:
    """Neutralise spreadsheet formula injection in exported text cells."""
    text = "" if value is None else str(value)
    if not text:
        return text
    first = text[0]
    if first in {"=", "+", "@", "\t", "\r"}:
        return "'" + text
    if first == "-" and (len(text) == 1 or not text[1].isdigit()):
        return "'" + text
    return text


def get_batch_rows(user_id: int, batch_id: int) -> list[sqlite3.Row]:
    with db.get_conn() as conn:
        owner = conn.execute(
            "SELECT id FROM batches WHERE id = ? AND user_id = ?", (int(batch_id), int(user_id))
        ).fetchone()
        if owner is None:
            return []
        return conn.execute(
            "SELECT row_index, review_text, sentiment_label, sentiment_score, aspects_json"
            " FROM batch_rows WHERE batch_id = ? ORDER BY row_index",
            (int(batch_id),),
        ).fetchall()
