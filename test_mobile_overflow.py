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
import json
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
def phone_browser():
    """One Chromium for the module (Playwright's sync API allows only one
    running instance per thread)."""
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch()
        except Exception as exc:  # Chromium build not installed
            pytest.skip(f"Chromium not available for Playwright: {exc}")
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def phone_page(site_url, phone_browser):
    context = phone_browser.new_context(
        viewport={"width": PHONE_WIDTH, "height": PHONE_HEIGHT},
        device_scale_factor=3, is_mobile=True, has_touch=True,
    )
    page = context.new_page()
    page.goto(site_url, wait_until="networkidle")
    page.wait_for_timeout(1500)  # let the tab select and first render settle
    yield page
    context.close()


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


# Status pills (UX refresh spec 5.6, Review Focus 4): with `status_stage`
# routed into every curated data file, Records rows carry a pill after the
# tracker chip. At phone width the pill shrinks to its symbol (the stage name
# stays as aria-label and title), and no row or view may overflow.
_CURATED_FILES = [
    "prosecution.json", "deregulation.json", "government-services.json",
    "oea.json", "trumpfamily.json", "dai.json",
]
PILL_PHONE_WIDTH = 400


def _fulfill_with(body):
    # A one-argument handler: Playwright passes (route, request) to a handler
    # that takes two parameters, so a default-argument lambda would get the
    # request as its body.
    return lambda route: route.fulfill(body=body, content_type="application/json")


def _inject_status_stage(page, stage="Court ruled"):
    data_dir = pathlib.Path(__file__).parent / "data"
    for name in _CURATED_FILES:
        entries = json.loads((data_dir / name).read_text(encoding="utf-8"))
        for entry in entries:
            entry["status_stage"] = stage
        page.route("**/data/" + name, _fulfill_with(json.dumps(entries)))


def test_curated_feed_with_compact_pills_fits_the_phone(site_url, phone_browser):
    context = phone_browser.new_context(
        viewport={"width": PILL_PHONE_WIDTH, "height": PHONE_HEIGHT},
        device_scale_factor=3, is_mobile=True, has_touch=True,
    )
    try:
        page = context.new_page()
        _inject_status_stage(page)
        page.goto(site_url, wait_until="networkidle")
        page.wait_for_timeout(1500)

        pills = page.eval_on_selector_all(
            "#headlines-view .headline-entry .status-pill",
            "els => els.map(e => [e.textContent.trim(), e.getAttribute('aria-label')])")
        assert pills, "expected compact pills on the curated feed rows"
        assert all(p == ["⚖", "Court ruled"] for p in pills), pills[:3]

        measured = page.evaluate(_MEASURE)
        assert measured == {"innerWidth": PILL_PHONE_WIDTH, "scrollWidth": PILL_PHONE_WIDTH}, measured
        overflowing = page.eval_on_selector_all(
            "#headlines-view .headline-row",
            "els => els.filter(r => r.scrollWidth > r.clientWidth"
            " || r.getBoundingClientRect().right > window.innerWidth + 0.5).length")
        assert overflowing == 0

        # Every view, with pills on the cards too.
        views = page.evaluate("() => [...document.querySelectorAll('#tabs option')].map(o => o.value)")
        too_wide = {}
        for value in views:
            page.evaluate(_SELECT_VIEW, value)
            page.wait_for_timeout(900)
            m = page.evaluate(_MEASURE)
            if m["innerWidth"] != PILL_PHONE_WIDTH or m["scrollWidth"] != PILL_PHONE_WIDTH:
                too_wide[value] = m
        assert not too_wide, f"views wider than {PILL_PHONE_WIDTH}px: {too_wide}"
    finally:
        context.close()
