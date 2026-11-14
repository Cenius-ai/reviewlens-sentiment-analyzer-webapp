"""The offline scorer and the aspect extractor - the product's core logic."""

from __future__ import annotations

from app.nlp import extract_aspects, score_text, split_clauses
from app.services.analyze_service import ReviewValidationError, validate_review_text


def test_positive_review_scores_positive_with_expected_words():
    result = score_text("Absolutely love it, great quality and fast delivery")
    assert result.label == "positive"
    assert result.score > 0.3
    fired = [item["word"] for item in result.fired]
    assert "love" in fired
    assert "great" in fired


def test_negative_review_scores_negative():
    result = score_text("Terrible. It broke in a week and support ignored me.")
    assert result.label == "negative"
    assert result.score < -0.3


def test_negation_flips_the_hit():
    plain = score_text("good")
    negated = score_text("not good at all")
    assert plain.label == "positive"
    assert negated.label == "negative"
    assert negated.score < 0 < plain.score
    assert negated.fired[0]["negated"] is True


def test_empty_text_is_neutral_and_never_raises():
    result = score_text("")
    assert result.label == "neutral"
    assert result.score == 0
    assert result.fired == []


def test_scoring_is_deterministic():
    text = "Fast delivery but the packaging was damaged and the price was high."
    assert score_text(text).as_dict() == score_text(text).as_dict()


def test_aspects_split_price_quality_and_shipping():
    review = "Cheap price but the quality is awful and shipping took three weeks"
    assert len(split_clauses(review)) == 3
    extracted = extract_aspects(review)
    by_aspect = {item["aspect"]: item for item in extracted["aspects"]}

    assert extracted["has_aspects"] is True
    assert by_aspect["price"]["label"] == "positive"
    assert by_aspect["quality"]["label"] == "negative"
    assert by_aspect["shipping"]["label"] == "negative"
    for aspect in ("price", "quality", "shipping"):
        assert by_aspect[aspect]["mentions"] == 1
        assert by_aspect[aspect]["excerpts"], f"{aspect} should carry an excerpt"


def test_aspects_absent_reports_no_aspects():
    extracted = extract_aspects("The colour is nice")
    assert extracted["has_aspects"] is False
    assert all(item["mentions"] == 0 for item in extracted["aspects"])
    assert all(item["label"] == "neutral" for item in extracted["aspects"])


def test_validation_rejects_empty_and_overlong_reviews():
    for bad in ("", "   "):
        try:
            validate_review_text(bad)
        except ReviewValidationError as exc:
            assert "Paste a review" in str(exc)
        else:  # pragma: no cover - explicit failure path
            raise AssertionError("empty review should not validate")

    try:
        validate_review_text("x" * 5001)
    except ReviewValidationError as exc:
        assert "too long" in str(exc).lower()
    else:  # pragma: no cover
        raise AssertionError("over-cap review should not validate")
