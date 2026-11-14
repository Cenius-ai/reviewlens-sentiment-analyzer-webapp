"""Public, server-rendered landing page at ``/``.

This is the front door a shop owner lands on: it explains the product, scores a
review live against the same offline scorer through ``/demo/analyze`` and
lists the seeded sample sets from ``/demo/samples``. The signed-in workspace
lives at ``/app``.
"""

from __future__ import annotations

import html

from .. import config
from ..nlp import get_lexicon
from ..services import analyze_service, sample_service
from ..ui.render import esc, render_result_card, section_label

DEMO_REVIEW = "Absolutely love it, great quality and fast delivery."


def _sample_cards(sets: list[dict]) -> str:
    if not sets:
        return (
            '<div class="rl-card"><div class="rl-empty"><strong>No sample sets available</strong>'
            "Seeding did not run - restart the app to recreate the demo review sets.</div></div>"
        )
    cards = []
    for entry in sets:
        cards.append(
            f"""<article class="rl-card rl-sample-card">
  <div class="rl-card-header">
    <h3 class="rl-h2">{esc(entry.get('name', ''))}</h3>
    <span class="rl-chip rl-chip--muted rl-num">{int(entry.get('review_count', 0))} reviews</span>
  </div>
  <p class="rl-body">{esc(entry.get('description', ''))}</p>
</article>"""
        )
    return "".join(cards)


def _nav(user) -> str:
    if user is None:
        actions = (
            '<a class="rl-signout" href="/login">Sign in</a>'
            '<a class="rl-btn rl-btn--primary" href="/app/">Open the analyzer</a>'
        )
    else:
        actions = (
            f'<span class="rl-meta">Signed in as <strong>{esc(user["username"])}</strong></span>'
            '<a class="rl-btn rl-btn--primary" href="/app/">Open the analyzer</a>'
        )
    return f"""<header class="rl-appbar">
  <div class="rl-appbar-brand">
    <span class="rl-logo" aria-hidden="true">RL</span>
    <div>
      <div class="rl-appbar-title">{esc(config.APP_NAME)}</div>
      <div class="rl-appbar-sub">Offline lexicon scoring · price / quality / shipping aspects</div>
    </div>
  </div>
  <nav class="rl-appbar-actions" aria-label="Primary">{actions}</nav>
</header>"""


def render_landing_page(user=None) -> str:
    lexicon = get_lexicon()
    sets = sample_service.list_sets()
    try:
        example = analyze_service.analyze_review(user_id=0, text=DEMO_REVIEW, persist=False)
        example_html = render_result_card(example, "Live example - scored by this server, nothing stored")
    except analyze_service.ReviewValidationError:  # pragma: no cover - constant demo text
        example_html = '<div class="rl-card"><div class="rl-empty">Paste a review to analyze</div></div>'

    total_reviews = sum(int(entry.get("review_count", 0)) for entry in sets)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{esc(config.APP_NAME)} - review sentiment without an API</title>
<meta name="description" content="{esc(config.APP_TAGLINE)}">
<link rel="icon" type="image/svg+xml" href="/site-assets/favicon.svg">
<link rel="stylesheet" href="/site-assets/app.css">
</head>
<body class="rl-public">
{_nav(user)}
<main class="rl-public-main">
  <section class="rl-hero">
    {section_label("Reviewlens")}
    <h1 class="rl-hero-title">Review sentiment for small shops, without an API bill.</h1>
    <p class="rl-hero-lede">
      Paste a product review and get a label, a -1 to 1 score and the exact lexicon words
      that fired - plus price, quality and shipping verdicts pulled from the clauses that
      mention them. Upload a CSV export and score a thousand rows at once.
    </p>
    <div class="rl-hero-actions">
      <a class="rl-btn rl-btn--primary" href="/app/">Open the analyzer</a>
      <a class="rl-btn" href="#demo">Try it below</a>
    </div>
    <dl class="rl-stats">
      <div class="rl-stat"><dt class="rl-stat-label">Lexicon words</dt><dd class="rl-stat-value rl-num">{lexicon.size}</dd></div>
      <div class="rl-stat"><dt class="rl-stat-label">Aspect buckets</dt><dd class="rl-stat-value rl-num">3</dd></div>
      <div class="rl-stat"><dt class="rl-stat-label">Batch cap</dt><dd class="rl-stat-value rl-num">{config.MAX_BATCH_ROWS:,}</dd></div>
      <div class="rl-stat"><dt class="rl-stat-label">Seeded sample reviews</dt><dd class="rl-stat-value rl-num">{total_reviews}</dd></div>
    </dl>
  </section>

  <section class="rl-demo" id="demo" aria-labelledby="demo-heading">
    <div class="rl-card-header">
      <h2 class="rl-h2" id="demo-heading">Score a review right here</h2>
      <span class="rl-meta">Runs against the same scorer as the app · nothing is stored</span>
    </div>
    <div class="rl-demo-grid">
      <form class="rl-card rl-demo-form" id="rl-demo-form" novalidate>
        <label class="rl-field-label" for="rl-demo-text">Product review</label>
        <textarea id="rl-demo-text" name="text" rows="6" maxlength="5000"
                  placeholder="Paste a product review here…">{esc(DEMO_REVIEW)}</textarea>
        <div class="rl-demo-row">
          <button class="rl-btn rl-btn--primary" type="submit" id="rl-demo-submit">Score this review</button>
          <span class="rl-meta rl-num" id="rl-demo-counter" role="status" aria-live="polite">0 / 5,000 characters</span>
        </div>
        <p class="rl-error" id="rl-demo-error" role="alert" hidden></p>
        <p class="rl-note">No account needed for this box. Sign in to keep history and score CSV batches.</p>
      </form>
      <div id="rl-demo-result" aria-live="polite">{example_html}</div>
    </div>
  </section>

  <section class="rl-samples" aria-labelledby="samples-heading">
    <div class="rl-card-header">
      <h2 class="rl-h2" id="samples-heading">Sample review sets</h2>
      <span class="rl-meta">seeded on first boot, loaded from <code>/demo/samples</code></span>
    </div>
    <div class="rl-sample-grid" id="rl-samples">{_sample_cards(sets)}</div>
  </section>

  <section class="rl-how" aria-labelledby="how-heading">
    <h2 class="rl-h2" id="how-heading" style="margin-bottom:12px">How it scores</h2>
    <div class="rl-how-grid">
      <article class="rl-card">
        {section_label("01 lexicon")}
        <h3 class="rl-h3">Traceable, not opaque</h3>
        <p class="rl-body">{lexicon.size} weighted words ship in the repo with negation and
        intensifier rules, so "not good" reads negative and every point of the score can be
        traced to a word that fired.</p>
      </article>
      <article class="rl-card">
        {section_label("02 aspects")}
        <h3 class="rl-h3">Clause-level verdicts</h3>
        <p class="rl-body">A review is split into clauses; price, quality and shipping verdicts
        come only from the clauses that mention them, so "cheap price but awful quality" gets
        two different answers.</p>
      </article>
      <article class="rl-card">
        {section_label("03 batches")}
        <h3 class="rl-h3">Whole exports, charted</h3>
        <p class="rl-body">Drop a CSV, pick the review column, and get the sentiment split,
        an aspect breakdown and your original file back with sentiment columns appended.</p>
      </article>
    </div>
  </section>
</main>
<footer class="rl-public-footer">
  <p class="rl-note">{esc(config.APP_NAME)} · offline, self-hosted, one SQLite file ·
  <a href="/app/">open the analyzer</a> · <a href="/login">sign in</a></p>
</footer>
<script src="/site-assets/landing.js" defer></script>
</body>
</html>
"""


def render_error_page(status: int, message: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{status} · {esc(config.APP_SHORT_NAME)}</title>
<link rel="icon" type="image/svg+xml" href="/site-assets/favicon.svg">
<link rel="stylesheet" href="/site-assets/app.css">
</head>
<body class="rl-public">
<main class="rl-public-main">
  <section class="rl-card" style="max-width:560px">
    {section_label(f"{status}")}
    <h1 class="rl-h1">{html.escape(message)}</h1>
    <p class="rl-body" style="margin:8px 0 16px">The page you asked for is not part of Reviewlens.</p>
    <p><a class="rl-btn rl-btn--primary" href="/">Back to the overview</a></p>
  </section>
</main>
</body>
</html>
"""
