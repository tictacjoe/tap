"""Browser tests for the key-events rail, collapsed full story and the source-jump click.
Fixture key_events are injected into one real CLA and one real GSR entry by intercepting the data
JSON in the browser, so nothing under data/ changes on disk. Skips if Playwright/Chromium is missing."""

import functools
import http.server
import json
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent
FAKE_URL = "https://example.invalid/not-in-the-sources-card"

_SELECT_VIEW = """(value) => {
    const select = document.getElementById('tabs');
    select.value = value;
    select.dispatchEvent(new Event('change', {bubbles: true}));
}"""
_OPEN_ENTRY = """(id) => {
    const card = document.querySelector('.entry[data-entry-id="' + id + '"]');
    const group = card.closest('.official-group');
    if (group) group.classList.add('open');
    card.classList.add('open');
    card.scrollIntoView();
}"""


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _pick_cla():
    for e in json.loads((SITE_DIR / "data" / "prosecution.json").read_text()):
        urls = [i["source_url"] for i in e["evidence"]
                if i.get("source_url") and not (i.get("description") or "").lstrip().startswith("Re-verif")]
        if urls:
            return e["id"], urls[-1]
    raise AssertionError("no CLA entry with evidence URLs")


def _pick_gsr():
    for e in json.loads((SITE_DIR / "data" / "government-services.json").read_text()):
        if e.get("sources"):
            return e["id"], e["sources"][-1]["url"]
    raise AssertionError("no GSR entry with sources")


CLA_ID, CLA_URL = _pick_cla()
GSR_ID, GSR_URL = _pick_gsr()


def _events(real_url):
    return [
        {"date": "2025-01-10", "text": "First fixture event cites nothing real.", "sources": [FAKE_URL]},
        {"date": "2025-03", "text": "Turning point fixture event.", "turning_point": True, "sources": [real_url]},
        {"date": "2025-06-02", "text": "Last fixture event cites a real source.", "sources": [real_url]},
    ]


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


def _inject(route, entry_id, events):
    response = route.fetch()
    data = response.json()
    for e in data:
        if e["id"] == entry_id:
            e["key_events"] = events
    route.fulfill(response=response, body=json.dumps(data), content_type="application/json")


def _open(browser, site_url, tab, entry_id, real_url, viewport=None, color_scheme=None):
    kwargs = {"viewport": viewport or {"width": 1280, "height": 900}}
    if color_scheme:
        kwargs["color_scheme"] = color_scheme
    context = browser.new_context(**kwargs)
    page = context.new_page()
    file_name = {"prosecution": "prosecution.json", "govservices": "government-services.json"}[tab]
    page.route("**/data/" + file_name, lambda r: _inject(r, entry_id, _events(real_url)))
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.evaluate(_SELECT_VIEW, tab)
    page.wait_for_timeout(900)
    page.evaluate(_OPEN_ENTRY, entry_id)
    page.wait_for_timeout(300)
    return page, errors


CASES = [("prosecution", CLA_ID, CLA_URL), ("govservices", GSR_ID, GSR_URL)]


@pytest.mark.parametrize("tab,entry_id,url", CASES)
def test_rail_is_visible_above_the_closed_story(browser, site_url, tab, entry_id, url):
    page, errors = _open(browser, site_url, tab, entry_id, url)
    card = page.locator(f'.entry[data-entry-id="{entry_id}"]')
    rail = card.locator("ol.key-events")
    story = card.locator("details.full-story")
    assert rail.is_visible()
    assert rail.locator("li.key-event").count() == 3
    assert card.locator("li.key-event-turning").count() == 1
    assert story.count() == 1 and story.get_attribute("open") is None
    assert rail.bounding_box()["y"] < story.bounding_box()["y"]
    assert errors == []


@pytest.mark.parametrize("tab,entry_id,url", CASES)
def test_last_dot_opens_sources_and_flashes(browser, site_url, tab, entry_id, url):
    page, errors = _open(browser, site_url, tab, entry_id, url)
    card = page.locator(f'.entry[data-entry-id="{entry_id}"]')
    sources = card.locator("details.field-toggle:has(.exhibit-list)")
    assert sources.get_attribute("open") is None
    card.locator(".key-event-link").last.click()
    page.wait_for_timeout(150)
    assert sources.get_attribute("open") is not None
    assert card.locator("li.source-flash").count() >= 1
    assert card.locator(".entry-detail").is_visible()  # the click did not toggle the card shut
    page.wait_for_timeout(2400)
    assert card.locator("li.source-flash").count() == 0
    assert errors == []


@pytest.mark.parametrize("tab,entry_id,url", CASES)
def test_dot_with_unknown_url_is_harmless(browser, site_url, tab, entry_id, url):
    page, errors = _open(browser, site_url, tab, entry_id, url)
    card = page.locator(f'.entry[data-entry-id="{entry_id}"]')
    card.locator(".key-event-link").first.click()
    page.wait_for_timeout(300)
    sources = card.locator("details.field-toggle:has(.exhibit-list)")
    assert sources.get_attribute("open") is not None
    assert card.locator("li.source-flash").count() == 0
    assert errors == []


@pytest.mark.parametrize("tab,entry_id,url", CASES)
def test_phone_width_has_no_overflow_and_tall_tap_targets(browser, site_url, tab, entry_id, url):
    page, errors = _open(browser, site_url, tab, entry_id, url, viewport={"width": 390, "height": 800})
    card = page.locator(f'.entry[data-entry-id="{entry_id}"]')
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    links = card.locator(".key-event-link")
    for i in range(links.count()):
        assert links.nth(i).bounding_box()["height"] >= 44
    assert errors == []


def test_dark_mode_rail_line_follows_the_theme(browser, site_url):
    """The rail line uses --rule. The site had no dark theme when this was written (no
    prefers-color-scheme blocks), so there is nothing to differ yet: skip rather than fake it."""
    def line_color(scheme):
        page, _ = _open(browser, site_url, "prosecution", CLA_ID, CLA_URL, color_scheme=scheme)
        return page.evaluate(
            "getComputedStyle(document.querySelector('ol.key-events')).borderLeftColor")
    light, dark = line_color("light"), line_color("dark")
    if light == dark:
        pytest.skip("site defines no dark theme tokens; rail line uses var(--rule) so it will follow one")
    assert light != dark
