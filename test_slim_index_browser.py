"""Browser tests for the slim index boot (lazy-load Phase 3b).
The page's first render reads data/index/<file>; the full data/<file> entries
load afterwards and are merged into the slim objects already in memory
(ensureFullEntries / mergeFullEntries). Skips if Playwright or Chromium is
missing."""

import functools
import http.server
import json
import pathlib
import sys
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

# The five curated files that have an index (community topics doesn't).
FULL_FILES = ["prosecution.json", "deregulation.json", "government-services.json",
              "trumpfamily.json", "dai.json"]


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class _QuietServer(http.server.ThreadingHTTPServer):
    """Closing a page mid-download (e.g. Reporting's large file) resets the
    connection; that's expected here, not worth a traceback."""
    def handle_error(self, request, client_address):
        if isinstance(sys.exc_info()[1], ConnectionError):
            return
        super().handle_error(request, client_address)


@pytest.fixture(scope="module")
def site_url():
    handler = functools.partial(_Quiet, directory=str(SITE_DIR))
    server = _QuietServer(("127.0.0.1", 0), handler)
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


@pytest.fixture()
def page(browser):
    """A page NOT yet navigated, so a test can install routes first."""
    ctx = browser.new_context()
    pg = ctx.new_page()
    yield pg
    ctx.close()


def _boot(page, site_url):
    page.goto(site_url + "/index.html")
    page.wait_for_function("curatedLoaded === true", timeout=60000)


def _is_full_file(url):
    """True for data/<file> of the five indexed trackers, never data/index/<file>."""
    path = url.split("?", 1)[0]
    return any(path.endswith("/data/" + f) for f in FULL_FILES)


def delayed_full(page):
    """Hold every full-file request until release() is called.

    (A sync-API route handler can't sleep without blocking the Playwright
    driver, so the "delay" is a hold that the test releases explicitly.)
    Requests arriving after release() go straight through."""
    held = []
    state = {"released": False}

    def handler(route):
        if state["released"]:
            route.continue_()
        else:
            held.append(route)

    page.route(_is_full_file, handler)

    def release():
        state["released"] = True
        while held:
            held.pop(0).continue_()

    return release


def test_first_render_uses_index(page, site_url):
    release = delayed_full(page)
    _boot(page, site_url)
    page.evaluate("selectDatabaseTab('govservices')")
    page.wait_for_selector("#entries .entry")
    assert page.evaluate("Object.keys(fullEntriesLoaded).length") == 0
    assert page.evaluate("TRACKERS.govservices.data[0].what_changed === undefined")
    # The index really is slim: the full file has the field.
    full = json.loads((SITE_DIR / "data" / "government-services.json").read_text())
    assert "what_changed" in full[0]
    release()


def test_full_entries_merge_in_place(page, site_url):
    release = delayed_full(page)
    _boot(page, site_url)
    page.evaluate("""() => {
        window.__o = TRACKERS.prosecution.data[3];
        window.__cat = window.__o.offense_category;
        window.__hadSummary = typeof window.__o.incident_summary;
    }""")
    assert page.evaluate("window.__hadSummary") == "undefined"
    release()
    assert page.evaluate("ensureFullEntries('prosecution')") is True
    assert page.evaluate("window.__o === TRACKERS.prosecution.data[3]")
    assert page.evaluate("typeof window.__o.incident_summary") == "string"
    assert page.evaluate("window.__o.offense_category === window.__cat")
    assert page.evaluate("fullEntriesLoaded.prosecution") is True
    # One cached promise per tracker: asking again fetches nothing more.
    page.evaluate("ensureFullEntries()")
    before = page.evaluate("window.__fullFetches")
    assert page.evaluate("ensureFullEntries()") is True
    assert page.evaluate("ensureFullEntries('prosecution')") is True
    assert page.evaluate("window.__fullFetches") == before == 5


def test_cla_classified_once(page, site_url):
    _boot(page, site_url)
    assert page.evaluate("ensureFullEntries('prosecution')") is True
    bad = page.evaluate("""async () => {
        const raw = await (await fetch('data/prosecution.json')).json();
        const byId = new Map(TRACKERS.prosecution.data.map(e => [e.id, e]));
        const bad = [];
        raw.forEach(r => {
            const e = byId.get(r.id);
            if (!e || e.offense_category_raw !== r.offense_category
                || e.offense_category !== classifyOffenseCategory(r.offense_category)
                || e.status_category !== classifyStatus(r.status)) bad.push(r.id);
        });
        return bad;
    }""")
    assert bad == []


def test_index_and_full_from_different_publishes(page, site_url):
    index = json.loads((SITE_DIR / "data" / "index" / "deregulation.json").read_text())
    full_ids = [e["id"] for e in json.loads((SITE_DIR / "data" / "deregulation.json").read_text())]
    fake = dict(index[1], id="zz-gone")
    stale = index[1:] + [fake]
    page.route("**/data/index/deregulation.json",
               lambda route: route.fulfill(status=200, content_type="application/json",
                                           body=json.dumps(stale)))
    release = delayed_full(page)
    _boot(page, site_url)
    ids = page.evaluate("TRACKERS.deregulation.data.map(e => e.id)")
    assert ids[-1] == "zz-gone" and full_ids[0] not in ids
    page.evaluate("window.__kept = TRACKERS.deregulation.data[0]")  # index[1]
    release()
    assert page.evaluate("ensureFullEntries('deregulation')") is True
    assert page.evaluate("TRACKERS.deregulation.data.map(e => e.id)") == full_ids
    assert page.evaluate("TRACKERS.deregulation.data[1] === window.__kept")


def test_missing_index_falls_back_to_full(page, site_url):
    page.route("**/data/index/dai.json", lambda route: route.fulfill(status=404, body="nope"))
    _boot(page, site_url)
    assert page.evaluate("fullEntriesLoaded.dai") is True
    page.evaluate("selectDatabaseTab('dai')")
    page.wait_for_selector("#entries .entry")
    # A field the index doesn't carry is there from boot.
    full0 = json.loads((SITE_DIR / "data" / "dai.json").read_text())[0]
    index0 = json.loads((SITE_DIR / "data" / "index" / "dai.json").read_text())[0]
    body_field = sorted(set(full0) - set(index0))[0]
    assert page.evaluate(f"TRACKERS.dai.data[0]['{body_field}'] !== undefined")
    banners = page.evaluate(
        "[...document.querySelectorAll('.regex-error')].map(b => b.textContent)"
        ".filter(t => t.includes('Could not load'))")
    assert banners == []
    # The boot fetch counted, and the background load doesn't fetch dai again.
    assert page.evaluate("ensureFullEntries()") is True
    assert page.evaluate("window.__fullFetches") == 5
