"""HTTP surface: the sign-in page, static assets and the Gradio mount."""

from .routes import router as web_router
from .middleware import ReviewlensMiddleware

__all__ = ["ReviewlensMiddleware", "web_router"]
