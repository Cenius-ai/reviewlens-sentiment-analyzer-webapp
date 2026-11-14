"""Single-review analysis: validate, score, extract aspects, persist."""

from __future__ import annotations

import json

from .. import config, db
from ..nlp import extract_aspects, get_lexicon, score_text

MAX_REVIEW_CHARS = config.MAX_REVIEW_CHARS


class ReviewValidationError(ValueError):
    """A review that cannot be scored, with a message fit for the UI."""


def validate_review_text(text: str | None) -> str:
    cleaned = (text or "").strip()
    if not cleaned:
        raise ReviewValidationError("Paste a review to analyze")
    if len(cleaned) > MAX_REVIEW_CHARS:
        raise ReviewValidationError(f"Review is too long ({MAX_REVIEW_CHARS:,} characters max)")
    return cleaned


def analyze_review(
    user_id: int,
    text: str | None,
    persist: bool = True,
    created_at: str | None = None,
) -> dict:
    """Score one review and (by default) save it to the user's history."""
    cleaned = validate_review_text(text)
    lexicon = get_lexicon()
    sentiment = score_text(cleaned, lexicon)
    aspects = extract_aspects(cleaned, lexicon)

    result = {
        "review_text": cleaned,
        "label": sentiment.label,
        "score": sentiment.score,
        "fired": sentiment.fired,
        "aspects": aspects,
        "created_at": created_at or db.utc_now(),
        "id": None,
    }
    if persist:
        result["id"] = _save(user_id, result)
    return result


def _save(user_id: int, result: dict) -> int:
    with db.get_conn() as conn:
        cursor = conn.execute(
            "INSERT INTO analyses (user_id, review_text, sentiment_label, sentiment_score,"
            " fired_words_json, aspects_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                int(user_id),
                result["review_text"],
                result["label"],
                result["score"],
                json.dumps(result["fired"]),
                json.dumps(result["aspects"]),
                result["created_at"],
            ),
        )
        return int(cursor.lastrowid)
