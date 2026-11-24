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


# ---- Task 3: opening a card, sources panel or Listen waits for the full entry ----

# Same counter as test_lazy_detail_browser.py: buildDetailHtml calls.
_COUNT_CALLS = """() => {
    window.__bdh = 0;
    const real = window.buildDetailHtml;
    window.buildDetailHtml = function (...args) { window.__bdh++; return real.apply(this, args); };
}"""

LOADING_DETAILS = "Loading details…"
LOADING_SOURCES = "Loading sources…"
LOAD_FAILED = "Details couldn't be loaded. Reload the page to try again."


def _detail_text(page, card_sel):
    return page.evaluate(
        "(s) => { const d = document.querySelector(s + ' .entry-detail'); return d ? d.innerText.trim() : null; }",
        card_sel)


def test_card_opened_early_fills_after_load(page, site_url):
    release = delayed_full(page)
    _boot(page, site_url)
    page.evaluate(_COUNT_CALLS)
    page.evaluate("selectDatabaseTab('govservices')")
    page.wait_for_selector("#entries .entry")
    page.locator("#entries .entry .entry-head").first.click()
    assert _detail_text(page, "#entries .entry") == LOADING_DETAILS
    assert page.evaluate("window.__bdh") == 0
    release()
    page.wait_for_function("fullEntriesLoaded.govservices === true", timeout=60000)
    page.wait_for_function(
        "document.querySelector('#entries .entry .entry-detail').innerText.length > 200", timeout=10000)
    assert page.evaluate("window.__bdh") == 1


def test_deep_link_before_full_load(page, site_url):
    eid = json.loads((SITE_DIR / "data" / "index" / "deregulation.json").read_text())[5]["id"]
    release = delayed_full(page)
    page.goto(site_url + f"/index.html#deregulation/{eid}")
    page.wait_for_function("curatedLoaded === true", timeout=60000)
    sel = f'#entries .entry[data-entry-id="{eid}"]'
    page.wait_for_selector(sel)
    assert "open" in page.get_attribute(sel, "class")
    assert _detail_text(page, sel) == LOADING_DETAILS
    release()
    page.wait_for_function(
        "(s) => document.querySelector(s + ' .entry-detail').innerText.length > 200", arg=sel, timeout=60000)
    assert page.evaluate("(s) => document.querySelectorAll(s + ' .entry-cols').length", sel) > 0


def test_records_trail_before_full_load(page, site_url):
    release = delayed_full(page)
    _boot(page, site_url)
    page.wait_for_selector("#headlines-view .headline-entry[data-entry-id] .headline-trail-btn")
    row = page.locator("#headlines-view .headline-entry[data-entry-id]").first
    row.locator(".headline-trail-btn").click()
    panel = row.locator(".headline-trail-panel")
    assert panel.inner_text().strip() == LOADING_SOURCES
    release()
    panel.locator("a[href]").first.wait_for(timeout=60000)


def test_full_load_failure_message(page, site_url):
    page.route("**/data/government-services.json", lambda route: route.fulfill(status=500, body="boom"))
    _boot(page, site_url)
    page.evaluate("selectDatabaseTab('govservices')")
    page.wait_for_selector("#entries .entry")
    page.locator("#entries .entry .entry-head").first.click()
    page.wait_for_function(
        "(t) => document.querySelector('#entries .entry .entry-detail').innerText.trim() === t",
        arg=LOAD_FAILED, timeout=60000)


# ---- Task 4: search waits for the full entries (decision 7.3) ----

SEARCH_LOADING = "Loading full entries for search…"


def _body_only_word(file, field="what_changed"):
    """(entry id, word): a word found in `field` of one entry and nowhere else
    in the whole file's JSON, so only a search over full bodies can match it."""
    import re
    entries = json.loads((SITE_DIR / "data" / file).read_text())
    blob = json.dumps(entries).lower()
    for e in entries:
        for w in re.findall(r"[a-z]{9,}", (e.get(field) or "").lower()):
            if blob.count(w) == 1:
                return e["id"], w
    pytest.skip("no body-only word in " + file)


def test_global_search_waits_for_full_entries(page, site_url):
    eid, word = _body_only_word("deregulation.json")
    release = delayed_full(page)
    _boot(page, site_url)
    page.fill("#global-search", word)
    page.wait_for_selector("#entries .search-loading")
    assert page.inner_text("#entries .search-loading").strip() == SEARCH_LOADING
    # The slim index can't match a body-only word, and no "no results" flash.
    assert page.locator("#entries .entry").count() == 0
    release()
    page.wait_for_selector(f'#entries .entry[data-entry-id="{eid}"]', timeout=60000)
    assert page.locator("#entries .search-loading").count() == 0


def test_global_search_matches_full_page(page, browser, site_url):
    _, word = _body_only_word("deregulation.json")
    release = delayed_full(page)
    _boot(page, site_url)
    page.fill("#global-search", word)
    page.wait_for_selector("#entries .search-loading")
    release()
    page.wait_for_function("document.querySelector('#entries .search-loading') === null", timeout=60000)
    page.wait_for_function("lastGlobalRender && lastGlobalRender.curatedN > 0", timeout=60000)
    delayed_n = page.evaluate("lastGlobalRender.curatedN")

    ref = browser.new_context().new_page()
    ref.goto(site_url + "/index.html", wait_until="networkidle")
    ref.wait_for_function("fullEntriesLoaded.dai === true && fullEntriesLoaded.prosecution === true", timeout=60000)
    ref.fill("#global-search", word)
    ref.wait_for_function("lastGlobalRender && lastGlobalRender.curatedN > 0", timeout=60000)
    assert ref.evaluate("lastGlobalRender.curatedN") == delayed_n
    ref.context.close()


def test_tab_search_waits(page, site_url):
    eid, word = _body_only_word("prosecution.json", "incident_summary")
    release = delayed_full(page)
    _boot(page, site_url)
    page.evaluate("selectDatabaseTab('prosecution')")
    page.wait_for_selector("#entries .entry")
    page.fill("#search", word)
    page.wait_for_selector("#entries .search-loading")
    assert page.inner_text("#entries .search-loading").strip() == SEARCH_LOADING
    release()
    page.wait_for_selector(f'#entries .entry[data-entry-id="{eid}"]', timeout=60000)
    assert page.locator("#entries .search-loading").count() == 0


def test_search_waits_then_failure_message(page, site_url):
    page.route("**/data/government-services.json", lambda route: route.fulfill(status=500, body="boom"))
    _boot(page, site_url)
    page.fill("#global-search", "health")
    page.wait_for_function(
        "document.querySelector('#entries .empty-state') && document.querySelector('#entries .empty-state').innerText.includes(\"Search couldn't load every entry\")",
        timeout=60000)


# ---- Task 5: Records adapts claim-checks only when filtered to them ----

def test_records_skips_community_topics(page, site_url):
    _boot(page, site_url)
    page.evaluate("""() => {
        window.__ct = 0;
        const real = window.adaptCommunityTopicEntry;
        window.adaptCommunityTopicEntry = function (...args) { window.__ct++; return real.apply(this, args); };
    }""")
    page.evaluate("headlinesTrackerFilter = ''; renderHeadlinesView()")
    assert page.evaluate("window.__ct") == 0
    page.evaluate("headlinesTrackerFilter = 'communitytopics'; buildHeadlineItems()")
    assert page.evaluate("window.__ct") > 0
    page.evaluate("headlinesTrackerFilter = ''")


# ---- Final-review fixes ----

def test_merge_redraws_stale_rows_and_keeps_open_cards(page, site_url):
    """I1: an index from an older publish (same ids, different glance.what)
    must not leave stale row text after the merge, and a card opened before
    the merge stays open after the redraw."""
    index = json.loads((SITE_DIR / "data" / "index" / "government-services.json").read_text())
    stale = json.loads(json.dumps(index))
    stale[0]["glance"]["what"] = "STALE-WHAT-TEXT"
    page.route("**/data/index/government-services.json",
               lambda route: route.fulfill(status=200, content_type="application/json",
                                           body=json.dumps(stale)))
    release = delayed_full(page)
    _boot(page, site_url)
    page.evaluate("selectDatabaseTab('govservices')")
    page.wait_for_selector("#entries .entry")
    assert "STALE-WHAT-TEXT" in page.inner_text("#entries")
    # Open a card (not the stale one) before the merge.
    open_id = index[1]["id"]
    sel = f'#entries .entry[data-entry-id="{open_id}"]'
    page.locator(sel + " .entry-head").click()
    assert "open" in page.get_attribute(sel, "class")
    release()
    page.wait_for_function("fullEntriesLoaded.govservices === true", timeout=60000)
    page.wait_for_function(
        "!document.getElementById('entries').innerText.includes('STALE-WHAT-TEXT')", timeout=10000)
    assert "open" in page.get_attribute(sel, "class")
    page.wait_for_function(
        "(s) => document.querySelector(s + ' .entry-detail').innerText.length > 200", arg=sel, timeout=10000)


def test_same_publish_merge_redraws_nothing(page, site_url):
    """I1 guard: index and full file from the same publish change nothing on
    screen, so the merge must not redraw (for any tracker)."""
    release = delayed_full(page)
    _boot(page, site_url)
    page.evaluate("""() => {
        window.__rd = 0;
        const real = window.renderDispatch;
        window.renderDispatch = function (...a) { window.__rd++; return real.apply(this, a); };
        window.__merges = {};
        const realMerge = window.mergeFullEntries;
        window.mergeFullEntries = function (k, raw) { const r = realMerge(k, raw); window.__merges[k] = r; return r; };
    }""")
    release()
    assert page.evaluate("ensureFullEntries()") is True
    merges = page.evaluate("window.__merges")
    assert sorted(merges) == sorted(["prosecution", "deregulation", "govservices", "trumpfamily", "dai"])
    assert all(m == {"added": 0, "removed": 0, "changed": 0} for m in merges.values()), merges
    assert page.evaluate("window.__rd") == 0


def test_global_search_works_when_one_tracker_failed_at_boot(page, site_url):
    """I2: a tracker whose index AND full file failed at boot has nothing to
    wait for; global search still searches the other trackers."""
    page.route("**/data/index/dai.json", lambda route: route.fulfill(status=404, body="nope"))
    page.route("**/data/dai.json", lambda route: route.fulfill(status=404, body="nope"))
    _boot(page, site_url)
    page.fill("#global-search", "health")
    page.wait_for_function("lastGlobalRender && lastGlobalRender.curatedN > 0", timeout=60000)
    assert "Search couldn't load every entry" not in page.inner_text("#entries")
    assert page.locator("#entries .search-loading").count() == 0
