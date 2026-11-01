"""Browser tests for the Records feed tabs ("TAP entries" / "Reporting feed").
Serves this repo's directory on a free port. Rows are identified by their
data-tracker attribute, never by visible abbr text. Skips if Playwright or
Chromium is missing."""

import functools
import http.server
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent
NON_CURATED = ("tracker", "communitytopics")


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


def _row_trackers(page):
    return page.eval_on_selector_all(
        "#headlines-view .headline-entry", "els => els.map(e => e.dataset.tracker)")


def test_default_tab_is_curated(browser, site_url):
    page = _open(browser, site_url)
    assert page.locator("#feed-tab-curated").get_attribute("aria-selected") == "true"
    assert page.locator("#feed-tab-reporting").get_attribute("aria-selected") == "false"
    trackers = _row_trackers(page)
    assert trackers, "expected rows on the default tab"
    assert all(t and t not in NON_CURATED for t in trackers)
    assert page.locator("#headlines-sort").input_value() == "date-desc"


def test_tab_counts(browser, site_url):
    page = _open(browser, site_url)
    counts = page.evaluate("""() => {
        const items = buildHeadlineItems().filter(i => extractFirstDate(i.date) >= 20250101);
        const vis = visibleTrackerKeys(TRACKERS).filter(k => k !== 'tracker' && k !== 'communitytopics');
        return {
          curated: items.filter(i => vis.includes(i.tracker)).length,
          reporting: items.filter(i => i.tracker === 'tracker').length,
        };
    }""")
    assert counts["curated"] > 0 and counts["reporting"] > 0
    assert page.locator("#feed-tab-curated").inner_text() == f"TAP entries ({counts['curated']})"
    assert (page.locator("#feed-tab-reporting").inner_text()
            == f"Reporting feed, unverified ({counts['reporting']})")


def test_reporting_tab_only_reporting(browser, site_url):
    page = _open(browser, site_url)
    page.locator("#feed-tab-reporting").click()
    page.wait_for_timeout(500)
    assert page.locator("#feed-tab-reporting").get_attribute("aria-selected") == "true"
    trackers = _row_trackers(page)
    assert trackers and set(trackers) == {"tracker"}
    assert page.locator("#headlines-tracker-filter").is_hidden()
    assert page.locator("#headlines-sort").input_value() == "date-desc"


def test_curated_filter_lists_only_visible_curated(browser, site_url):
    page = _open(browser, site_url)
    values = page.eval_on_selector_all(
        "#headlines-tracker-filter option", "os => os.map(o => o.value)")
    assert "tracker" not in values and "communitytopics" not in values
    assert "deregulation" in values


def test_exclude_button_removed(browser, site_url):
    page = _open(browser, site_url)
    assert page.locator("#headlines-exclude-reporting-btn").count() == 0


def test_tabs_are_keyboard_operable(browser, site_url):
    page = _open(browser, site_url)
    page.locator("#feed-tab-reporting").focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(300)
    assert page.locator("#feed-tab-reporting").get_attribute("aria-selected") == "true"
    page.locator("#feed-tab-curated").focus()
    page.keyboard.press("Space")
    page.wait_for_timeout(300)
    assert page.locator("#feed-tab-curated").get_attribute("aria-selected") == "true"


def test_back_returns_to_reporting_tab(browser, site_url):
    page = _open(browser, site_url)
    page.locator("#feed-tab-reporting").click()
    page.wait_for_timeout(500)
    page.locator("#headlines-view .headline-row-tracker").first.click()
    page.wait_for_timeout(800)
    page.go_back()
    page.wait_for_timeout(800)
    assert page.locator("#feed-tab-reporting").get_attribute("aria-selected") == "true"
    assert set(_row_trackers(page)) == {"tracker"}
