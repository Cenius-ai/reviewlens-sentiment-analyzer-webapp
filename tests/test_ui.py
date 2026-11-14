"""UI contract checks that do not need a browser: the shell, the config and the
lexicon that the whole product depends on."""

from __future__ import annotations

import json

from app import config
from app.nlp import get_lexicon


def test_signed_in_root_serves_the_gradio_shell(client):
    client.post("/login", data={"username": "cenius", "password": "cenius"})
    page = client.get("/")
    assert page.status_code == 200
    assert "Reviewlens Sentiment Analyzer" in page.text
    # the offline rule: the delivered page must not pull assets from a CDN
    assert "cdnjs.cloudflare.com" not in page.text
    assert "fonts.googleapis.com" not in page.text


def test_gradio_config_exposes_the_four_tabs(client):
    client.post("/login", data={"username": "cenius", "password": "cenius"})
    payload = client.get("/app/config").json()
    blob = json.dumps(payload)
    for label in ("Analyze", "Batch CSV", "Samples", "History"):
        assert label in blob
    assert "Paste a review and press Analyze" in blob


def test_assets_are_served_from_this_origin(client):
    stylesheet = client.get("/site-assets/app.css")
    assert stylesheet.status_code == 200
    assert "text/css" in stylesheet.headers["content-type"]

    font = client.get("/site-assets/fonts/atkinson-400.woff2")
    assert font.status_code == 200

    favicon = client.get("/site-assets/favicon.svg")
    assert favicon.status_code == 200


def test_lexicon_ships_with_the_repo():
    lexicon = get_lexicon()
    assert lexicon.size >= 200
    assert "love" in lexicon.words and lexicon.words["love"] > 0
    assert "terrible" in lexicon.words and lexicon.words["terrible"] < 0
    assert "not" in lexicon.negators
    assert not any(word in lexicon.words for word in ("price", "quality", "shipping"))


def test_sample_sets_file_matches_the_seed():
    payload = json.loads(config.data_file("sample_sets.json").read_text(encoding="utf-8"))
    assert len(payload["sets"]) == 3
    for entry in payload["sets"]:
        assert 8 <= len(entry["reviews"]) <= 12
