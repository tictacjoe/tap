"""Phase B redirects and the CLA 'Also in Trump Family' line. Injects state in-page
(TFS is public since the 2026-10-17 cutover; _setup injects fixture state). Served from this repo on a free
port; skips without Playwright/Chromium."""

import functools
import http.server
import json
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

# loadAllData() reports failed loads in a .regex-error banner it prepends to
# <main> (the static #regex-error element is the search box's, not this one).
LOAD_ERROR_BANNER = "main > .regex-error:not(#regex-error)"


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


def _setup(page):
    """Unhide TFS in-page with one fixture entry and a moved-ids map pointing at it."""
    page.evaluate("""() => {
      const fx = mapTrumpFamilyEntry({id: "moved-fx", title: "Fixture", category: "crypto",
        family_members: ["Eric Trump"], business_entity: {name: "World Liberty Financial"},
        government_nexus: {action: "a", official: {name: "Steve Witkoff", role: "Envoy"}},
        financial_stake: {summary: "s", figures: [], caveat: "c"}, status: "Ongoing", sources: []});
      TRACKERS.trumpfamily.hidden = false;
      TRACKERS.trumpfamily.data = [fx];
      MOVED_IDS = {"moved-fx": {from: "prosecution", to: "trumpfamily", date: "2026-10-20"}};
    }""")


def test_committed_site_shows_tfs_and_loads_moved_ids(browser, site_url):
    # Public since the Phase B cutover (2026-10-17).
    page, errors = _goto(browser, site_url, "")
    assert page.evaluate("!!TRACKERS.trumpfamily.hidden") is False
    assert page.evaluate("JSON.stringify(MOVED_IDS)") == json.dumps(
        json.loads((SITE_DIR / "data" / "moved-ids.json").read_text()), separators=(",", ":"))
    assert errors == []


def test_old_link_redirects_and_rewrites_url(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _setup(page)
    page.evaluate("location.hash = '#prosecution/moved-fx'; openEntryFromHash();")
    assert page.evaluate("activeTracker") == "trumpfamily"
    assert page.evaluate("location.hash") == "#trumpfamily/moved-fx"
    assert page.locator('.entry.open[data-entry-id="moved-fx"]').count() == 1
    assert errors == []


def test_unmoved_cla_link_unchanged(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _setup(page)
    cla_id = page.evaluate("TRACKERS.prosecution.data[0].id")
    page.evaluate("(id) => { location.hash = '#prosecution/' + id; openEntryFromHash(); }", cla_id)
    assert page.evaluate("activeTracker") == "prosecution"
    assert page.evaluate("location.hash") == "#prosecution/" + cla_id
    assert errors == []


def test_missing_moved_ids_file_is_harmless(browser, site_url):
    page = browser.new_context().new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.route("**/data/moved-ids.json", lambda route: route.fulfill(status=404, body=""))
    page.goto(f"{site_url}/index.html", wait_until="networkidle")
    page.wait_for_timeout(1500)
    assert page.evaluate("JSON.stringify(MOVED_IDS)") == "{}"
    assert page.locator(LOAD_ERROR_BANNER).count() == 0
    assert "Could not load" not in page.locator("main").inner_text()
    assert errors == []


def test_cla_individual_view_links_to_tfs(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _setup(page)
    page.evaluate("switchToTracker('prosecution'); groupMode = 'individual'; renderEntries();")
    link = page.locator('.also-in-cross[data-tracker="trumpfamily"]').first
    assert "Also in Trump Family: 1 entry" in link.inner_text()
    link.click()
    assert page.evaluate("activeTracker") == "trumpfamily"
    assert page.evaluate("searchTerm") == "Steve Witkoff"
    assert errors == []


def test_cla_individual_view_lists_tfs_only_official(browser, site_url):
    # An official named only in TFS (here via also_officials) gets an empty
    # CLA group head with the same "Also in Trump Family" link.
    page, errors = _goto(browser, site_url, "")
    _setup(page)
    page.evaluate("""() => {
      TRACKERS.trumpfamily.data[0].government_nexus.also_officials =
        [{name: "Zed Fixture-Official", role: "Secretary of Fixtures"}];
    }""")
    page.evaluate("switchToTracker('prosecution'); groupMode = 'individual'; renderEntries();")
    groups = page.locator(".official-group")
    last = groups.last
    assert last.locator(".official-group-name").inner_text() == "Zed Fixture-Official"
    assert last.locator(".official-group-count").inner_text() == "0 entries here"
    assert last.locator(".official-group-body .entry").count() == 0
    link = last.locator('.also-in-cross[data-tracker="trumpfamily"]')
    assert "Also in Trump Family: 1 entry" in link.inner_text()
    link.click()
    assert page.evaluate("activeTracker") == "trumpfamily"
    assert page.evaluate("searchTerm") == "Zed Fixture-Official"
    assert page.locator('.entry[data-entry-id="moved-fx"]').count() == 1
    assert errors == []


def test_cla_individual_view_links_to_tfs_once_public(browser, site_url):
    # Real published data: TFS entries name CLA officials (e.g. Hegseth in also_officials).
    page, errors = _goto(browser, site_url, "")
    page.evaluate("switchToTracker('prosecution'); groupMode = 'individual'; renderEntries();")
    assert page.locator('.also-in-cross[data-tracker="trumpfamily"]').count() > 0
    assert errors == []


def test_cla_individual_view_has_no_tfs_link_while_hidden(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    # Hide in-page to keep testing the mechanism.
    page.evaluate("TRACKERS.trumpfamily.hidden = true; switchToTracker('prosecution'); groupMode = 'individual'; renderEntries();")
    assert page.locator(".official-group").count() > 0
    assert page.locator('.also-in-cross[data-tracker="trumpfamily"]').count() == 0
    assert "entries here" not in page.locator("#entries").inner_text()
    assert errors == []


def test_old_govservices_link_redirects_to_dai(browser, site_url):
    # DAI Phase B: tracker/moved_ids.json records GSR moves as "government-services";
    # the old site link uses the key "govservices".
    page, errors = _goto(browser, site_url, "")
    page.evaluate("""() => {
      const fx = mapDaiEntry({id: "g-fx", title: "Fixture GSR move", category: "removals",
        agencies: ["ICE"], location: {place: "x"}, people: {officials: [], agents: [], affected: []},
        human_toll: {summary: "s", figures: [], caveat: "c"}, status: "Ongoing", sources: []});
      TRACKERS.dai.hidden = false;
      TRACKERS.dai.data = [fx];
      MOVED_IDS = {"g-fx": {from: "government-services", to: "dai", date: "2026-10-18"}};
    }""")
    page.evaluate("location.hash = '#govservices/g-fx'; openEntryFromHash();")
    assert page.evaluate("activeTracker") == "dai"
    assert page.evaluate("location.hash") == "#dai/g-fx"
    assert page.locator('.entry.open[data-entry-id="g-fx"]').count() == 1
    assert errors == []
