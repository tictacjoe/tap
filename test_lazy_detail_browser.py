"""Browser tests for lazy card detail (lazy-load Phase 3a, task 1).
A tracker-tab card draws with an empty .entry-detail and builds it once, on
first open (ensureEntryDetail). Skips if Playwright or Chromium is missing."""

import functools
import http.server
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

# Wrap the global buildDetailHtml (a top-level function declaration, looked up
# at call time) with a counter.
_COUNT_CALLS = """() => {
    window.__bdh = 0;
    const real = window.buildDetailHtml;
    window.buildDetailHtml = function (...args) { window.__bdh++; return real.apply(this, args); };
}"""


# Same idea for buildTrailHtml (the sources panels).
_COUNT_TRAILS = """() => {
    window.__bth = 0;
    const real = window.buildTrailHtml;
    window.buildTrailHtml = function (...args) { window.__bth++; return real.apply(this, args); };
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
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # Chromium not installed
            pytest.skip(f"Chromium unavailable: {exc}")
        yield b
        b.close()


@pytest.fixture()
def page(browser, site_url):
    ctx = browser.new_context()
    ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=site_url)
    pg = ctx.new_page()
    pg.goto(site_url + "/index.html")
    pg.wait_for_function("curatedLoaded === true", timeout=60000)
    yield pg
    ctx.close()


def _counted(page, tab):
    """Install the counter after load, then draw the tab."""
    page.evaluate(_COUNT_CALLS)
    page.evaluate(f"selectDatabaseTab('{tab}')")
    page.wait_for_selector("#entries .entry")


def _detail_len(page, card_sel):
    return page.evaluate(
        "(s) => document.querySelector(s).querySelector('.entry-detail').innerText.length", card_sel)


def test_tab_render_builds_no_details(page):
    _counted(page, "govservices")
    assert page.evaluate("window.__bdh") == 0
    assert page.evaluate(
        "[...document.querySelectorAll('#entries .entry .entry-detail')].every(d => d.innerHTML === '')")


def test_opening_a_card_builds_its_detail_once(page):
    _counted(page, "govservices")
    head = page.locator("#entries .entry .entry-head").first
    head.click()
    assert page.evaluate("window.__bdh") == 1
    assert _detail_len(page, "#entries .entry") > 200
    head.click()
    head.click()
    assert page.evaluate("window.__bdh") == 1


def test_deep_link_opens_with_detail(page):
    eid = page.evaluate("TRACKERS.deregulation.data[5].id")
    # The #tracker/id hash is read at page load, so open it in a fresh load.
    ctx = page.context
    deep = ctx.new_page()
    deep.goto(page.url.split("#")[0] + f"#deregulation/{eid}")
    deep.wait_for_function("curatedLoaded === true", timeout=60000)
    page = deep
    sel = f'#entries .entry[data-entry-id="{eid}"]'
    page.wait_for_selector(sel + ".open")
    assert _detail_len(page, sel) > 200


def test_grouped_cabinet_card_deep_link_has_detail(page):
    page.evaluate("selectDatabaseTab('prosecution')")
    page.wait_for_selector("#entries .entry")
    page.evaluate("""() => { const g = document.getElementById('group-mode');
        g.value = 'individual'; g.dispatchEvent(new Event('change', {bubbles: true})); }""")
    eid = page.evaluate("TRACKERS.prosecution.data[3].id")
    page.evaluate(f"openCardById('{eid}')")
    sel = f'#entries .entry[data-entry-id="{eid}"]'
    assert page.evaluate("(s) => document.querySelector(s).classList.contains('open')", sel)
    assert _detail_len(page, sel) > 200


def test_term_highlights_survive_lazy_build(page):
    page.evaluate("selectDatabaseTab('deregulation')")
    page.wait_for_selector("#entries .entry")
    page.fill("#search", "EPA")
    page.wait_for_selector("#entries .entry")
    page.wait_for_timeout(500)
    page.locator("#entries .entry .entry-head").first.click()
    n = page.evaluate("document.querySelector('#entries .entry .entry-detail').querySelectorAll('mark').length")
    assert n > 0


def test_row_copy_link_in_lazy_detail_works_once(page):
    page.evaluate("selectDatabaseTab('govservices')")
    page.wait_for_selector("#entries .entry")
    page.locator("#entries .entry .entry-head").first.click()
    btn = page.locator("#entries .entry .entry-row-tools .share-link-btn[data-share-tracker]").first
    btn.click()
    # The clipboard write is async, so wait for the label to flip.
    page.wait_for_function(
        "document.querySelector('#entries .entry .entry-row-tools .share-link-btn[data-share-tracker]').textContent === 'Copied!'")
    assert page.evaluate("document.querySelector('#entries .entry').classList.contains('open')")


def test_oneliner_search_builds_detail_on_click(page):
    """Global search in 1-liner mode draws rows only; the detail is built on the
    first click, once, and keeps its <mark> highlights."""
    page.evaluate(_COUNT_CALLS)
    # The toggle may sit in a collapsed advanced panel, so set it directly.
    page.evaluate("""() => {
        const cb = document.getElementById('global-oneliner');
        cb.checked = true;
        cb.dispatchEvent(new Event('change', { bubbles: true }));
    }""")
    page.fill("#global-search", "EPA")
    page.wait_for_selector(".oneliner-row")
    page.wait_for_timeout(500)  # let the debounced search settle
    assert page.evaluate("window.__bdh") == 0
    page.locator(".oneliner-row").first.click()
    assert page.evaluate("window.__bdh") == 1
    marks = page.evaluate(
        "document.querySelector('.oneliner-row + .oneliner-detail').querySelectorAll('mark').length")
    assert marks > 0
    # Close and reopen: built once, never rebuilt.
    page.locator(".oneliner-row").first.click()
    page.locator(".oneliner-row").first.click()
    assert page.evaluate("window.__bdh") == 1


def _records_page(page):
    """Counter first, then draw Records again, so every row is built under the
    counter. The page is already loaded (curatedLoaded) and sits on Records
    (the default view), so install the counter and call renderDispatch()."""
    page.evaluate(_COUNT_TRAILS)
    page.evaluate("renderDispatch()")
    page.wait_for_selector("#headlines-view .headline-row")


def test_records_render_builds_no_trails(page):
    _records_page(page)
    assert page.evaluate("window.__bth") == 0
    btn = page.locator('#headlines-view .headline-row button[aria-label="confidence/sources"]').first
    btn.click()
    assert page.evaluate("window.__bth") == 1
    panel = page.locator("#headlines-view .headline-trail-panel:visible").first
    assert panel.locator("a[href]").count() > 0
    btn.click()
    btn.click()
    assert page.evaluate("window.__bth") == 1


def test_tab_row_sources_panel_builds_on_click(page):
    page.evaluate(_COUNT_TRAILS)
    page.evaluate("selectDatabaseTab('govservices')")
    page.wait_for_selector("#entries .entry")
    assert page.evaluate("window.__bth") == 0
    page.locator("#entries .entry button.entry-row-sources").first.click()
    assert page.evaluate("window.__bth") == 1
    panel = page.locator(".entry-row-sources-panel:visible").first
    assert panel.locator("a[href]").count() > 0


def test_records_hover_is_the_skim_summary(page):
    _records_page(page)
    # Expected skim per "tracker:id", read from the loaded tracker data.
    skims = page.evaluate("""() => {
        const out = {};
        for (const k of Object.keys(TRACKERS)) {
          for (const e of (TRACKERS[k].data || [])) {
            const s = e.section_summaries;
            const v = s && (k === 'prosecution' ? s.incident_summary : s.what_changed);
            // Production runs the skim through stripAdaptedItemLabels -> stripProcessLabels.
            if (e.id && v) out[k + ':' + e.id] = stripProcessLabels(v);
          }
        }
        return out;
    }""")
    rows = page.evaluate("""() => [...document.querySelectorAll('#headlines-view .headline-entry')].map(r => ({
        key: r.dataset.entryId ? r.dataset.tracker + ':' + r.dataset.entryId : null,
        title: r.querySelector('.headline-row-text').title,
    }))""")
    norm = lambda x: " ".join((x or "").split())
    checked = 0
    for r in rows:
        if r["key"] in skims:  # skip any row whose entry has no skim (e.g. Reporting)
            assert norm(r["title"]) == norm(skims[r["key"]]), r["key"]
            checked += 1
    assert checked > 0
