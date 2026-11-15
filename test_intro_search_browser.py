"""Browser tests for the (removed) intro strip and the Advanced search toggle.
Serves this repo's directory on a free port; page.route stubs
data/site_meta.json. Skips if Playwright or Chromium is missing."""

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


def _open(browser, site_url, width=1280):
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(800)
    return page


def test_intro_strip_removed(browser, site_url):
    # 2026-11-15 (Joe): the intro strip is gone; the browse button says "tracker".
    page = _open(browser, site_url)
    assert page.locator("#intro-strip").count() == 0
    assert page.locator("#browse-instead").inner_text().strip().lower() == "— browse by tracker —"


def test_advanced_panel_hidden_by_default(browser, site_url):
    page = _open(browser, site_url)
    assert not page.locator("#search-advanced-panel").is_visible()
    assert page.locator("#search-advanced-btn").inner_text().strip() == "Advanced \u25be"
    assert page.get_attribute("#search-advanced-btn", "aria-expanded") == "false"


def test_advanced_shows_active_count(browser, site_url):
    page = _open(browser, site_url)
    page.click("#search-advanced-btn")
    assert page.locator("#search-advanced-panel").is_visible()
    page.check("#global-regex")
    page.click("#search-advanced-btn")
    assert not page.locator("#search-advanced-panel").is_visible()
    assert page.locator("#search-advanced-btn").inner_text().strip() == "Advanced (1) \u25be"
    page.click("#search-advanced-btn")
    page.check("#global-oneliner")
    page.click("#search-advanced-btn")
    assert page.locator("#search-advanced-btn").inner_text().strip() == "Advanced (2) \u25be"
