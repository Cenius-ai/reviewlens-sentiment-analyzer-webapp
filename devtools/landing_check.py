"""Dev-only: verify the public landing page + the gated workspace at /app.

Not part of the shipped app (see README "Development checks"). Point it at any
deployment with ``REVIEWLENS_BASE_URL`` or a positional argument; the default is
the local dev server.
"""

import os
import sys

from playwright.sync_api import sync_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:7860"
BASE = (
    sys.argv[1]
    if len(sys.argv) > 1
    else os.environ.get("REVIEWLENS_BASE_URL", DEFAULT_BASE_URL)
)
failures = []
errors = []


def note(ok, *args):
    line = " ".join(str(a) for a in args)
    print(("ok   " if ok else "FAIL ") + line)
    if not ok:
        failures.append(line)


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--no-sandbox"])
    page = browser.new_context(viewport={"width": 1360, "height": 900}).new_page()
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on("console", lambda msg: errors.append(f"console: {msg.text[:160]}") if msg.type == "error" else None)

    # ---- public landing page ------------------------------------------------
    response = page.goto(BASE + "/", wait_until="load")
    note(response.status == 200, "GET / status:", response.status)
    note("text/html" in response.headers.get("content-type", ""), "GET / content-type:", response.headers.get("content-type"))
    page.wait_for_timeout(1500)
    body = page.inner_text("body")
    note("Review sentiment for small shops" in body, "hero headline rendered")
    note("Mixed weekly export" in body, "seeded sample sets listed")
    note("Score a review right here" in body, "live demo panel present")
    note("Lexicon words that fired" in body, "server-rendered example result")
    styles = page.evaluate("document.styleSheets.length")
    note(styles >= 1, "stylesheet loaded:", styles)
    note(
        page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(245, 251, 255)",
        "committed page background",
    )
    page.screenshot(path="/tmp/landing.png", full_page=True)

    # ---- live demo against the real API -------------------------------------
    page.fill("#rl-demo-text", "Terrible. It broke in a week and support ignored me.")
    page.click("#rl-demo-submit")
    page.wait_for_function(
        "() => document.getElementById('rl-demo-result').innerText.includes('Negative')", timeout=30000
    )
    page.wait_for_timeout(400)
    result = page.inner_text("#rl-demo-result")
    note("Negative" in result, "demo scored via /demo/analyze")
    note("ignored" in result or "broke" in result, "fired words rendered from the API")
    note("Aspects" in result, "aspect table rendered by the landing JS")

    # empty submission keeps the error at the field
    page.fill("#rl-demo-text", "   ")
    page.click("#rl-demo-submit")
    page.wait_for_timeout(600)
    note(
        page.locator("#rl-demo-error").is_visible()
        and "Paste a review" in page.inner_text("#rl-demo-error"),
        "empty demo submit shows an inline error",
    )

    # ---- sign in from the landing page --------------------------------------
    page.goto(BASE + "/app", wait_until="load")
    note("/login" in page.url, "/app requires a session ->", page.url)
    page.fill("#rl-username", "cenius@cenius.ai")
    page.fill("#rl-password", "cenius")
    page.click("button[type=submit]")
    page.wait_for_selector('#rl-tabs button[role="tab"]', timeout=45000)
    page.wait_for_timeout(3000)
    note("/app" in page.url, "post-login lands in the workspace:", page.url)
    body = page.inner_text("body")
    note("Signed in as" in body, "workspace shell rendered")
    note(page.locator('#rl-tabs button[role="tab"]').count() == 4, "four tabs")

    page.fill("#rl-review-input textarea", "Absolutely love it, great quality and fast delivery.")
    page.get_by_role("button", name="Analyze review").click()
    page.wait_for_function("() => document.body.innerText.includes('Lexicon words that fired')", timeout=40000)
    note("Positive" in page.inner_text("body"), "analysis works in the workspace")
    page.screenshot(path="/tmp/workspace.png", full_page=True)

    # ---- mobile -------------------------------------------------------------
    for width in (390, 320):
        page.set_viewport_size({"width": width, "height": 844})
        page.goto(BASE + "/", wait_until="load")
        page.wait_for_timeout(800)
        note(
            not page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"),
            f"landing: no horizontal scroll at {width}",
        )
        page.screenshot(path=f"/tmp/landing-{width}.png", full_page=True)

    browser.close()

print("\n--- console/page errors:", len(errors))
for err in errors[:15]:
    print("   ", err)
print("--- failures:", len(failures))
for failure in failures:
    print("   ", failure)
sys.exit(1 if (failures or errors) else 0)
