"""Browser test: the Claim-checks tab (User Topics) lists newest entries first by
default (2026-10-31, Joe's call -- new submissions were landing mid-list under the
generic impact-score default and were easy to miss). Newest = date_added, then
date_submitted. The site is served from this repo's own directory on a free port.
Skips if Playwright or Chromium is missing."""

import functools
import http.server
import json
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

_SELECT_VIEW = """(value) => {
    const select = document.getElementById('tabs');
    select.value = value;
    select.dispatchEvent(new Event('change', {bubbles: true}));
}"""


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


def test_claim_checks_default_order_is_newest_first(browser, site_url):
    entries = json.loads((SITE_DIR / "data" / "community-topics.json").read_text(encoding="utf-8"))
    by_id = {e["id"]: e for e in entries}
    page = browser.new_page(viewport={"width": 1280, "height": 900})
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.evaluate(_SELECT_VIEW, "communitytopics")
    page.wait_for_timeout(900)
    assert page.locator("#sort-order").input_value() == ""
    shown = page.evaluate("[...document.querySelectorAll('.entry')].map(e => e.dataset.entryId)")
    assert len(shown) == len(entries)
    keys = [(by_id[i].get("date_added") or "", by_id[i].get("date_submitted") or "") for i in shown]
    assert keys == sorted(keys, reverse=True), keys
    # The newest entry is the first card a visitor sees.
    newest = max((e.get("date_added") or "", e.get("date_submitted") or "") for e in entries)
    assert keys[0] == newest
