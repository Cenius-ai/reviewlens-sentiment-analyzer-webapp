"""SQLite access layer.

One connection per unit of work (FastAPI and Gradio both call us from worker
threads, so a shared connection would be a footgun). Rows come back as
``sqlite3.Row`` so they support both index and name access.
"""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Iterator
from datetime import datetime, timezone

from . import config

SCHEMA_PATH = config.PACKAGE_DIR / "schema.sql"


def utc_now() -> str:
    """UTC timestamp in the ISO-8601 form stored throughout the schema."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def connect() -> sqlite3.Connection:
    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=20, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextlib.contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    """Transactional connection: commit on success, roll back on error."""
    conn = connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def create_schema() -> None:
    config.ensure_dirs()
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def init_db(seed: bool = True) -> None:
    """Create the schema and idempotently seed demo data.

    Called from the normal boot path (``app.main``), so a bare ``python -m
    app.main`` on a fresh clone always lands on a populated app.
    """
    create_schema()
    if seed:
        from . import seed as seed_module

        seed_module.seed_all()
