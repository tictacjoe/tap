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
            == f"Reporting feed, uncurated ({counts['reporting']})")


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
    page.locator("#headlines-view .headline-row-text").first.click()
    page.wait_for_timeout(800)
    page.go_back()
    page.wait_for_timeout(800)
    assert page.locator("#feed-tab-reporting").get_attribute("aria-selected") == "true"
    assert set(_row_trackers(page)) == {"tracker"}


def test_headline_text_opens_entry(browser, site_url):
    # 2026-11-15: the headline text (right of the "notes" tag) opens the
    # entry's detail card; the tracker chip is a plain label, not a button.
    page = _open(browser, site_url)
    row = page.locator("#headlines-view .headline-entry").first
    assert row.locator("button.headline-row-tracker").count() == 0
    assert row.locator("span.headline-row-tracker").count() == 1
    text = row.locator(".headline-row-text")
    assert text.get_attribute("role") == "button"
    text.click()
    page.wait_for_timeout(1000)
    entry_id = page.evaluate("history.state && history.state.id")
    assert entry_id
    assert page.locator(f'.entry.open[data-entry-id="{entry_id}"]').count() == 1


def test_headline_text_opens_entry_from_keyboard(browser, site_url):
    page = _open(browser, site_url)
    page.locator("#headlines-view .headline-row-text").first.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(1000)
    entry_id = page.evaluate("history.state && history.state.id")
    assert entry_id
    assert page.locator(f'.entry.open[data-entry-id="{entry_id}"]').count() == 1


def test_tracker_filter_names_match_chips(browser, site_url):
    # 2026-11-15: "All trackers", and each option reads like its tracker chip.
    page = _open(browser, site_url)
    options = page.eval_on_selector_all(
        "#headlines-tracker-filter option", "os => os.map(o => [o.value, o.textContent])")
    assert options[0] == ["", "All trackers"]
    # 2026-11-19: the last two options open the Harms and Possible Illegality
    # views instead of filtering rows, so they have no chip name.
    assert options[-2:] == [["harms", "Harms \u2192"], ["illegality", "Possible Illegality (All Trackers) \u2192"]]
    chips = page.evaluate("HEADLINE_TRACKER_MEDIUM")
    for value, text in options[1:-2]:
        assert text == chips[value]


def test_records_rows_line_up(browser, site_url):
    # 2026-11-15: every part of a Records row starts at the same x on every row
    # (the status pill sits in a fixed-width slot; pills vary 70-142px).
    page = _open(browser, site_url)
    starts = page.evaluate("""() => {
        const rows = [...document.querySelectorAll('#headlines-view .headline-row')].slice(0, 300);
        const out = {};
        for (const sel of ['.headline-row-date', '.headline-row-tracker', '.headline-row-status', '.headline-trail-btn', '.headline-row-text']) {
            out[sel] = [...new Set(rows.map(r => r.querySelector(sel)).filter(Boolean)
                .map(el => Math.round(el.getBoundingClientRect().left)))];
        }
        return out;
    }""")
    for sel, xs in starts.items():
        assert len(xs) == 1, f"{sel} starts at {xs}"
