"""Hidden Trump Family tracker: no tab, no browse option, no Headlines row,
no global-search hit, deep link inert; flipping hidden shows the tab with a
fixture entry grouped per family member. Served from this repo on a free
port; skips without Playwright/Chromium."""

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


def _goto(browser, site_url, fragment):
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/index.html" + (f"#{fragment}" if fragment else ""), wait_until="networkidle")
    page.wait_for_timeout(1500)
    return page, errors


FIXTURE = {
    "id": "tfs-fixture", "title": "Fixture WLF deal", "category": "crypto",
    "family_members": ["Eric Trump", "Donald Trump Jr."],
    "business_entity": {"name": "World Liberty Financial"},
    "government_nexus": {"action": "x", "official": {"name": "Y", "role": "Z"}},
    "financial_stake": {"summary": "s", "figures": [], "caveat": "c"},
    "date_of_action": "2026-01-01", "date_added": "2026-10-17", "status": "Ongoing", "sources": [],
}


def _inject(page):
    page.evaluate("""(fx) => { TRACKERS.trumpfamily.data = [mapTrumpFamilyEntry(fx)]; }""", FIXTURE)


def test_hidden_tracker_has_no_tab_browse_or_headlines(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _inject(page)
    page.evaluate("renderTabs()")
    assert page.locator('#tabs option[value="trumpfamily"]').count() == 0
    assert page.locator('#headlines-tracker-filter option[value="trumpfamily"]').count() == 0
    assert page.evaluate("buildHeadlineItems().filter(i => i.tracker === 'trumpfamily').length") == 0
    # Browse modal lists no Trump Family option.
    page.evaluate("openBrowseModal()")
    browse = page.locator("#browse-options .browse-option-btn").all_inner_texts()
    assert browse and not any("Trump Family" in t for t in browse)
    page.evaluate("closeBrowseModal()")
    # Global search (the #global-search input -> renderDispatch ->
    # renderGlobalResults) finds nothing from the hidden tracker.
    page.fill("#global-search", "Fixture WLF")
    page.wait_for_timeout(300)
    assert page.locator('#entries .entry[data-entry-id="tfs-fixture"]').count() == 0
    assert "Trump Family" not in page.locator("#entries").inner_text()
    assert errors == []


def test_hidden_tracker_deep_link_is_inert(browser, site_url):
    page, errors = _goto(browser, site_url, "trumpfamily/tfs-fixture")
    assert page.evaluate("activeTracker") != "trumpfamily"
    assert errors == []


def test_unhidden_tracker_shows_tab_and_groups_per_member(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _inject(page)
    page.evaluate("TRACKERS.trumpfamily.hidden = false; renderTabs(); switchToTracker('trumpfamily');")
    assert page.locator('#tabs option[value="trumpfamily"]').count() == 1
    page.select_option("#group-mode", "family")
    heads = page.locator(".official-group-name").all_inner_texts()
    assert sorted(heads) == ["Donald Trump Jr.", "Eric Trump"]
    assert errors == []
