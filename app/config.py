"""Runtime configuration for Reviewlens.

Everything here has a working default so the app boots on a fresh clone with no
``.env`` file and no pre-injected environment: the SQLite file lives in
``data/`` under the repo, and the session secret is generated once on first boot
and cached in ``data/.session_secret`` (mode 0600) instead of being hardcoded.
"""

from __future__ import annotations

import os
import secrets
from pathlib import Path

APP_NAME = "Reviewlens Sentiment Analyzer"
APP_SHORT_NAME = "Reviewlens"
APP_TAGLINE = "Lexicon sentiment for product reviews - no API, no model downloads."
APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Read an optional .env next to the manifest (real env vars always win)."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and key not in os.environ:
            os.environ[key] = value


_load_dotenv()
PACKAGE_DIR = BASE_DIR / "app"
DATA_DIR_NAME = "data"

SESSION_COOKIE = "reviewlens_session"
DEFAULT_SESSION_HOURS = 12
DEFAULT_PORT = 7860
HOST = "0.0.0.0"

MAX_REVIEW_CHARS = 5000
MAX_BATCH_ROWS = 1000


def _resolve(value: str) -> Path:
    """Relative overrides resolve against the repo root, never the shell's cwd."""
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else (BASE_DIR / candidate)


def data_dir() -> Path:
    """Directory that holds the SQLite file, the secret and CSV exports."""
    override = os.getenv("REVIEWLENS_DATA_DIR", "").strip()
    return _resolve(override) if override else BASE_DIR / DATA_DIR_NAME


def db_path() -> Path:
    """Path of the single SQLite file backing the app."""
    override = os.getenv("REVIEWLENS_DB_PATH", "").strip()
    return _resolve(override) if override else data_dir() / "app.db"


def port() -> int:
    raw = os.getenv("PORT", "").strip()
    if raw.isdigit():
        return int(raw)
    return DEFAULT_PORT


def session_hours() -> int:
    raw = os.getenv("REVIEWLENS_SESSION_HOURS", "").strip()
    if raw.isdigit() and int(raw) > 0:
        return int(raw)
    return DEFAULT_SESSION_HOURS


def session_secret() -> bytes:
    """Signing key for the session cookie.

    Read from ``SESSION_SECRET`` when provided; otherwise a random secret is
    generated once and cached next to the database so sessions survive restarts
    and no signing key is ever committed to the repository.
    """
    from_env = os.getenv("SESSION_SECRET", "").strip()
    if from_env:
        return from_env.encode("utf-8")

    secret_file = data_dir() / ".session_secret"
    if secret_file.exists():
        cached = secret_file.read_text(encoding="utf-8").strip()
        if cached:
            return cached.encode("utf-8")

    secret_file.parent.mkdir(parents=True, exist_ok=True)
    generated = secrets.token_hex(32)
    secret_file.write_text(generated, encoding="utf-8")
    try:
        secret_file.chmod(0o600)
    except OSError:
        pass
    return generated.encode("utf-8")


def ensure_dirs() -> None:
    data_dir().mkdir(parents=True, exist_ok=True)


def data_file(name: str) -> Path:
    """A read-only data file shipped inside the package (lexicon, sample sets)."""
    return PACKAGE_DIR / "data" / name


def static_dir() -> Path:
    return PACKAGE_DIR / "static"
