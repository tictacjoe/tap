"""
Phone-width regression test: no view of the site may be wider than the phone.

The page is loaded in headless Chromium with real mobile emulation (390 x 844,
the width the Glance plan's phone check uses). Mobile emulation matters: when
anything overflows, Chrome's mobile layout widens the *layout viewport* to fit
it (window.innerWidth grows past 390), which is what makes a real phone zoom
the page out. So the test checks both innerWidth and scrollWidth.

Two independent causes have produced overflow here (both fixed together with
this test):

  * main / #headlines-wrap keep `width: max(880px, ...)` on a phone, giving a
    document scrollWidth of 899, when the `@media (max-width: 900px)` override
    that lifts the floor is declared BEFORE those base rules (same specificity,
    so the later base rule wins and the override is dead). Undo the fix by
    moving the override back above the base rules, or deleting it, and this
    test fails with scrollWidth 899.
  * The search box is a nowrap flex row whose text input keeps its intrinsic
    min-width, pushing the "regex" label 21px past the edge (scrollWidth 411).
    Delete `min-width: 0` from `.global-search-box input[type="text"]` and this
    test fails with 411.

The test serves this repo's own directory on a free local port (the page reads
its data from data/*.json, so no network is needed) and skips if Playwright or
its Chromium build is not installed.
"""

import functools
import http.server
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

PHONE_WIDTH = 390
PHONE_HEIGHT = 844


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):  # keep pytest output pristine
        pass


@pytest.fixture(scope="module")
def site_url():
    """Serve this repo's directory on a free port for the duration of the module."""
    handler = functools.partial(_QuietHandler, directory=str(pathlib.Path(__file__).parent))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}/index.html"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def phone_page(site_url):
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:  # Chromium build not installed
            pytest.skip(f"Chromium not available for Playwright: {exc}")
        context = browser.new_context(
            viewport={"width": PHONE_WIDTH, "height": PHONE_HEIGHT},
            device_scale_factor=3, is_mobile=True, has_touch=True,
        )
        page = context.new_page()
        page.goto(site_url, wait_until="networkidle")
        page.wait_for_timeout(1500)  # let the tab select and first render settle
        yield page
        browser.close()


_MEASURE = "() => ({innerWidth: window.innerWidth, scrollWidth: document.documentElement.scrollWidth})"

# The tabs live in a visually-hidden <select id="tabs">; the page's own handler
# listens for its change event, so setting the value and firing it switches view.
_SELECT_VIEW = """(value) => {
    const select = document.getElementById('tabs');
    select.value = value;
    select.dispatchEvent(new Event('change', {bubbles: true}));
}"""


def test_no_view_is_wider_than_the_phone(phone_page):
    views = phone_page.evaluate(
        "() => [...document.querySelectorAll('#tabs option')].map(o => [o.value, o.textContent.trim()])")
    assert len(views) >= 5, f"expected the database views to be listed, got {views}"

    too_wide = {}
    for value, label in views:
        phone_page.evaluate(_SELECT_VIEW, value)
        phone_page.wait_for_timeout(900)
        measured = phone_page.evaluate(_MEASURE)
        if measured["innerWidth"] != PHONE_WIDTH or measured["scrollWidth"] != PHONE_WIDTH:
            too_wide[label] = measured

    assert not too_wide, f"views wider than {PHONE_WIDTH}px: {too_wide}"
