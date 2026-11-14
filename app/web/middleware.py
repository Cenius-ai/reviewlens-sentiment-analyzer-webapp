"""ASGI middleware: the sign-in gate, security headers and remote-asset scrub.

Layout of the delivered app:

* ``/``            public, server-rendered HTML landing page (always 200)
* ``/login``       public sign-in page
* ``/demo/*``      public page-support endpoints for the landing page
* ``/api/*``       the JSON API: every route requires HTTP Basic or a cookie
                   except ``/api/health`` (so the gate lets them through and the
                   router answers 401 itself)
* ``/app``         the Gradio workspace - requires a session
* everything else  requires a session

Anonymous requests to gated *pages* are redirected (303) to ``/login``; requests
for the workspace's internal JSON/asset endpoints get a 401 so a dead session
never renders an HTML login page into the SPA.
"""

from __future__ import annotations

import json
import re
from urllib.parse import quote, unquote

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from .. import auth

PUBLIC_EXACT = ("/", "/index.html", "/login", "/logout", "/health", "/favicon.ico", "/robots.txt")
PUBLIC_PREFIXES = ("/site-assets/", "/demo/", "/api/")

# Paths that must answer JSON when unauthenticated (the SPA and its data).
JSON_PREFIXES = (
    "/app/gradio_api/",
    "/app/config",
    "/app/info",
    "/app/queue/",
    "/app/heartbeat",
    "/app/static/",
    "/app/assets/",
    "/app/file=",
    "/gradio_api/",
    "/config",
    "/info",
    "/queue/",
    "/heartbeat",
    "/assets/",
    "/static/",
    "/manifest.json",
)

SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cross-Origin-Opener-Policy": "same-origin",
    # Gradio compiles event handlers client-side and injects its own bootstrap
    # script, so inline/eval must stay permitted or the UI renders blank.
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "font-src 'self' data:; "
        "media-src 'self' data: blob:; "
        "connect-src 'self' ws: wss:; "
        "worker-src 'self' blob:; "
        "frame-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    ),
}

REMOTE_SCRIPT_RE = re.compile(rb'<script[^>]*\bsrc="https?://[^"]*"[^>]*>\s*</script>', re.DOTALL)
REMOTE_LINK_RE = re.compile(rb'<link[^>]*\bhref="https?://[^"]*"[^>]*>', re.DOTALL)
REMOTE_META_RE = re.compile(rb'<meta[^>]*\bcontent="https?://[^"]*"[^>]*>', re.DOTALL)


def scrub_remote_assets(body: bytes) -> bytes:
    """Drop third-party script/link/meta tags from a framework-served page."""
    for pattern in (REMOTE_SCRIPT_RE, REMOTE_LINK_RE, REMOTE_META_RE):
        body = pattern.sub(b"", body)
    return body


def _header(scope: Scope, name: bytes) -> str:
    for key, value in scope.get("headers", []):
        if key == name:
            return value.decode("latin-1")
    return ""


def _is_public(path: str) -> bool:
    return path in PUBLIC_EXACT or any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def _wants_json(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in JSON_PREFIXES)


class ReviewlensMiddleware:
    """Deny-by-default gate; every response carries the security headers."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "/")
        if path.endswith("/gradio_api/upload_progress") and _query(scope, "upload_id") in (None, "", "undefined"):
            # Gradio polls upload progress with an undefined id after a small
            # upload; answer "done" instead of letting a 404 reach the console.
            await self._empty_progress(send)
            return

        if not _is_public(path):
            cookies = _parse_cookies(_header(scope, b"cookie"))
            if auth.user_from_cookies(cookies) is None:
                await self._reject(scope, send, path)
                return

        buffered: list[bytes] = []
        state = {"scrub": False}
        is_page = path in ("/", "/app") or path.startswith("/app/")

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for key, value in SECURITY_HEADERS.items():
                    headers[key] = value
                content_type = headers.get("content-type", "")
                if content_type.startswith("text/html") and is_page:
                    state["scrub"] = True
                    if "content-length" in headers:
                        del headers["content-length"]
            elif message["type"] == "http.response.body" and state["scrub"]:
                buffered.append(message.get("body", b""))
                if message.get("more_body"):
                    return
                await send({"type": "http.response.body", "body": scrub_remote_assets(b"".join(buffered))})
                return
            await send(message)

        await self.app(scope, receive, send_wrapper)

    async def _empty_progress(self, send: Send) -> None:
        body = b'data: {"msg": "done"}\n\n'
        headers = [
            (b"content-type", b"text/event-stream"),
            (b"content-length", str(len(body)).encode()),
            (b"cache-control", b"no-store"),
        ]
        for key, value in SECURITY_HEADERS.items():
            headers.append((key.lower().encode(), value.encode()))
        await send({"type": "http.response.start", "status": 200, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def _reject(self, scope: Scope, send: Send, path: str) -> None:
        if _wants_json(path):
            body = json.dumps({"detail": "Not authenticated"}).encode()
            status = 401
            headers = [
                (b"content-type", b"application/json"),
                (b"www-authenticate", b'Basic realm="Reviewlens"'),
                (b"cache-control", b"no-store"),
            ]
        else:
            body = b"Redirecting to sign in."
            status = 303
            headers = [
                (b"location", f"/login?next={quote(path, safe='/')}".encode("latin-1")),
                (b"content-type", b"text/plain; charset=utf-8"),
                (b"cache-control", b"no-store"),
            ]
        headers.append((b"content-length", str(len(body)).encode()))
        for key, value in SECURITY_HEADERS.items():
            headers.append((key.lower().encode(), value.encode()))

        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})


def _query(scope: Scope, name: str) -> str | None:
    query = scope.get("query_string", b"").decode("latin-1")
    for chunk in query.split("&"):
        key, _, value = chunk.partition("=")
        if key == name:
            return unquote(value)
    return None


def _parse_cookies(header: str) -> dict[str, str]:
    cookies: dict[str, str] = {}
    for chunk in header.split(";"):
        if "=" not in chunk:
            continue
        name, _, value = chunk.strip().partition("=")
        if name:
            cookies[name] = value
    return cookies
