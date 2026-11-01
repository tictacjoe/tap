"""Browser test for the "browse by database" dialog's entry counts (fixed
2026-11-01). The counts read each tracker's loaded data, so a visitor who
opened the dialog before the data files finished loading saw 0 next to every
database, and the 0s stayed put after the data arrived. The server here holds
back tracker.json (the ~14MB Reporting file) so the dialog can be opened
mid-load, the same way a slow connection does it. Skips if Playwright or
Chromium is missing."""

import functools
import http.server
import pathlib
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent
TRACKER_DELAY_S = 3


class _SlowTracker(http.server.SimpleHTTPRequestHandler):
    """Serves the site, but delays data/tracker.json so loading stays in progress."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.split("?")[0].endswith("/data/tracker.json"):
            time.sleep(TRACKER_DELAY_S)
        super().do_GET()


@pytest.fixture(scope="module")
def site_url():
    handler = functools.partial(_SlowTracker, directory=str(SITE_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # Chromium not installed
            pytest.skip(f"Chromium unavailable: {exc}")
        yield b
        b.close()


def test_browse_counts_never_show_zero_while_loading_and_fill_in_after(site_url, browser):
    page = browser.new_page()
    page.goto(site_url + "/index.html", wait_until="domcontentloaded")
    page.click("#browse-instead")

    # Mid-load: no fake 0s -- a placeholder instead.
    during = page.locator(".browse-option-count").all_inner_texts()
    assert during, "dialog listed no databases"
    assert "0" not in during, f"counts showed 0 while loading: {during}"

    # Once loading finishes, the still-open dialog shows the real counts.
    page.wait_for_function("TRACKERS.tracker.data.length > 0", timeout=60000)
    page.wait_for_function(
        "[...document.querySelectorAll('.browse-option-count')].every(el => /^\\d+$/.test(el.textContent))",
        timeout=10000,
    )
    expected = page.evaluate(
        "visibleTrackerKeys(TRACKERS).map(k => String(TRACKERS[k].data.length))"
    )
    assert page.locator(".browse-option-count").all_inner_texts() == expected
    assert "0" not in expected  # every visible tracker has entries today
    page.close()
