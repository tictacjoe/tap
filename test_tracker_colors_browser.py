"""Browser tests for tracker colors: chips on Records rows, left borders on
curated cards. Skips if Playwright or Chromium is missing."""

import functools
import http.server
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def site_url():
    handler = functools.partial(_Quiet, directory=str(SITE_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()
    server.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as playwright:
        try:
            instance = playwright.chromium.launch()
        except Exception as exc:
            pytest.skip(f"Chromium not available for Playwright: {exc}")
        yield instance
        instance.close()


def _open(browser, site_url):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(800)
    return page


def test_rows_have_tracker_chips(browser, site_url):
    page = _open(browser, site_url)
    counts = page.eval_on_selector_all(
        "#headlines-view .headline-entry",
        "els => els.map(e => e.querySelectorAll('.tracker-chip').length)")
    assert counts and all(c == 1 for c in counts)
    # The chip carries the tracker name as text, not color alone.
    texts = page.eval_on_selector_all(
        "#headlines-view .headline-entry .tracker-chip", "els => els.map(e => e.textContent.trim())")
    assert all(texts)

    page.locator("#feed-tab-reporting").click()
    page.wait_for_timeout(500)
    rows = page.locator("#headlines-view .headline-entry")
    assert rows.count() > 0
    assert page.locator("#headlines-view .tracker-chip").count() == 0
    label = page.locator("#headlines-view .headline-row-tracker").first.inner_text()
    assert "reporting" in label.lower()


def test_cards_have_left_border(browser, site_url):
    page = _open(browser, site_url)
    page.evaluate("goToTrackerHome('prosecution')")
    page.wait_for_timeout(800)
    card = page.locator(".entry.curated-card").first
    assert card.count() == 1
    color = card.evaluate("e => getComputedStyle(e).borderLeftColor")
    width = card.evaluate("e => getComputedStyle(e).borderLeftWidth")
    assert color == "rgb(122, 63, 143)"
    assert width == "6px"
