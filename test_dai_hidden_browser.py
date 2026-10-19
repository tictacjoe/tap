"""Hidden DHS and ICE tracker (tap-data spec
docs/superpowers/specs/2026-10-18-tap-dai-tracker-design.md): no tab, no
browse option, no Headlines row, no global-search hit, deep link inert, no
CLA "Also in DHS and ICE" link; flipping hidden shows the tab with a fixture
entry grouped per agency, its People card, and the CLA cross-view link.
Served from this repo on a free port; skips without Playwright/Chromium."""

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
    "id": "dai-fixture", "title": "Fixture Broadview shooting", "category": "use_of_force",
    "agencies": ["Border Patrol", "ICE"], "location": {"place": "Broadview, Illinois"},
    "people": {
        "officials": [{"name": "Zed Fixture-Commander", "role": "Border Patrol commander",
                       "sources": ["https://a.example/1"]}],
        "agents": [{"name": "Agent Fixture", "role": "Border Patrol agent", "incident_role": "fired",
                    "sources": ["https://a.example/1", "https://b.example/2"]}],
        "affected": [{"name": "Person Fixture", "description": "U.S. citizen shot",
                      "sources": ["https://a.example/1"]}],
    },
    "legal_status": "",
    "human_toll": {"summary": "One person shot", "figures": [], "caveat": "c"},
    "date_of_action": "2026-01-01", "date_added": "2026-10-18", "status": "Under investigation",
    "sources": [{"name": "A", "url": "https://a.example/1"}, {"name": "B", "url": "https://b.example/2"}],
}


def _inject(page):
    page.evaluate("""(fx) => { TRACKERS.dai.data = [mapDaiEntry(fx)]; }""", FIXTURE)


def test_dai_is_hidden_on_load(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    assert page.evaluate("TRACKERS.dai.hidden") is True
    assert page.evaluate("Array.isArray(TRACKERS.dai.data)") is True
    assert errors == []


def test_hidden_dai_has_no_tab_browse_headlines_or_search_hit(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _inject(page)
    page.evaluate("renderTabs(); renderHeadlinesControls()")
    assert page.locator('#tabs option[value="dai"]').count() == 0
    assert page.locator('#headlines-tracker-filter option[value="dai"]').count() == 0
    assert page.evaluate("buildHeadlineItems().filter(i => i.tracker === 'dai').length") == 0
    page.evaluate("openBrowseModal()")
    browse = page.locator("#browse-options .browse-option-btn").all_inner_texts()
    assert browse and not any("DHS and ICE" in t for t in browse)
    page.evaluate("closeBrowseModal()")
    page.fill("#global-search", "Fixture Broadview")
    page.wait_for_timeout(300)
    assert page.locator('#entries .entry[data-entry-id="dai-fixture"]').count() == 0
    assert "DHS and ICE" not in page.locator("#entries").inner_text()
    assert errors == []


def test_hidden_dai_deep_link_is_inert(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _inject(page)
    page.evaluate("""() => { history.replaceState(null, '', '#dai/dai-fixture'); openEntryFromHash(); }""")
    assert page.evaluate("activeTracker") != "dai"
    assert errors == []


def test_hidden_dai_adds_no_cla_cross_view_link(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _inject(page)
    page.evaluate("switchToTracker('prosecution'); groupMode = 'individual'; renderEntries();")
    assert page.locator('.also-in-cross[data-tracker="dai"]').count() == 0
    assert "Zed Fixture-Commander" not in page.locator("#entries").inner_text()
    assert errors == []


def test_unhidden_dai_shows_tab_groups_people_and_cross_view(browser, site_url):
    page, errors = _goto(browser, site_url, "")
    _inject(page)
    page.evaluate("TRACKERS.dai.hidden = false; renderTabs(); switchToTracker('dai');")
    assert page.locator('#tabs option[value="dai"]').count() == 1
    page.select_option("#group-mode", "agency")
    heads = page.locator(".official-group-name").all_inner_texts()
    assert sorted(heads) == ["Border Patrol", "ICE"]
    page.select_option("#group-mode", "")
    card = page.locator('.entry[data-entry-id="dai-fixture"]').first
    card.locator(".entry-head").first.click()
    page.wait_for_timeout(200)
    text = card.inner_text().lower()  # field labels are uppercased by CSS
    for needle in ("Officials", "Agents", "Affected", "Agent Fixture", "Person Fixture", "Human toll"):
        assert needle.lower() in text, needle
    assert card.locator('a[href="https://a.example/1"]', has_text="Person Fixture").count() == 1
    # CLA "List by individual" now links the DAI-only official.
    page.evaluate("switchToTracker('prosecution'); groupMode = 'individual'; renderEntries();")
    link = page.locator('.also-in-cross[data-tracker="dai"]').last
    assert "Also in DHS and ICE: 1 entry" in link.inner_text()
    link.click()
    assert page.evaluate("activeTracker") == "dai"
    assert page.evaluate("searchTerm") == "Zed Fixture-Commander"
    assert errors == []
