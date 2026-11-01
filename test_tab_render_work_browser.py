"""Browser test for the work a tracker tab does when it renders (2026-11-01).
Opening an entry from Records re-renders the whole tracker tab, and with an
empty search box renderEntries() still built every entry's search haystack
(visibleSearchText(), which runs stripProcessLabels()'s regexes) just to have
matchesTerm() return true -- 14,000+ times for Reporting. On a slow or busy
machine that froze the tab for seconds. This counts visibleSearchText() calls
during a render: none with no search, and a search still filters correctly.
Skips if Playwright or Chromium is missing."""

import functools
import http.server
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

# Wraps the global visibleSearchText (a top-level function declaration, so a
# window property that renderEntries() looks up at call time) with a counter.
_COUNT_CALLS = """() => {
    window.__vstCalls = 0;
    const real = window.visibleSearchText;
    window.visibleSearchText = function (...args) { window.__vstCalls++; return real.apply(this, args); };
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


@pytest.fixture(scope="module")
def page(site_url):
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # Chromium not installed
            pytest.skip(f"Chromium unavailable: {exc}")
        pg = b.new_page()
        pg.goto(site_url + "/index.html")
        pg.wait_for_function("TRACKERS.tracker.data.length > 0", timeout=60000)
        pg.evaluate(_COUNT_CALLS)
        yield pg
        b.close()


def test_empty_search_render_builds_no_search_haystacks(page):
    page.evaluate("() => { window.__vstCalls = 0; goToTrackerHome('tracker'); }")
    assert page.evaluate("window.__vstCalls") == 0
    assert page.locator("#entries > .entry").count() == 300  # Reporting's render cap


def test_search_still_filters_after_the_skip(page):
    # Pick a word from one real Reporting entry, search it, expect a narrowed list.
    result = page.evaluate("""() => {
        goToTrackerHome('tracker');
        searchTerm = 'Alaska';
        document.getElementById('search').value = searchTerm;
        window.__vstCalls = 0;
        renderDispatch();
        const cfg = TRACKERS.tracker;
        return {
            calls: window.__vstCalls,
            total: cfg.data.length,
            expected: cfg.data.filter(e => matchesTerm(visibleSearchText(e, cfg), 'Alaska', false)).length,
            shown: document.getElementById('count').textContent,
        };
    }""")
    assert result["calls"] >= result["total"]  # searching does build every haystack
    assert 0 < result["expected"] < result["total"]
    assert str(result["expected"]) in result["shown"]
