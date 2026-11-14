"""Read-only access to the seeded sample review sets."""

from __future__ import annotations

import json
import sqlite3

from .. import db


def list_sets() -> list[dict]:
    with db.get_conn() as conn:
        rows = conn.execute(
            "SELECT id, slug, name, description, reviews_json FROM sample_sets ORDER BY id"
        ).fetchall()
    return [_as_summary(row) for row in rows]


def get_set(sample_id: int) -> dict | None:
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, slug, name, description, reviews_json FROM sample_sets WHERE id = ?",
            (int(sample_id),),
        ).fetchone()
    if row is None:
        return None
    summary = _as_summary(row)
    summary["reviews"] = json.loads(row["reviews_json"])
    return summary


def _as_summary(row: sqlite3.Row) -> dict:
    reviews = json.loads(row["reviews_json"])
    return {
        "id": int(row["id"]),
        "slug": row["slug"],
        "name": row["name"],
        "description": row["description"],
        "review_count": len(reviews),
    }
