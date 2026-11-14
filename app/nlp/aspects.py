"""Aspect extraction for the three buckets shops care about.

A review is split into clauses (sentences, and clauses joined by "but"/"and"/...),
each clause is assigned to price / quality / shipping by keyword cues, and the
aspect label is derived *only* from the sentiment of the clauses that matched.
That keeps "cheap price but awful quality" honest: two different verdicts.
"""

from __future__ import annotations

import re

from .lexicon import Lexicon
from .sentiment import NEUTRAL, label_for, normalize, score_text

ASPECTS = ("price", "quality", "shipping")

ASPECT_LABELS = {
    "price": "Price",
    "quality": "Quality",
    "shipping": "Shipping",
}

CLAUSE_SPLIT_RE = re.compile(
    r"(?<=[.!?;])\s+|,\s*|\s+(?:but|though|although|however|yet|whereas|while|and|because|since|plus)\s+",
    re.IGNORECASE,
)

ASPECT_PATTERNS: dict[str, re.Pattern[str]] = {
    "price": re.compile(
        r"\b(price|prices|priced|pricing|cost|costs|costly|expensive|cheap|cheaper|"
        r"cheapest|value|affordable|bargain|overpriced|worth|money|dollars|euros|"
        r"budget|discount|deal|deals|sale|refund|invoice|paid|payment|pay)\b",
        re.IGNORECASE,
    ),
    "quality": re.compile(
        r"\b(quality|material|materials|build|built|construction|craftsmanship|"
        r"durable|durability|sturdy|flimsy|fabric|stitching|finish|finished|"
        r"workmanship|manufacturing|made|making|fittings|hardware)\b",
        re.IGNORECASE,
    ),
    "shipping": re.compile(
        r"\b(shipping|shipped|shipment|delivery|delivered|deliver|arrived|arrive|"
        r"arriving|package|packaging|parcel|courier|postage|dispatch|dispatched|"
        r"tracking|transit|carrier|mailbox|mail)\b",
        re.IGNORECASE,
    ),
}

# When a clause names an aspect but carries no lexicon sentiment at all, these
# domain cues decide the polarity (e.g. "shipping took three weeks" is slow).
FALLBACK_CUES: dict[str, list[tuple[re.Pattern[str], float]]] = {
    "shipping": [
        (
            re.compile(
                r"\b(?:took|takes|take|waited|wait|waits|sat|sits)\b[^.]{0,30}?"
                r"\b(?:\d+|two|three|four|five|six|seven|several|a few|many)\s+"
                r"(?:days|weeks|months)\b",
                re.IGNORECASE,
            ),
            -0.6,
        ),
        (re.compile(r"\b(?:still|never)\s+(?:waiting|arrived|delivered|shipped|came)\b", re.IGNORECASE), -0.65),
        (re.compile(r"\bno\s+(?:tracking|update|updates|word)\b", re.IGNORECASE), -0.55),
        (re.compile(r"\b(?:crushed|soaked|unsafe packaging)\b", re.IGNORECASE), -0.55),
    ],
    "price": [
        (re.compile(r"\b(?:too|very|quite|kind of|a bit)\s+(?:expensive|pricey|dear)\b", re.IGNORECASE), -0.6),
        (re.compile(r"\bworth\s+(?:every|the)\b", re.IGNORECASE), 0.6),
        (re.compile(r"\brip[\s-]?off\b", re.IGNORECASE), -0.75),
        (re.compile(r"\bsave[sd]?\b[^.]{0,20}\b(?:money|dollars)\b", re.IGNORECASE), 0.45),
    ],
    "quality": [
        (re.compile(r"\bfell\s+apart\b", re.IGNORECASE), -0.8),
        (re.compile(r"\bcheap(?:ly)?\s+(?:made|plastic|materials?)\b", re.IGNORECASE), -0.6),
        (re.compile(r"\b(?:held|holds)\s+up\b", re.IGNORECASE), 0.5),
    ],
}

MAX_EXCERPT_CHARS = 180
MAX_EXCERPTS = 3
ASPECT_LABEL_THRESHOLD = 0.08


def split_clauses(text: str) -> list[str]:
    clauses = [clause.strip(" \t,;:-") for clause in CLAUSE_SPLIT_RE.split(text or "")]
    return [clause for clause in clauses if clause]


def _matched_aspects(clause: str) -> list[str]:
    return [aspect for aspect in ASPECTS if ASPECT_PATTERNS[aspect].search(clause)]


def _clause_sentiment(clause: str, lexicon: Lexicon | None) -> tuple[float, list[dict]]:
    """Sentiment of one clause as a raw valence plus the words that fired."""
    result = score_text(clause, lexicon)
    if result.fired:
        return result.raw, result.fired
    return 0.0, []


def _fallback_cue(aspect: str, clause: str) -> float:
    for pattern, value in FALLBACK_CUES[aspect]:
        if pattern.search(clause):
            return value
    return 0.0


def _excerpt(clause: str) -> str:
    text = " ".join(clause.split())
    if len(text) > MAX_EXCERPT_CHARS:
        text = text[: MAX_EXCERPT_CHARS - 1].rstrip() + "…"
    return text


def extract_aspects(text: str, lexicon: Lexicon | None = None) -> dict:
    """Return per-aspect mentions, labels, scores and supporting excerpts."""
    buckets: dict[str, dict] = {
        aspect: {"aspect": aspect, "mentions": 0, "raw": 0.0, "excerpts": []}
        for aspect in ASPECTS
    }

    for clause in split_clauses(text):
        matched = _matched_aspects(clause)
        if not matched:
            continue
        raw, _fired = _clause_sentiment(clause, lexicon)
        for aspect in matched:
            bucket = buckets[aspect]
            if raw == 0.0:
                raw = _fallback_cue(aspect, clause)
            bucket["mentions"] += 1
            bucket["raw"] += raw
            if len(bucket["excerpts"]) < MAX_EXCERPTS:
                bucket["excerpts"].append(_excerpt(clause))

    aspects = []
    for aspect in ASPECTS:
        bucket = buckets[aspect]
        mentions = bucket["mentions"]
        mean_raw = bucket["raw"] / mentions if mentions else 0.0
        score = round(normalize(mean_raw), 4)
        label = label_for(score, ASPECT_LABEL_THRESHOLD) if mentions else NEUTRAL
        aspects.append(
            {
                "aspect": aspect,
                "label": label,
                "score": score,
                "mentions": mentions,
                "excerpts": bucket["excerpts"],
            }
        )

    return {
        "has_aspects": any(item["mentions"] for item in aspects),
        "aspects": aspects,
    }
