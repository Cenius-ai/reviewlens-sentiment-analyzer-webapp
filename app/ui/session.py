"""Signed-in user resolution for Gradio callbacks."""

from __future__ import annotations

import logging
import sqlite3

import gradio as gr

from .. import auth

logger = logging.getLogger(__name__)


def current_user(request: gr.Request | None) -> sqlite3.Row | None:
    """The user behind a Gradio callback, from the signed session cookie."""
    if request is None:
        return None
    try:
        cookies = getattr(request, "cookies", None)
    except AttributeError:
        return None
    return auth.user_from_cookies(cookies)


def require_user(request: gr.Request | None) -> sqlite3.Row:
    user = current_user(request)
    if user is None:
        raise gr.Error("Your session expired. Sign in again to keep going.")
    return user
