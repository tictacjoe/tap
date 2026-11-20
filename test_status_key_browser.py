"""Browser tests for the status key above the result count (Joe, 2026-11-20).
Serves this repo's directory on a free port. Skips if Playwright or
Chromium is missing."""

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


STAGES = ["Reversed or withdrawn", "Court ruled", "In court",
          "Finding issued", "Under investigation", "Unchallenged"]


def test_records_key_lists_all_six_stages_with_definitions(browser, site_url):
    page = _open(browser, site_url)
    key = page.locator("#status-key-records")
    assert key.is_visible()
    names = key.locator(".status-key-name")
    assert names.count() == 6
    items = key.locator(".status-key-item")
    for i, name in enumerate(STAGES):
        assert name in names.nth(i).inner_text()
        assert len(items.nth(i).inner_text()) > len(name) + 10  # meaning follows the name
    assert key.locator(".status-pill, button").count() == 0  # plain text only


def test_key_hidden_on_reporting_feed(browser, site_url):
    page = _open(browser, site_url)
    page.locator("#feed-tab-reporting").click()
    page.wait_for_timeout(400)
    assert not page.locator("#status-key-records").is_visible()


def test_key_on_a_tracker_tab(browser, site_url):
    page = _open(browser, site_url)
    page.evaluate("switchToTracker('prosecution')")
    page.wait_for_timeout(800)
    assert page.locator("#status-key-tab").is_visible()


def test_key_is_plain_single_column_with_hyphens(browser, site_url):
    """Joe, 2026-11-20 rev 2: no icons or colors, "Name - meaning", one column."""
    page = _open(browser, site_url)
    key = page.locator("#status-key-records")
    items = key.locator(".status-key-item")
    xs = set()
    body_color = key.evaluate("el => getComputedStyle(el).color")
    for i, name in enumerate(STAGES):
        item = items.nth(i)
        assert item.inner_text().startswith(name + " - ")
        xs.add(round(item.bounding_box()["x"]))
        assert item.locator(".status-key-name").evaluate(
            "el => getComputedStyle(el).color") == body_color
    assert len(xs) == 1  # every stage starts at the same left edge
