"""Reviewlens Sentiment Analyzer - entrypoint.

``python -m app.main`` (or ``uvicorn app.main:app``) creates the SQLite schema,
seeds the demo data on the way up, and serves the Gradio UI behind a sign-in page.
"""

from __future__ import annotations

import logging
import os

import gradio as gr
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.staticfiles import StaticFiles

from . import auth, config, db
from .api import router as api_router
from .ui.app_ui import SHELL_HEAD, build_app
from .ui.theme import build_theme, stylesheet
from .web import ReviewlensMiddleware, web_router
from .web.landing import render_error_page, render_landing_page
from .web.demo import router as demo_router

logging.basicConfig(
    level=os.getenv("REVIEWLENS_LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("reviewlens")


def create_app() -> FastAPI:
    # Schema + demo seed happen here, on the normal boot path, so a bare start
    # on a fresh clone always lands on a populated app.
    db.init_db()

    app = FastAPI(
        title=config.APP_NAME,
        version=config.APP_VERSION,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(ReviewlensMiddleware)

    app.include_router(web_router)
    app.include_router(demo_router)  # public landing-page helpers, outside /api
    app.include_router(api_router, prefix="/api")  # every route authenticates itself
    app.mount("/site-assets", StaticFiles(directory=str(config.static_dir())), name="assets")

    @app.get("/health")
    def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION})

    def _landing_page(request: Request) -> HTMLResponse:
        user = auth.user_from_cookies(request.cookies)
        return HTMLResponse(render_landing_page(user))

    @app.get("/", response_class=HTMLResponse)
    def landing(request: Request) -> HTMLResponse:
        """The public front door: real product page with a live scoring demo."""
        return _landing_page(request)

    @app.get("/index.html", response_class=HTMLResponse)
    def landing_alias(request: Request) -> HTMLResponse:
        return _landing_page(request)

    @app.get("/robots.txt", response_class=HTMLResponse)
    def robots() -> HTMLResponse:
        return HTMLResponse("User-agent: *\nDisallow: /app\nDisallow: /api/\n", media_type="text/plain")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> Response:
        """Keep API error details intact; give humans a styled page."""
        if request.url.path.startswith(("/api/", "/app/", "/demo/")):
            # keep challenge headers (e.g. WWW-Authenticate on 401) intact
            return JSONResponse(
                {"detail": exc.detail},
                status_code=exc.status_code,
                headers=dict(exc.headers or {}),
            )
        message = "Page not found" if exc.status_code == 404 else str(exc.detail)
        return HTMLResponse(render_error_page(exc.status_code, message), status_code=exc.status_code)

    @app.get("/favicon.ico", include_in_schema=False)
    def favicon() -> Response:
        return Response(
            content=(config.static_dir() / "favicon.svg").read_bytes(),
            media_type="image/svg+xml",
            headers={"Cache-Control": "public, max-age=86400"},
        )

    demo = build_app()
    gr.mount_gradio_app(
        app,
        demo,
        path="/app",
        server_name=config.HOST,
        server_port=config.port(),
        # Gradio 6 takes the shell styling on the mount, not on Blocks().
        theme=build_theme(),
        css=stylesheet(),
        head=SHELL_HEAD,
        footer_links=[],
        show_error=True,
        ssr_mode=False,
    )
    return app


app = create_app()


def main() -> None:
    port = config.port()
    logger.info("Reviewlens listening on http://%s:%s", config.HOST, port)
    uvicorn.run(app, host=config.HOST, port=port, log_level=os.getenv("REVIEWLENS_LOG_LEVEL", "info").lower())


if __name__ == "__main__":
    main()
