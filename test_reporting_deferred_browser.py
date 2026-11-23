"""Browser tests for Reporting's deferred load: data/tracker.json (the big uncurated archive) is
fetched only after the curated trackers have rendered, and a failed fetch leaves the curated
tabs working. Served from this repo on a free port; skips without Playwright/Chromium."""

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


def _new_page(browser):
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return page, errors


def test_curated_records_render_while_reporting_is_held(browser, site_url):
    page, errors = _new_page(browser)
    held = []
    page.route("**/data/tracker.json", lambda r: held.append(r))
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_function("curatedLoaded === true", timeout=60000)
    assert page.evaluate("reportingLoaded") is False
    assert page.locator("#headlines-view .headline-row").count() > 0
    assert errors == []
    # Reporting's request arrives after the first render; let it through.
    for _ in range(50):
        if held:
            break
        page.wait_for_timeout(100)
    assert held
    held[0].continue_()
    page.wait_for_function("reportingLoaded === true", timeout=60000)
    assert page.evaluate("TRACKERS.tracker.data.length") > 1000


def test_reporting_is_requested_only_after_curated_data(browser, site_url):
    page, _ = _new_page(browser)
    held, held_p = [], []
    page.route("**/data/tracker.json", lambda r: held.append(r))
    page.route("**/data/prosecution.json", lambda r: held_p.append(r))
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    assert held == []  # curated is still incomplete, so Reporting has not been asked for
    assert held_p
    held_p[0].continue_()
    page.wait_for_function("curatedLoaded === true", timeout=60000)
    for _ in range(50):
        if len(held) == 1:
            break
        page.wait_for_timeout(100)
    assert len(held) == 1
    held[0].continue_()


def test_a_failed_reporting_file_leaves_curated_working(browser, site_url):
    page, _ = _new_page(browser)
    page.route("**/data/tracker.json", lambda r: r.fulfill(status=404, body=""))
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_function("curatedLoaded === true", timeout=60000)
    page.wait_for_function("reportingFailed === true", timeout=60000)
    banner = page.locator("main .regex-error").first.inner_text()
    assert "Could not load: tracker.json (HTTP 404)" in banner
    assert "Other databases are unaffected." in banner
    assert page.locator("#headlines-view .headline-row").count() > 0
