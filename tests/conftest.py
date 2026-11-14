"""Shared fixtures. The env var is set before any app module is imported so the
test run gets its own SQLite file and never touches the developer's data/."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Make the repo root importable whatever invoked us (`pytest`, `python -m pytest`,
# an IDE runner): the suite imports the `app` package, which lives one level up.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

TEST_DATA_DIR = tempfile.mkdtemp(prefix="reviewlens-tests-")
os.environ["REVIEWLENS_DATA_DIR"] = TEST_DATA_DIR
os.environ["SESSION_SECRET"] = "test-only-secret-not-used-anywhere-else"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services import sample_service  # noqa: E402


@pytest.fixture()
def client() -> TestClient:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def demo_auth() -> tuple[str, str]:
    """HTTP Basic credentials for the seeded demo account."""
    return ("cenius@cenius.ai", "cenius")


@pytest.fixture()
def shop2_auth() -> tuple[str, str]:
    return ("shop2@reviewlens.dev", "shop2")


@pytest.fixture()
def sample_csv() -> bytes:
    rows = ["order_id,review,rating"]
    reviews = [
        "Absolutely love it, great quality and fast delivery.",
        "Terrible. It broke in a week and support ignored me.",
        "",
        "Cheap price but the quality is awful and shipping took three weeks.",
        "Shipping was very slow and the packaging arrived damaged.",
        "Great value, worth every penny. Arrived in two days.",
        "",
        "The colour is nice but the material feels thin for the price.",
        "Excellent quality, sturdy build and prompt delivery.",
        "Overpriced for what you get. The finish is mediocre.",
    ]
    for index, review in enumerate(reviews, start=1):
        escaped = review.replace('"', '""')
        rows.append(f'A-{1000 + index},"{escaped}",{(index % 5) + 1}')
    return ("\n".join(rows) + "\n").encode("utf-8")


@pytest.fixture()
def first_sample_set_id() -> int:
    sets = sample_service.list_sets()
    assert sets, "seed data should always provide sample sets"
    return int(sets[0]["id"])
