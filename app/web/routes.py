"""Server-rendered sign-in page and sign-out route.

Gradio's JSON endpoints sit behind the same cookie, so one credential store
covers the whole app; ``/api`` additionally accepts HTTP Basic.
"""

from __future__ import annotations

import html
import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .. import auth, config

logger = logging.getLogger(__name__)

router = APIRouter()

DEMO_HINT = "Demo: cenius@cenius.ai / cenius"


WORKSPACE_PATH = "/app/"


def safe_next(value: str | None) -> str:
    """Only allow local redirect targets (no protocol-relative or absolute URLs)."""
    if not value:
        return WORKSPACE_PATH
    candidate = value.strip()
    if not candidate.startswith("/") or candidate.startswith("//"):
        return WORKSPACE_PATH
    if "\\" in candidate or "\n" in candidate or "\r" in candidate:
        return WORKSPACE_PATH
    return candidate


def render_login_page(next_path: str = "", error: str | None = None, username: str = "") -> str:
    error_html = f'<div class="rl-error" role="alert">{html.escape(error)}</div>' if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>Sign in · Reviewlens Sentiment Analyzer</title>
<meta name="description" content="Reviewlens scores product reviews with an offline lexicon - no API keys, no model downloads.">
<link rel="icon" type="image/svg+xml" href="/site-assets/favicon.svg">
<link rel="stylesheet" href="/site-assets/app.css">
</head>
<body>
<main class="rl-login-wrap">
  <section class="rl-login-brand">
    <span class="rl-section-label">Reviewlens</span>
    <h1 class="rl-login-title">Review sentiment for small shops, without an API bill.</h1>
    <p class="rl-login-lede">
      Paste a review, score a whole CSV export, and see exactly which words drove
      each verdict. Everything runs on this machine against a lexicon that ships
      in the repo.
    </p>
    <ul class="rl-login-points">
      <li><span class="rl-dot" aria-hidden="true">01</span>
        <span><b>Single review scoring</b>
        <span>Label, -1 to 1 score and the lexicon words that fired - negations included.</span></span></li>
      <li><span class="rl-dot" aria-hidden="true">02</span>
        <span><b>Price / quality / shipping</b>
        <span>Aspect verdicts derived only from the clauses that mention them.</span></span></li>
      <li><span class="rl-dot" aria-hidden="true">03</span>
        <span><b>Batch CSV + history</b>
        <span>Score up to 1,000 rows, chart the split, download the scored file.</span></span></li>
    </ul>
    <p class="rl-note">Offline by design: no outbound network calls, no API keys, one SQLite file.</p>
  </section>

  <section class="rl-login-card">
    <h2 class="rl-h1">Sign in</h2>
    <p class="rl-note" style="margin-bottom:16px">One account per shop. Your history and batches stay scoped to you.</p>
    {error_html}
    <form method="post" action="/login" novalidate>
      <input type="hidden" name="next" value="{html.escape(next_path or WORKSPACE_PATH, quote=True)}">
      <div class="rl-field">
        <label for="rl-username">Email or username</label>
        <div class="rl-input-row">
          <input id="rl-username" name="username" type="text" value="{html.escape(username, quote=True)}"
                 autocomplete="username" autocapitalize="none" spellcheck="false"
                 placeholder="you@shop.example" required autofocus>
        </div>
      </div>
      <div class="rl-field">
        <label for="rl-password">Password</label>
        <div class="rl-input-row">
          <input id="rl-password" name="password" type="password" autocomplete="current-password"
                 placeholder="Your password" required>
          <button class="rl-toggle" type="button" id="rl-toggle-password" aria-controls="rl-password"
                  aria-pressed="false">Show</button>
        </div>
      </div>
      <button class="rl-submit" type="submit">Sign in</button>
    </form>
    <div class="rl-demo-hint">
      <strong>{html.escape(DEMO_HINT)}</strong>
      <div class="rl-note" style="margin-top:6px">
        <button class="rl-link-button" type="button" id="rl-demo-fill">Fill the demo credentials</button>
      </div>
    </div>
    <p class="rl-note">Passwords are stored as salted PBKDF2-SHA256 hashes in a local SQLite file.</p>
  </section>
</main>
<script src="/site-assets/login.js" defer></script>
</body>
</html>
"""


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "") -> Response:
    if auth.user_from_cookies(request.cookies) is not None:
        return RedirectResponse(safe_next(next), status_code=303)
    return HTMLResponse(render_login_page(next_path=safe_next(next)))


def _same_origin(request: Request) -> bool:
    """Cross-site POST guard for browsers that send Origin/Referer."""
    origin = request.headers.get("origin") or request.headers.get("referer")
    if not origin:
        return True  # non-browser client (curl, tests); SameSite=Lax covers the rest
    host = request.headers.get("host", "")
    if not host:
        return False
    return origin.split("://", 1)[-1].split("/", 1)[0] == host


@router.post("/login")
async def login_submit(request: Request) -> Response:
    if not _same_origin(request):
        logger.warning("rejected cross-origin login attempt")
        return HTMLResponse(render_login_page(error="Sign-in was blocked. Open the app directly and try again."),
                            status_code=403)

    form = await request.form()
    identifier = str(form.get("username", "") or "")
    password = str(form.get("password", "") or "")
    next_path = safe_next(str(form.get("next", "") or ""))

    user = auth.authenticate(identifier, password)
    if user is None:
        logger.info("failed sign-in attempt")
        return HTMLResponse(
            render_login_page(
                next_path=next_path,
                error="Invalid username or password.",
                username=identifier,
            ),
            status_code=401,
        )

    response = RedirectResponse(next_path, status_code=303)
    response.set_cookie(
        config.SESSION_COOKIE,
        auth.create_session_token(int(user["id"])),
        max_age=config.session_hours() * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.get("/logout")
def logout() -> Response:
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(config.SESSION_COOKIE, path="/")
    return response
