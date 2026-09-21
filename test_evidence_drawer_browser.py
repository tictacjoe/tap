"""Browser tests for the Evidence drawer. The site is served from this repo's own directory on a
free port; the drawer flag is off in index.html, so each test serves a copy of the page with the
Cabinet-Level flag flipped on (index.html itself is not touched). Skips if Playwright or Chromium
is missing."""

import functools
import http.server
import json
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent
FLAG_OFF = "evidenceDrawerEnabled: false"
FLAG_ON = "evidenceDrawerEnabled: true"
ENTRY_ID = "bondi-tirrell-ethics-jack-smith-purge-2025"
OTHER_ID = "comer-epstein-probe-selective-subpoenas-2025-2026"

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


def _entry_evidence_counts():
    entries = json.loads((SITE_DIR / "data" / "prosecution.json").read_text())
    return {e["id"]: len(e["evidence"]) for e in entries}


def _open_page(browser, site_url, context_args=None, block_checks=False):
    context = browser.new_context(**(context_args or {"viewport": {"width": 1280, "height": 900}}))
    page = context.new_page()
    original = (SITE_DIR / "index.html").read_text(encoding="utf-8")
    assert FLAG_OFF in original, "the prosecution flag line changed; update this test"
    flipped = original.replace(FLAG_OFF, FLAG_ON, 1)
    page.route("**/index.html", lambda route: route.fulfill(body=flipped, content_type="text/html"))
    requests = []
    page.on("request", lambda r: requests.append(r.url) if "claim-checks.json" in r.url else None)
    if block_checks:
        page.route("**/data/claim-checks.json", lambda route: route.abort())
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.evaluate(_SELECT_VIEW, "prosecution")
    page.wait_for_timeout(900)
    return page, requests, errors


def test_the_drawer_is_collapsed_and_fetches_nothing_until_opened(browser, site_url):
    page, requests, errors = _open_page(browser, site_url)
    page.evaluate(_OPEN_ENTRY, ENTRY_ID)
    drawer = page.locator(f'.entry[data-entry-id="{ENTRY_ID}"] .evidence-drawer')
    assert drawer.count() == 1
    expected = _entry_evidence_counts()[ENTRY_ID]
    assert drawer.locator(".evidence-drawer-title").inner_text() == f"Evidence · {expected} items"
    assert drawer.locator(".evidence-drawer-body").is_hidden()
    assert drawer.locator(".evidence-tally").inner_text() == ""
    assert requests == []
    assert errors == []


def test_opening_loads_the_checks_once_and_shows_states_and_a_tally(browser, site_url):
    page, requests, errors = _open_page(browser, site_url)
    page.evaluate(_OPEN_ENTRY, ENTRY_ID)
    drawer = page.locator(f'.entry[data-entry-id="{ENTRY_ID}"] .evidence-drawer')
    drawer.locator(".evidence-drawer-head").click()
    page.wait_for_timeout(900)
    expected = _entry_evidence_counts()[ENTRY_ID]
    assert drawer.locator(".evidence-drawer-head").get_attribute("aria-expanded") == "true"
    assert drawer.locator(".evidence-drawer-body").is_visible()
    assert drawer.locator(".evidence-item").count() == expected
    assert drawer.locator(".evidence-tally").inner_text() != ""
    assert drawer.locator(".evidence-badge").count() == expected
    # a second drawer reuses the same fetch
    page.evaluate(_OPEN_ENTRY, OTHER_ID)
    other = page.locator(f'.entry[data-entry-id="{OTHER_ID}"] .evidence-drawer')
    other.locator(".evidence-drawer-head").click()
    page.wait_for_timeout(600)
    assert len(requests) == 1
    assert errors == []


def test_when_the_check_file_fails_the_items_still_list(browser, site_url):
    page, _, errors = _open_page(browser, site_url, block_checks=True)
    page.evaluate(_OPEN_ENTRY, ENTRY_ID)
    drawer = page.locator(f'.entry[data-entry-id="{ENTRY_ID}"] .evidence-drawer')
    drawer.locator(".evidence-drawer-head").click()
    page.wait_for_timeout(900)
    expected = _entry_evidence_counts()[ENTRY_ID]
    assert "Check results unavailable right now." in drawer.locator(".evidence-drawer-body").inner_text()
    assert drawer.locator(".evidence-item").count() == expected
    assert errors == []


def test_an_open_drawer_does_not_overflow_a_phone(browser, site_url):
    args = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True}
    page, _, errors = _open_page(browser, site_url, context_args=args)
    page.evaluate(_OPEN_ENTRY, ENTRY_ID)
    drawer = page.locator(f'.entry[data-entry-id="{ENTRY_ID}"] .evidence-drawer')
    drawer.locator(".evidence-drawer-head").click()
    page.wait_for_timeout(900)
    measure = page.evaluate("() => ({w: window.innerWidth, s: document.documentElement.scrollWidth})")
    assert measure["w"] == 390 and measure["s"] <= measure["w"], measure
    assert errors == []


def test_the_drawer_works_in_the_global_search_one_liner_list(browser, site_url):
    """The 1-liners checkbox belongs to the global search box, so one-liner mode is reached by
    searching (not from a per-tracker tab). A Cabinet-Level row expanded there must get a
    working drawer too."""
    page, _, errors = _open_page(browser, site_url)
    page.check("#global-oneliner")
    page.fill("#global-search", "Tirrell")
    page.wait_for_timeout(900)
    detail = page.locator(f'.oneliner-detail:has(.evidence-drawer[data-evidence-entry="{ENTRY_ID}"])')
    assert detail.count() == 1
    # expand the row that owns this detail (the row is the detail's previous sibling)
    detail.evaluate("el => el.previousElementSibling.click()")
    drawer = detail.locator(".evidence-drawer")
    drawer.scroll_into_view_if_needed()
    drawer.locator(".evidence-drawer-head").click()
    page.wait_for_timeout(900)
    expected = _entry_evidence_counts()[ENTRY_ID]
    assert drawer.locator(".evidence-drawer-head").get_attribute("aria-expanded") == "true"
    assert drawer.locator(".evidence-drawer-body").is_visible()
    assert drawer.locator(".evidence-item").count() == expected
    assert errors == []
