"""Deterministic lexicon sentiment scoring with negation and intensifiers.

Every point of the score is traceable to a lexicon word that fired, which is what
the UI shows and what makes the product explainable without a model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .lexicon import Lexicon, get_lexicon

TOKEN_RE = re.compile(r"[a-z']+")
NEGATION_WINDOW = 3
# Squashing constant: a long review cannot saturate the scale, and a single
# strong word still lands clearly on the positive/negative side of zero.
SCORE_DIVISOR = 2.0
LABEL_THRESHOLD = 0.15

POSITIVE = "positive"
NEUTRAL = "neutral"
NEGATIVE = "negative"


@dataclass
class SentimentResult:
    label: str
    score: float
    fired: list[dict] = field(default_factory=list)
    token_count: int = 0
    raw: float = 0.0

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "score": self.score,
            "fired": self.fired,
            "token_count": self.token_count,
        }


def tokenize(text: str) -> list[str]:
    return TOKEN_RE.findall((text or "").lower())


def normalize(raw: float) -> float:
    """Map an unbounded raw valence into (-1, 1)."""
    if raw == 0:
        return 0.0
    return raw / (abs(raw) + SCORE_DIVISOR)


def label_for(score: float, threshold: float = LABEL_THRESHOLD) -> str:
    if score > threshold:
        return POSITIVE
    if score < -threshold:
        return NEGATIVE
    return NEUTRAL


def score_text(text: str, lexicon: Lexicon | None = None) -> SentimentResult:
    """Score a chunk of text. Empty input scores neutral, never raises."""
    lex = lexicon or get_lexicon()
    tokens = tokenize(text)
    fired: list[dict] = []
    raw = 0.0

    for index, token in enumerate(tokens):
        base = lex.words.get(token)
        if base is None:
            continue

        multiplier = 1.0
        negated = False
        intensifier = None
        for back in range(1, NEGATION_WINDOW + 1):
            prev_index = index - back
            if prev_index < 0:
                break
            previous = tokens[prev_index]
            if previous in lex.negators:
                negated = True
                break
            if previous in lex.intensifiers and intensifier is None:
                intensifier = previous
                multiplier *= lex.intensifiers[previous]

        value = base * multiplier
        if negated:
            value = -value * lex.negation_factor

        fired.append(
            {
                "word": token,
                "value": round(value, 4),
                "negated": negated,
                "intensifier": intensifier,
            }
        )
        raw += value

    score = round(normalize(raw), 4)
    return SentimentResult(
        label=label_for(score),
        score=score,
        fired=fired,
        token_count=len(tokens),
        raw=round(raw, 4),
    )
