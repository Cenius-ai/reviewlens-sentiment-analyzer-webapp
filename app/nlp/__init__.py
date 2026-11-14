"""Offline NLP core: a shipped lexicon, a deterministic scorer, aspect cues."""

from .aspects import ASPECTS, extract_aspects, split_clauses
from .lexicon import Lexicon, get_lexicon, load_lexicon
from .sentiment import NEGATIVE, NEUTRAL, POSITIVE, SentimentResult, score_text

__all__ = [
    "ASPECTS",
    "Lexicon",
    "NEGATIVE",
    "NEUTRAL",
    "POSITIVE",
    "SentimentResult",
    "extract_aspects",
    "get_lexicon",
    "load_lexicon",
    "score_text",
    "split_clauses",
]
