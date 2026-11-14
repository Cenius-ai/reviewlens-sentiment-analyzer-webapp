# Install and run

Reviewlens is a single Python service with no external services. It needs **Python 3.11+**
and **pip** — nothing else. There is no database server, no Node toolchain, no API key.

The package manager for this project is **pip** (dependencies are pinned in
`requirements.txt`). Do not mix in conda/poetry; the pinned versions assume pip.

## 1. Install dependencies and seed the demo data

```bash
sh install.sh
```

That runs, in order:

1. `python3 -m pip install --upgrade pip setuptools wheel`
2. `python3 -m pip install -r requirements.txt` (gradio, pandas, python-multipart, httpx, pytest)
3. `python3 -m app.seed` — creates `data/app.db`, the two demo accounts, the three sample
   review sets, six seeded analyses and one scored batch
4. `python3 -c "import app.main"` — import self-check so a broken install fails here, not at boot

The script exits when it is done. **It never starts the server.**

<details>
<summary>Manual equivalent (no script)</summary>

```bash
python3 -m pip install -r requirements.txt
python3 -m app.seed
```
</details>

## 2. Run the app

```bash
python3 app.py
```

It binds `0.0.0.0` on `$PORT` (default `7860`) and prints
`Reviewlens listening on http://0.0.0.0:7860`. Open <http://localhost:7860> for the public
overview, then **Open the analyzer** and sign in with `cenius@cenius.ai` / `cenius`.
The public page lives at `/`, the signed-in workspace at `/app/`.

Equivalent start commands: `python3 -m app.main` or
`uvicorn app.main:app --host 0.0.0.0 --port 7860`.

The schema and demo data are also created on this boot path, so a bare start on a fresh
clone works even if you skipped step 1's seed (dependencies still have to be installed).

## 3. Verify

```bash
curl -s localhost:7860/api/health        # {"status": "ok", ...}
curl -s -o /dev/null -w '%{http_code} %{content_type}\n' localhost:7860/   # 200 text/html
python3 -m pytest -q                     # 37 tests, no network needed
```

## Configuration

No `.env` file is required; every value has a working default (see `.env.example`).

| Variable | Default | Purpose |
| --- | --- | --- |
| `PORT` | `7860` | HTTP port, bound on `0.0.0.0`. |
| `REVIEWLENS_DATA_DIR` | `./data` | Data directory (SQLite file + generated session secret). |
| `REVIEWLENS_DB_PATH` | `data/app.db` | Explicit SQLite file path. |
| `REVIEWLENS_SESSION_HOURS` | `12` | Session cookie lifetime in hours. |
| `SESSION_SECRET` | generated into `data/.session_secret` | Cookie signing key. Set it explicitly when running more than one instance behind a load balancer. |
| `REVIEWLENS_LOG_LEVEL` | `INFO` | Python log level. |

## Troubleshooting

- **`externally-managed-environment` from pip** — install.sh retries with
  `--break-system-packages`. Preferred: create a virtualenv first
  (`python3 -m venv .venv && . .venv/bin/activate`) and re-run `sh install.sh`.
- **Port already in use** — `PORT=7870 python3 app.py`.
- **Forgot the demo password** — the seed is idempotent; `python3 -m app.seed` recreates
  any missing account without duplicating data.
- **Start over** — stop the server, delete `data/`, then `python3 -m app.seed` (or just
  start the app again).
