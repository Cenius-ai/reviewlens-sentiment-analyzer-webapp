"""Sign-in gate, password storage and per-user scoping."""

from __future__ import annotations

import sqlite3

from app import config


def test_landing_page_is_public_html(client):
    """`/` is the public front door: real HTML, no sign-in wall."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    body = response.text
    assert "Reviewlens Sentiment Analyzer" in body
    assert "Score a review right here" in body
    assert "Mixed weekly export" in body  # seeded sample set, server-rendered
    assert "fonts.googleapis.com" not in body


def test_workspace_requires_a_session(client):
    for path in ("/app", "/app/"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"].startswith("/login")


def test_login_page_shows_the_demo_credentials(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert "Demo: cenius@cenius.ai / cenius" in response.text
    assert 'name="username"' in response.text
    assert 'type="password"' in response.text


def test_demo_account_can_sign_in_and_reach_the_workspace(client):
    okay = client.post(
        "/login",
        data={"username": "cenius@cenius.ai", "password": "cenius"},
        follow_redirects=False,
    )
    assert okay.status_code == 303
    assert okay.headers["location"] == "/app/"
    assert config.SESSION_COOKIE in client.cookies

    page = client.get("/app/")
    assert page.status_code == 200
    assert "gradio" in page.text.lower()

    client.get("/logout", follow_redirects=False)
    assert client.get("/app/", follow_redirects=False).status_code == 303


def test_wrong_password_is_rejected_with_one_generic_message(client):
    response = client.post(
        "/login",
        data={"username": "cenius@cenius.ai", "password": "***REDACTED-SECRET***"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "Invalid username or password" in response.text
    assert config.SESSION_COOKIE not in client.cookies


def test_unknown_user_gets_the_same_message(client):
    response = client.post(
        "/login",
        data={"username": "nobody@example.com", "password": "whatever"},
        follow_redirects=False,
    )
    assert response.status_code == 401
    assert "Invalid username or password" in response.text


def test_open_redirect_target_is_rejected(client):
    response = client.post(
        "/login",
        data={"username": "cenius@cenius.ai", "password": "cenius", "next": "//evil.example/x"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/app/"


def test_passwords_are_salted_hashes_not_plaintext():
    conn = sqlite3.connect(f"{config.data_dir()}/app.db")
    try:
        rows = conn.execute("SELECT username, password_hash, salt FROM users").fetchall()
    finally:
        conn.close()
    assert rows
    for username, password_hash, salt in rows:
        assert password_hash != "cenius"
        assert len(password_hash) == 64  # hex pbkdf2-sha256 digest
        assert len(salt) == 32
        assert username not in password_hash


def test_api_requires_credentials(client):
    """Every /api route except /api/health is HTTP Basic gated."""
    assert client.post("/api/analyze", json={"text": "great"}).status_code == 401
    assert client.get("/api/samples").status_code == 401
    assert client.get("/api/samples/1").status_code == 401
    assert client.get("/api/history").status_code == 401
    assert client.get("/api/batch/1/download").status_code == 401
    assert client.post("/api/batch").status_code == 401
    unauthorised = client.get("/api/history")
    assert unauthorised.headers["www-authenticate"].startswith("Basic")
    # the demo helpers are page support, not API surface
    assert client.get("/api/demo/samples").status_code == 404


def test_api_health_is_public(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_public_page_endpoints_are_open_but_stateless(client):
    """The landing page helpers live outside /api and never touch user rows."""
    samples = client.get("/demo/samples")
    assert samples.status_code == 200
    assert len(samples.json()["samples"]) == 3

    scored = client.post("/demo/analyze", json={"text": "Cheap price but the quality is awful"})
    assert scored.status_code == 200
    payload = scored.json()
    assert payload["label"] == "negative"
    assert payload["id"] is None  # nothing persisted

    empty = client.post("/demo/analyze", json={"text": "  "})
    assert empty.status_code == 422
    assert empty.json()["detail"] == "Paste a review to analyze"


def test_security_headers_are_present(client):
    response = client.get("/api/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_history_is_scoped_per_user(client, demo_auth, shop2_auth):
    client.post("/api/analyze", json={"text": "Great value and quick delivery."}, auth=demo_auth)

    demo_history = client.get("/api/history", auth=demo_auth).json()["analyses"]
    shop2_history = client.get("/api/history", auth=shop2_auth).json()["analyses"]

    assert demo_history, "the demo account should have analyses"
    assert shop2_history == []
