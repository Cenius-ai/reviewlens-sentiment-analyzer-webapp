"""The JSON API contract: analyze, samples, batch and history."""

from __future__ import annotations

import csv
import io


def test_analyze_returns_the_full_result_and_persists(client, demo_auth):
    response = client.post(
        "/api/analyze",
        json={"text": "Great quality and fast delivery, worth every penny."},
        auth=demo_auth,
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["label"] == "positive"
    assert -1.0 <= payload["score"] <= 1.0
    assert payload["id"]
    assert any(item["word"] == "great" for item in payload["fired"])
    assert {item["aspect"] for item in payload["aspects"]["aspects"]} == {"price", "quality", "shipping"}

    history = client.get("/api/history", auth=demo_auth).json()["analyses"]
    assert any(item["id"] == payload["id"] for item in history)


def test_analyze_rejects_empty_text_with_a_plain_message(client, demo_auth):
    response = client.post("/api/analyze", json={"text": "   "}, auth=demo_auth)
    assert response.status_code == 422
    assert response.json()["detail"] == "Paste a review to analyze"


def test_analyze_rejects_overlong_text(client, demo_auth):
    response = client.post("/api/analyze", json={"text": "x" * 5001}, auth=demo_auth)
    assert response.status_code == 422
    assert "too long" in response.json()["detail"].lower()


def test_samples_list_and_detail(client, demo_auth, first_sample_set_id):
    listing = client.get("/api/samples", auth=demo_auth)
    assert listing.status_code == 200
    sets = listing.json()["samples"]
    assert len(sets) == 3
    for entry in sets:
        assert entry["name"] and entry["description"]
        assert entry["review_count"] >= 8

    detail = client.get(f"/api/samples/{first_sample_set_id}", auth=demo_auth)
    assert detail.status_code == 200
    assert len(detail.json()["reviews"]) == sets[0]["review_count"]

    missing = client.get("/api/samples/99999", auth=demo_auth)
    assert missing.status_code == 404
    assert missing.json()["detail"] == "Sample set not found"


def test_batch_scores_every_row_and_skips_blanks(client, demo_auth, sample_csv):
    response = client.post(
        "/api/batch",
        files={"file": ("reviews.csv", sample_csv, "text/csv")},
        data={"text_column": "review"},
        auth=demo_auth,
    )
    assert response.status_code == 200
    payload = response.json()

    assert payload["row_count"] == 8
    assert payload["skipped_count"] == 2
    counts = payload["counts"]
    assert counts["positive"] + counts["neutral"] + counts["negative"] == payload["row_count"]
    assert set(payload["aspect_summary"]) == {"price", "quality", "shipping"}
    assert payload["id"]


def test_batch_of_fifty_rows(client, demo_auth):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "review"])
    for index in range(50):
        writer.writerow([index, "Great quality and fast delivery, love it." if index % 2 else "Terrible and broken on arrival."])

    response = client.post(
        "/api/batch",
        files={"file": ("fifty.csv", buffer.getvalue().encode(), "text/csv")},
        data={"text_column": "review"},
        auth=demo_auth,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["row_count"] == 50
    assert sum(payload["counts"].values()) == 50
    assert len(payload["rows"]) == 50


def test_batch_rejects_missing_text_column_by_listing_available_ones(client, demo_auth, sample_csv):
    response = client.post(
        "/api/batch",
        files={"file": ("reviews.csv", sample_csv, "text/csv")},
        data={"text_column": "nope"},
        auth=demo_auth,
    )
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "nope" in detail
    assert "review" in detail and "order_id" in detail


def test_batch_rejects_non_csv_and_over_cap(client, demo_auth):
    not_csv = client.post(
        "/api/batch",
        files={"file": ("reviews.txt", b"hello", "text/plain")},
        data={"text_column": "review"},
        auth=demo_auth,
    )
    assert not_csv.status_code == 422
    assert "not a .csv" in not_csv.json()["detail"]

    big = io.StringIO()
    writer = csv.writer(big)
    writer.writerow(["review"])
    for _ in range(1001):
        writer.writerow(["great quality"])
    too_big = client.post(
        "/api/batch",
        files={"file": ("big.csv", big.getvalue().encode(), "text/csv")},
        data={"text_column": "review"},
        auth=demo_auth,
    )
    assert too_big.status_code == 422
    assert "1,000" in too_big.json()["detail"]


def test_batch_download_appends_sentiment_columns(client, demo_auth, sample_csv):
    created = client.post(
        "/api/batch",
        files={"file": ("reviews.csv", sample_csv, "text/csv")},
        data={"text_column": "review"},
        auth=demo_auth,
    ).json()

    download = client.get(f"/api/batch/{created['id']}/download", auth=demo_auth)
    assert download.status_code == 200
    assert "text/csv" in download.headers["content-type"]
    assert "attachment" in download.headers["content-disposition"]

    rows = list(csv.reader(io.StringIO(download.text)))
    header = rows[0]
    for column in ("sentiment_label", "sentiment_score", "price_label", "quality_label", "shipping_label"):
        assert column in header
    assert "review" in header and "order_id" in header
    assert len(rows) == 11  # header + 10 original rows


def test_batch_download_is_scoped_to_owner(client, demo_auth, shop2_auth, sample_csv):
    created = client.post(
        "/api/batch",
        files={"file": ("scoped.csv", sample_csv, "text/csv")},
        data={"text_column": "review"},
        auth=demo_auth,
    ).json()

    assert client.get(f"/api/batch/{created['id']}/download", auth=demo_auth).status_code == 200
    assert client.get(f"/api/batch/{created['id']}/download", auth=shop2_auth).status_code == 404


def test_history_newest_first_and_limited(client, demo_auth):
    for text in ("First review, good quality.", "Second review, terrible shipping.", "Third review, lovely price."):
        client.post("/api/analyze", json={"text": text}, auth=demo_auth)

    history = client.get("/api/history", auth=demo_auth).json()["analyses"]
    timestamps = [item["created_at"] for item in history]
    assert timestamps == sorted(timestamps, reverse=True)

    limited = client.get("/api/history?limit=1", auth=demo_auth).json()["analyses"]
    assert len(limited) == 1
    for item in history:
        assert {"label", "score", "created_at"} <= set(item)
