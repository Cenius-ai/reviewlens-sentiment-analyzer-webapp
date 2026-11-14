-- Reviewlens schema. SQLite, created idempotently on every boot.
-- Timestamps are UTC ISO-8601 text; money-like data is not stored here.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT    NOT NULL UNIQUE,
    email         TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    salt          TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'owner' CHECK (role IN ('owner', 'analyst')),
    created_at    TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS analyses (
    id                INTEGER PRIMARY KEY,
    user_id           INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    review_text       TEXT    NOT NULL,
    sentiment_label   TEXT    NOT NULL CHECK (sentiment_label IN ('positive', 'neutral', 'negative')),
    sentiment_score   REAL    NOT NULL CHECK (sentiment_score >= -1.0 AND sentiment_score <= 1.0),
    fired_words_json  TEXT    NOT NULL DEFAULT '[]',
    aspects_json      TEXT    NOT NULL DEFAULT '{}',
    created_at        TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_analyses_user_created ON analyses(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS batches (
    id                  INTEGER PRIMARY KEY,
    user_id             INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename            TEXT    NOT NULL,
    text_column         TEXT    NOT NULL,
    row_count           INTEGER NOT NULL,
    skipped_count       INTEGER NOT NULL DEFAULT 0,
    positive_count      INTEGER NOT NULL DEFAULT 0,
    neutral_count       INTEGER NOT NULL DEFAULT 0,
    negative_count      INTEGER NOT NULL DEFAULT 0,
    aspect_summary_json TEXT    NOT NULL DEFAULT '{}',
    source_json         TEXT    NOT NULL DEFAULT '[]',
    created_at          TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_batches_user_created ON batches(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS batch_rows (
    id              INTEGER PRIMARY KEY,
    batch_id        INTEGER NOT NULL REFERENCES batches(id) ON DELETE CASCADE,
    row_index       INTEGER NOT NULL,
    review_text     TEXT    NOT NULL,
    sentiment_label TEXT    NOT NULL CHECK (sentiment_label IN ('positive', 'neutral', 'negative')),
    sentiment_score REAL    NOT NULL,
    aspects_json    TEXT    NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS ix_batch_rows_batch ON batch_rows(batch_id, row_index);

CREATE TABLE IF NOT EXISTS sample_sets (
    id            INTEGER PRIMARY KEY,
    slug          TEXT    NOT NULL UNIQUE,
    name          TEXT    NOT NULL,
    description   TEXT    NOT NULL,
    reviews_json  TEXT    NOT NULL
);
