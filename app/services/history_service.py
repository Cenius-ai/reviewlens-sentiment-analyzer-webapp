"""A user's stored single-review analyses (newest first)."""

from __future__ import annotations

import json
import sqlite3

from .. import db


def _row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": int(row["id"]),
        "review_text": row["review_text"],
        "label": row["sentiment_label"],
        "score": round(float(row["sentiment_score"]), 4),
        "fired": json.loads(row["fired_words_json"]),
        "aspects": json.loads(row["aspects_json"]),
        "created_at": row["created_at"],
    }


def list_analyses(user_id: int, limit: int | None = None) -> list[dict]:
    """Newest-first analyses for one user. Never crosses accounts."""
    query = (
        "SELECT id, review_text, sentiment_label, sentiment_score, fired_words_json,"
        " aspects_json, created_at FROM analyses WHERE user_id = ?"
        " ORDER BY created_at DESC, id DESC"
    )
    params: list[object] = [int(user_id)]
    if limit is not None:
        query += " LIMIT ?"
        params.append(max(1, int(limit)))
    with db.get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def count_analyses(user_id: int) -> int:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM analyses WHERE user_id = ?", (int(user_id),)
        ).fetchone()
    return int(row["n"])


def label_counts(user_id: int) -> dict[str, int]:
    counts = {"positive": 0, "neutral": 0, "negative": 0}
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT sentiment_label, COUNT(*) AS n FROM analyses WHERE user_id = ?"
            " GROUP BY sentiment_label",
            (int(user_id),),
        ).fetchall()
    for row in rows:
        counts[row["sentiment_label"]] = int(row["n"])
    return counts


def clear_analyses(user_id: int) -> int:
    with db.get_conn() as conn:
        cursor = conn.execute("DELETE FROM analyses WHERE user_id = ?", (int(user_id),))
        return int(cursor.rowcount)
