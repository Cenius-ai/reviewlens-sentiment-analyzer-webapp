"""Password hashing, session cookies and request authentication.

Passwords are stored as salted PBKDF2-SHA256 hashes (never plaintext). Sessions
are signed with an HMAC over ``user_id:expiry`` using the per-install secret from
:mod:`app.config`, so the cookie survives restarts and reloads.
"""

from __future__ import annotations

import base64
import binascii
import hmac
import logging
import sqlite3
import time
from hashlib import pbkdf2_hmac, sha256
from typing import Any

from . import config, db

logger = logging.getLogger(__name__)

PBKDF2_ITERATIONS = 260_000
HASH_ALGORITHM = "pbkdf2_sha256"


class AuthError(Exception):
    """Raised when credentials or a session token cannot be trusted."""


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Return ``(hash_hex, salt_hex)`` for a plaintext password."""
    salt = bytes.fromhex(salt_hex) if salt_hex else bytes.fromhex(_random_hex(16))
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return digest.hex(), salt.hex()


def _random_hex(n_bytes: int) -> str:
    import secrets

    return secrets.token_hex(n_bytes)


def verify_password(password: str, password_hash: str, salt_hex: str) -> bool:
    """Constant-time password check against a stored PBKDF2 hash."""
    try:
        salt = bytes.fromhex(salt_hex)
    except (ValueError, binascii.Error):
        return False
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest.hex(), password_hash)


def create_user(username: str, email: str, password: str, role: str = "owner") -> int:
    """Insert a user with a fresh salt; idempotent on unique conflicts."""
    password_hash, salt = hash_password(password)
    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE username = ? OR email = ?",
            (username, email),
        ).fetchone()
        if existing:
            return int(existing["id"])
        cur = conn.execute(
            "INSERT INTO users (username, email, password_hash, salt, role, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (username, email, password_hash, salt, role, db.utc_now()),
        )
        return int(cur.lastrowid)


def get_user_by_id(user_id: int) -> sqlite3.Row | None:
    with db.get_conn() as conn:
        return conn.execute(
            "SELECT id, username, email, role, created_at FROM users WHERE id = ?",
            (int(user_id),),
        ).fetchone()


def authenticate(identifier: str, password: str) -> sqlite3.Row | None:
    """Look a user up by username *or* email and verify the password.

    Returns ``None`` for any failure - callers must show one generic message so
    the response never reveals whether the account exists.
    """
    identifier = (identifier or "").strip()
    if not identifier or not password:
        return None
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id, username, email, role, password_hash, salt FROM users"
            " WHERE lower(username) = lower(?) OR lower(email) = lower(?)",
            (identifier, identifier),
        ).fetchone()
    if row is None:
        # Spend comparable time so a missing account is not distinguishable.
        verify_password(password, "0" * 64, "0" * 32)
        return None
    if not verify_password(password, row["password_hash"], row["salt"]):
        return None
    return row


def _sign(payload: str) -> str:
    digest = hmac.new(config.session_secret(), payload.encode("utf-8"), sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def create_session_token(user_id: int) -> str:
    expires = int(time.time()) + config.session_hours() * 3600
    payload = f"{int(user_id)}:{expires}"
    return f"{payload}:{_sign(payload)}"


def read_session_token(token: str | None) -> int | None:
    """Verify a session token and return its user id, or ``None``."""
    if not token:
        return None
    parts = token.split(":")
    if len(parts) != 3:
        return None
    user_id_raw, expires_raw, signature = parts
    payload = f"{user_id_raw}:{expires_raw}"
    if not hmac.compare_digest(_sign(payload), signature):
        return None
    try:
        user_id = int(user_id_raw)
        expires = int(expires_raw)
    except ValueError:
        return None
    if expires < int(time.time()):
        return None
    return user_id


def user_from_cookies(cookies: Any) -> sqlite3.Row | None:
    """Resolve the signed-in user from a cookie mapping (dict/Cookies/Obj)."""
    token = _cookie_value(cookies, config.SESSION_COOKIE)
    user_id = read_session_token(token)
    if user_id is None:
        return None
    return get_user_by_id(user_id)


def _cookie_value(cookies: Any, name: str) -> str | None:
    if not cookies:
        return None
    try:
        value = dict(cookies).get(name)
    except (TypeError, ValueError):
        value = None
    return value if isinstance(value, str) else None


def user_from_basic_auth(header: str | None) -> sqlite3.Row | None:
    """Resolve a user from an HTTP ``Authorization: Basic`` header."""
    if not header or not header.lower().startswith("basic "):
        return None
    try:
        decoded = base64.b64decode(header.split(" ", 1)[1].strip()).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError):
        return None
    if ":" not in decoded:
        return None
    identifier, password = decoded.split(":", 1)
    return authenticate(identifier, password)


def user_from_request(cookies: Any = None, authorization: str | None = None) -> sqlite3.Row | None:
    """One credential store, two front doors.

    An explicit ``Authorization`` header wins, so a scripted client always acts as
    the identity it names even if a browser cookie happens to be present.
    """
    return user_from_basic_auth(authorization) or user_from_cookies(cookies)
