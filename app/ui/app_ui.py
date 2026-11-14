"""The Gradio Blocks application: shell, tabs and load handlers."""

from __future__ import annotations

import logging
import sqlite3

import gradio as gr

from .. import config
from ..nlp import get_lexicon
from .render import esc, section_label
from .session import current_user
from .tabs import analyze_tab, batch_tab, history_tab, samples_tab
from .theme import build_theme, stylesheet

logger = logging.getLogger(__name__)

# Gradio re-scopes the ``css=`` stylesheet to inside its component tree, so the few
# rules that live *outside* that tree (the shell padding, the container width) are
# injected through ``head`` instead. Everything visual still comes from app.css.
SHELL_HEAD = """
<link rel="icon" type="image/svg+xml" href="/site-assets/favicon.svg">
<style>
  .gradio-container { width: 100% !important; min-width: 0 !important; max-width: 1280px !important; margin: 0 auto !important; }
  main.fillable { width: 100% !important; min-width: 0 !important; padding: 10px 14px 40px !important; }
  @media (min-width: 640px) { main.fillable { padding: 14px 20px 48px !important; } }
  @media (min-width: 1024px) { main.fillable { padding: 16px 28px 64px !important; } }
  body { background: #f5fbff; color: #0b1418; }
</style>
"""


def header_html(user: sqlite3.Row | None) -> str:
    if user is None:
        identity = (
            '<span class="rl-meta">Not signed in</span>'
            '<a class="rl-signout" href="/login">Sign in</a>'
        )
    else:
        identity = (
            f'<span>Signed in as <strong>{esc(user["username"])}</strong>'
            f' <span class="rl-meta">· {esc(user["role"])}</span></span>'
            '<a class="rl-signout" href="/logout">Sign out</a>'
        )
    return f"""
<header class="rl-appbar">
  <div class="rl-appbar-brand">
    <span class="rl-logo" aria-hidden="true">RL</span>
    <div>
      <h1 class="rl-appbar-title">{esc(config.APP_NAME)}</h1>
      <div class="rl-appbar-sub">Offline lexicon scoring · price / quality / shipping aspects</div>
    </div>
  </div>
  <div class="rl-appbar-actions">{identity}</div>
</header>"""


def footer_html() -> str:
    lexicon = get_lexicon()
    return f"""
<footer class="rl-card" style="margin-top:24px">
  <div class="rl-card-header">
    {section_label("About")}
    <span class="rl-meta rl-num">lexicon v{lexicon.version} · {lexicon.size} weighted words</span>
  </div>
  <p class="rl-body" style="max-width:78ch">
    Reviewlens scores English product reviews with a lexicon that ships inside the repository -
    no model weights, no API keys and no outbound network calls. Every point of the score is
    traceable to a word that fired, and aspect verdicts come only from the clauses that mention
    price, quality or shipping.
  </p>
  <p class="rl-note">Data stays on this machine in one SQLite file. Signed in accounts only ever see their own history and batches.</p>
</footer>"""


def _load_header(request: gr.Request) -> str:
    return header_html(current_user(request))


def build_app() -> gr.Blocks:
    with gr.Blocks(
        title=f"{config.APP_NAME} - review sentiment without an API",
        fill_width=True,
        analytics_enabled=False,
    ) as demo:
        header = gr.HTML(header_html(None))
        with gr.Tabs(elem_id="rl-tabs"):
            with gr.Tab("Analyze", id="analyze"):
                analyze = analyze_tab.build()
            with gr.Tab("Batch CSV", id="batch") as batch_tab_ui:
                batch = batch_tab.build()
            with gr.Tab("Samples", id="samples"):
                samples_tab.build(analyze)
            with gr.Tab("History", id="history") as history_tab_ui:
                history = history_tab.build(analyze)
        gr.HTML(footer_html())

        on_page_load = getattr(demo, "load")
        on_page_load(_load_header, inputs=None, outputs=[header], queue=False)
        on_page_load(
            batch_tab.load_for,
            inputs=None,
            outputs=[batch["charts"], batch["table"], batch["recent"]],
        )
        on_page_load(
            history_tab.load_for,
            inputs=None,
            outputs=[history["state"], history["table"], history["summary"]],
        )
        # Opening a data tab re-reads it, so a fresh analysis or upload shows up
        # immediately without a page reload.
        batch_tab_ui.select(
            batch_tab.load_for,
            inputs=None,
            outputs=[batch["charts"], batch["table"], batch["recent"]],
        )
        history_tab_ui.select(
            history_tab.load_for,
            inputs=None,
            outputs=[history["state"], history["table"], history["summary"]],
        )
        demo.queue(default_concurrency_limit=8)

    return demo
