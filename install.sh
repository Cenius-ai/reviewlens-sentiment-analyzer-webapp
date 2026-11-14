#!/usr/bin/env bash
# Reviewlens Sentiment Analyzer - install project dependencies and seed the demo data.
#
# Installs project-level Python dependencies only (no system packages, no sudo),
# creates the SQLite schema and seeds the demo accounts + sample data, then exits.
# Start the server separately with: python3 app.py
set -euo pipefail
cd "$(dirname "$0")"

PYTHON="${PYTHON:-python3}"

echo "==> Python: $($PYTHON --version)"
echo "==> Installing project dependencies with pip"
$PYTHON -m pip install --upgrade pip setuptools wheel || echo "    (pip upgrade skipped)"
if ! $PYTHON -m pip install -r requirements.txt; then
  echo "==> Retrying with --break-system-packages (PEP 668 managed environment)"
  $PYTHON -m pip install --break-system-packages -r requirements.txt
fi

echo "==> Creating the SQLite schema and seeding demo data"
$PYTHON -m app.seed

echo "==> Import self-check"
$PYTHON -c "import app.main"

cat <<'MSG'

Setup complete - the server is NOT running yet.
  Start it with:  python3 app.py         (binds 0.0.0.0:7860, honours $PORT)
  Demo account:   cenius@cenius.ai / cenius
  Test suite:     python3 -m pytest -q
MSG
