"""Lexicon loading.

The lexicon is a JSON file shipped in the repository - no downloads, no model
weights, no NLTK corpora. It is loaded once per process and cached.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .. import config

LEXICON_PATH = config.data_file("lexicon.json")


@dataclass(frozen=True)
class Lexicon:
    words: dict[str, float]
    negators: frozenset[str]
    intensifiers: dict[str, float]
    negation_factor: float
    version: int

    @property
    def size(self) -> int:
        return len(self.words)


def load_lexicon(path: Path | None = None) -> Lexicon:
    source = path or LEXICON_PATH
    raw = json.loads(source.read_text(encoding="utf-8"))
    words = {str(word).lower(): float(value) for word, value in raw["words"].items()}
    return Lexicon(
        words=words,
        negators=frozenset(str(n).lower() for n in raw.get("negators", [])),
        intensifiers={str(k).lower(): float(v) for k, v in raw.get("intensifiers", {}).items()},
        negation_factor=float(raw.get("negation_factor", 0.85)),
        version=int(raw.get("version", 1)),
    )


@lru_cache(maxsize=1)
def get_lexicon() -> Lexicon:
    return load_lexicon()
