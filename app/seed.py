"""Idempotent demo seed: accounts, sample sets, history and one scored batch.

Runs on the normal boot path (see :func:`app.db.init_db`), so a bare
``python -m app.main`` lands on a populated app. Re-running never duplicates
rows: every insert is guarded by a check or an upsert.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from . import auth, config, db
from .services import analyze_service, batch_service, history_service

SAMPLE_SETS_PATH = config.data_file("sample_sets.json")

DEMO_ACCOUNTS = (
    {"username": "cenius", "email": "cenius@cenius.ai", "password": "cenius", "role": "owner"},
    {"username": "shop2", "email": "shop2@reviewlens.dev", "password": "shop2", "role": "analyst"},
)

# Reviews seeded into the demo account's history so the History tab is populated
# on first load. Timestamps are relative to seed time, newest first.
SEEDED_ANALYSES = (
    (2.0, "Absolutely love it, great quality and fast delivery. Already ordered a second one."),
    (30.5, "Shipping took three weeks and the packaging arrived crushed, but the kettle works fine."),
    (52.0, "Terrible. It broke in a week and support ignored me for four days."),
    (77.25, "The tote is roomy and the straps are comfortable. Stitching still looks durable after a month."),
    (101.0, "Not good at all. The zipper jammed on day two and the return process was a hassle."),
    (126.0, "Reasonable price and the finish is gorgeous. Delivery was a couple of days late."),
)


def seed_all() -> None:
    seed_users()
    seed_sample_sets()
    demo_user = _demo_user()
    if demo_user is not None:
        seed_history(int(demo_user["id"]))
        seed_batch(int(demo_user["id"]))


def seed_users() -> None:
    for account in DEMO_ACCOUNTS:
        auth.create_user(
            username=account["username"],
            email=account["email"],
            password=account["password"],
            role=account["role"],
        )


def seed_sample_sets() -> None:
    payload = json.loads(SAMPLE_SETS_PATH.read_text(encoding="utf-8"))
    with db.get_conn() as conn:
        for entry in payload["sets"]:
            conn.execute(
                "INSERT INTO sample_sets (slug, name, description, reviews_json)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(slug) DO UPDATE SET"
                " name = excluded.name,"
                " description = excluded.description,"
                " reviews_json = excluded.reviews_json",
                (
                    entry["slug"],
                    entry["name"],
                    entry["description"],
                    json.dumps(list(entry["reviews"])),
                ),
            )


def seed_history(user_id: int) -> None:
    if history_service.count_analyses(user_id) > 0:
        return
    now = datetime.now(timezone.utc)
    for hours_ago, review in SEEDED_ANALYSES:
        created_at = (now - timedelta(hours=hours_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
        analyze_service.analyze_review(user_id, review, created_at=created_at)


def seed_batch(user_id: int) -> None:
    if batch_service.list_batches(user_id, limit=1):
        return
    csv_text = "\n".join(
        [
            "order_id,review,customer",
            'A-1041,"Absolutely love it, great quality and fast delivery.",Priya S.',
            'A-1042,"Cheap price but the quality is awful and shipping took three weeks.",Marek D.',
            'A-1043,,Jonah T.',
            'A-1044,"Shipping was very slow and the packaging arrived damaged.",Elena R.',
            'A-1045,"Great value, worth every penny, and it arrived in two days.",Tomasz W.',
            'A-1046,"The colour is nice but the material feels thin for the price.",Aisha K.',
            'A-1047,"Not good at all. The zipper jammed on day two.",Ben O.',
            'A-1048,"Excellent quality, sturdy build and the delivery was prompt.",Lucia M.',
            'A-1049,,Noor H.',
            'A-1050,"Overpriced for what you get. The finish is mediocre.",Ravi P.',
            'A-1051,"Arrived late and the packaging was crushed, though the item was fine.",Sofia G.',
        ]
    )
    batch_service.score_csv(user_id, "sample-weekly-export.csv", "review", csv_text.encode("utf-8"))


def main() -> None:
    """``python3 -m app.seed`` - create the schema and seed, then exit."""
    db.create_schema()
    seed_all()
    print("Seeded Reviewlens: demo accounts, 3 sample sets, history and one scored batch.")


def _demo_user():
    with db.get_conn() as conn:
        return conn.execute(
            "SELECT id FROM users WHERE lower(email) = lower(?)", ("cenius@cenius.ai",)
        ).fetchone()


if __name__ == "__main__":
    main()
