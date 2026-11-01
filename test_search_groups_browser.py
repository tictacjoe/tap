"""Browser tests for global search results in three groups: TAP entries,
Claim-checks, and Reporting (not verified by TAP). Search terms are chosen
at test time from the loaded data so they never go stale. Skips if
Playwright or Chromium is missing."""

import functools
import http.server
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

# Runs in the page: counts plain-text matches per group for a term, the same
# way renderGlobalResults decides them.
COUNTS_JS = """term => {
    const n = key => TRACKERS[key].data.filter(e =>
        matchesTerm(visibleSearchText(e, TRACKERS[key]), term, false)).length;
    const curated = visibleTrackerKeys(TRACKERS)
        .filter(k => k !== 'tracker' && k !== 'communitytopics')
        .reduce((a, k) => a + n(k), 0);
    return { curated, claimchecks: n('communitytopics'), reporting: n('tracker') };
}"""

# Candidate words come from the data titles; the first word satisfying
# `want` (a function of the counts) wins.
PICK_JS = """([source, wantSrc]) => {
    const want = eval(wantSrc);
    const cfg = TRACKERS[source];
    const words = new Set();
    cfg.data.forEach(e => String(e[cfg.titleField] || '').split(/[^A-Za-z]+/)
        .filter(w => w.length >= 5).forEach(w => words.add(w.toLowerCase())));
    const n = key => TRACKERS[key].data.filter(e =>
        matchesTerm(visibleSearchText(e, TRACKERS[key]), w, false)).length;
    let w;
    for (w of words) {
        const curated = visibleTrackerKeys(TRACKERS)
            .filter(k => k !== 'tracker' && k !== 'communitytopics')
            .reduce((a, k) => a + n(k), 0);
        if (want({ curated, claimchecks: n('communitytopics'), reporting: n('tracker') })) return w;
    }
    return null;
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


def _open(browser, site_url):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(800)
    return page


def _search(page, term):
    page.fill("#global-search", term)
    page.wait_for_timeout(500)


def _groups(page):
    return page.eval_on_selector_all(
        "#entries section.search-group", "els => els.map(e => e.dataset.group)")


def test_groups_in_order(browser, site_url):
    page = _open(browser, site_url)
    term = page.evaluate(PICK_JS, ["communitytopics",
                                   "c => c.curated > 0 && c.claimchecks > 0 && c.reporting > 0"])
    assert term, "no term in the data matches all three groups"
    counts = page.evaluate(COUNTS_JS, term)
    _search(page, term)
    assert _groups(page) == ["curated", "claimchecks", "reporting"]
    headings = page.eval_on_selector_all(
        "#entries section.search-group > h2.search-group-heading", "els => els.map(e => e.textContent)")
    assert headings == [
        f"TAP entries ({counts['curated']})",
        f"Claim-checks ({counts['claimchecks']})",
        f"Reporting, not verified by TAP ({counts['reporting']})",
    ]


def test_reporting_group_capped_with_show_all(browser, site_url):
    page = _open(browser, site_url)
    term = page.evaluate(PICK_JS, ["tracker", "c => c.reporting > 50"])
    assert term, "no term matches more than 50 Reporting entries"
    counts = page.evaluate(COUNTS_JS, term)
    _search(page, term)
    rows = page.locator('section[data-group="reporting"] .headline-entry')
    assert rows.count() == 50
    assert page.eval_on_selector_all(
        'section[data-group="reporting"] .headline-entry', "els => els.every(e => e.dataset.tracker === 'tracker')")
    button = page.locator('section[data-group="reporting"] button.search-group-show-all')
    assert button.inner_text() == f"Show all {counts['reporting']} in the Reporting database"
    button.click()
    page.wait_for_timeout(500)
    assert page.locator("#global-search").input_value() == ""
    assert page.evaluate("activeTracker") == "tracker"
    assert page.locator("#search").input_value() == term


def test_empty_group_hidden(browser, site_url):
    page = _open(browser, site_url)
    term = page.evaluate(PICK_JS, ["tracker", "c => c.curated === 0 && c.claimchecks === 0 && c.reporting > 0"])
    assert term, "no term matches only Reporting"
    _search(page, term)
    assert _groups(page) == ["reporting"]
    assert page.locator('#entries [data-group="curated"]').count() == 0
    assert "(0)" not in page.locator("#entries").inner_text()
    count = page.locator("#count").inner_text()
    assert "0 result" not in count


def test_tabs_hidden_during_search(browser, site_url):
    page = _open(browser, site_url)
    page.locator("#feed-tab-reporting").click()
    page.wait_for_timeout(300)
    term = page.evaluate(PICK_JS, ["tracker", "c => c.reporting > 0"])
    _search(page, term)
    assert page.locator(".records-feed-tabs").is_hidden()
    page.fill("#global-search", "")
    page.wait_for_timeout(500)
    assert page.locator(".records-feed-tabs").is_visible()
    assert page.locator("#feed-tab-reporting").get_attribute("aria-selected") == "true"
    assert page.locator("#feed-tab-curated").get_attribute("aria-selected") == "false"


def test_curated_oneliner_row_has_tracker_chip(browser, site_url):
    page = _open(browser, site_url)
    term = page.evaluate(PICK_JS, ["deregulation", "c => c.curated > 0"])
    page.click("#search-advanced-btn")
    page.check("#global-oneliner")
    _search(page, term)
    assert page.locator('section[data-group="curated"] .oneliner-row .tracker-chip').count() > 0


def test_back_from_reporting_jump_restores_search(browser, site_url):
    page = _open(browser, site_url)
    term = page.evaluate(PICK_JS, ["tracker", "c => c.reporting > 0"])
    _search(page, term)
    page.locator('section[data-group="reporting"] .headline-row-tracker').first.click()
    page.wait_for_timeout(500)
    page.go_back()
    page.wait_for_timeout(600)
    assert page.locator("#global-search").input_value() == term
    assert page.locator('#entries section[data-group="reporting"]').is_visible()


def test_start_over_closes_advanced_panel(browser, site_url):
    page = _open(browser, site_url)
    page.click("#search-advanced-btn")
    assert page.locator("#search-advanced-panel").is_visible()
    page.click("#start-over-btn")
    assert page.locator("#search-advanced-panel").is_hidden()
    assert page.get_attribute("#search-advanced-btn", "aria-expanded") == "false"
