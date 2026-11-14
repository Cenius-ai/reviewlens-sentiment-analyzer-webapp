"""Dev-only: drive the workspace flows (upload, download, history, clear).

Point it anywhere with REVIEWLENS_BASE_URL or a positional argument; the default
is the local dev server.
"""

import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

DEFAULT_BASE_URL = "http://127.0.0.1:7860"
BASE = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("REVIEWLENS_BASE_URL", DEFAULT_BASE_URL)
WORKSPACE = BASE.rstrip("/") + "/app/"

CSV = Path("/tmp/flow-workspace.csv")
CSV.write_text(
    "order_id,review,rating\n"
    'A-1,"Absolutely love it, great quality and fast delivery.",5\n'
    'A-2,"Terrible. It broke in a week and support ignored me.",1\n'
    "A-3,,3\n"
    'A-4,"Cheap price but the quality is awful and shipping took three weeks.",2\n'
    'A-5,"Shipping was very slow and the packaging arrived damaged.",2\n'
    'A-6,"Great value, worth every penny. Arrived in two days.",5\n'
    "A-7,,4\n"
    'A-8,"The colour is nice but the material feels thin for the price.",3\n'
    'A-9,"Excellent quality, sturdy build and prompt delivery.",5\n'
    'A-10,"Overpriced for what you get. The finish is mediocre.",2\n',
    encoding="utf-8",
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
    page = browser.new_context(viewport={"width": 1360, "height": 900}, accept_downloads=True).new_page()
    page.on("pageerror", lambda exc: errors.append(f"pageerror: {exc}"))
    page.on("console", lambda msg: errors.append(f"console: {msg.text[:160]}") if msg.type == "error" else None)

    page.goto(WORKSPACE, wait_until="load")
    note("/login" in page.url, "workspace requires a session ->", page.url)
    page.fill("#rl-username", "cenius@cenius.ai")
    page.fill("#rl-password", "cenius")
    page.click("button[type=submit]")
    page.wait_for_selector('#rl-tabs button[role="tab"]', timeout=45000)
    page.wait_for_timeout(3000)
    note("/app" in page.url and '#rl-tabs' in page.content(), "signed in at the workspace:", page.url)

    # batch upload
    page.locator('#rl-tabs button[role="tab"]').nth(1).click()
    page.wait_for_timeout(1500)
    page.set_input_files("#rl-batch-upload input[type=file]", str(CSV))
    page.wait_for_timeout(3000)
    note("found 3 columns" in page.inner_text("body").lower(), "column detection works under /app/")
    note(page.locator("#rl-batch-column input").input_value() == "review", "review column auto-detected")

    page.get_by_role("button", name="Score reviews").click()
    page.wait_for_function("() => document.body.innerText.includes('Download scored CSV')", timeout=45000)
    page.wait_for_timeout(1000)
    body = page.inner_text("body")
    note("8 rows scored" in body, "rows scored")
    note("2 blank rows skipped" in body, "blank rows skipped")
    note("Sentiment split" in body, "chart rendered")

    with page.expect_download(timeout=30000) as info:
        page.get_by_role("link", name="Download scored CSV").click()
    target = Path("/tmp/downloaded-workspace.csv")
    info.value.save_as(target)
    header = target.read_text(encoding="utf-8").splitlines()[0]
    note("sentiment_label" in header and "shipping_label" in header, "download header:", header)

    # history reload + clear
    page.locator('#rl-tabs button[role="tab"]').nth(3).click()
    page.wait_for_timeout(2500)
    note("stored analyses" in page.inner_text("body"), "history populated")
    page.locator("#rl-history-table td .cell-wrap").nth(1).click(force=True)
    page.wait_for_timeout(2500)
    note("Loaded from history" in page.inner_text("body"), "row click reloads into Analyze")
    page.locator('#rl-tabs button[role="tab"]').nth(3).click()
    page.wait_for_timeout(1500)
    page.get_by_role("checkbox").check()
    page.get_by_role("button", name="Clear history").click()
    page.wait_for_timeout(2500)
    note("No analyses yet" in page.inner_text("body"), "confirmed clear empties history")

    # mobile workspace
    for width in (390, 320):
        page.set_viewport_size({"width": width, "height": 844})
        page.wait_for_timeout(1000)
        note(
            not page.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"),
            f"workspace: no horizontal scroll at {width}",
        )

    browser.close()

print("\n--- console/page errors:", len(errors))
for err in errors[:15]:
    print("   ", err)
print("--- failures:", len(failures))
for failure in failures:
    print("   ", failure)
sys.exit(1 if (failures or errors) else 0)
