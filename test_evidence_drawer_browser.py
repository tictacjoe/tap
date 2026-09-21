"""Browser tests for the Evidence drawer. The site is served from this repo's own directory on a
free port. The drawer flag is on in index.html, so the tests load the page as shipped. Skips if
Playwright or Chromium is missing."""

import functools
import http.server
import json
import pathlib
import re
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent
FLAG_ON = "evidenceDrawerEnabled: true"
ENTRY_ID = "bondi-tirrell-ethics-jack-smith-purge-2025"
OTHER_ID = "comer-epstein-probe-selective-subpoenas-2025-2026"
# TAP's own dated recheck notes ("Re-verified 2026-08-18: ...", "Re-verification ...") are not
# sources and the drawer does not list them. Same rule as isRecheckNote() in index.html: only a
# description that BEGINS with the word counts.
RECHECK_NOTE = re.compile(r"^\s*Re-verif(?:ied|ication)\b", re.I)

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
    return {e["id"]: sum(1 for item in e["evidence"] if not RECHECK_NOTE.match(item.get("description") or ""))
            for e in entries}


def _open_page(browser, site_url, context_args=None, block_checks=False):
    context = browser.new_context(**(context_args or {"viewport": {"width": 1280, "height": 900}}))
    page = context.new_page()
    assert FLAG_ON in (SITE_DIR / "index.html").read_text(encoding="utf-8"), "the prosecution flag is expected to be on"
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


_CLICK_HEAD_TWICE = """(id) => {
    const head = document.querySelector('.entry[data-entry-id="' + id + '"] .evidence-drawer-head');
    head.click();   // opens the drawer and starts the one fetch
    head.click();   // the reader changes their mind before the file arrives
}"""
_ACTIVE_HEAD = """() => {
    const el = document.activeElement;
    const drawer = el && el.closest ? el.closest('.evidence-drawer') : null;
    return {klass: el ? el.className : "", entry: drawer ? drawer.getAttribute('data-evidence-entry') : ""};
}"""


def _slow_checks_route(page, delay=1.0):
    """Serve the real check file, but a second late, so a test can act during the load."""
    body = (SITE_DIR / "data" / "claim-checks.json").read_text(encoding="utf-8")

    def handler(route):
        time.sleep(delay)
        route.fulfill(status=200, content_type="application/json", body=body)

    page.route("**/data/claim-checks.json", handler)


def test_keyboard_focus_survives_the_first_open(browser, site_url):
    """Opening from the keyboard re-renders the drawer in place; the reader must not be
    left with focus on the document body, unable to press Enter again to close it."""
    page, _, errors = _open_page(browser, site_url)
    page.evaluate(_OPEN_ENTRY, ENTRY_ID)
    drawer = page.locator(f'.entry[data-entry-id="{ENTRY_ID}"] .evidence-drawer')
    drawer.locator(".evidence-drawer-head").focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(1200)
    assert drawer.locator(".evidence-tally").inner_text() != "", "the checks should have loaded and re-rendered"
    focused = page.evaluate(_ACTIVE_HEAD)
    assert focused == {"klass": "evidence-drawer-head", "entry": ENTRY_ID}, focused
    assert drawer.locator(".evidence-drawer-head").get_attribute("aria-expanded") == "true"
    assert errors == []


def test_collapsing_during_the_load_leaves_the_drawer_closed(browser, site_url):
    """The post-load re-render must use the drawer's current state, not force it open."""
    page, _, errors = _open_page(browser, site_url)
    _slow_checks_route(page)
    page.evaluate(_OPEN_ENTRY, ENTRY_ID)
    page.evaluate(_CLICK_HEAD_TWICE, ENTRY_ID)
    drawer = page.locator(f'.entry[data-entry-id="{ENTRY_ID}"] .evidence-drawer')
    assert drawer.locator(".evidence-drawer-head").get_attribute("aria-expanded") == "false"
    page.wait_for_timeout(2500)
    assert drawer.locator(".evidence-tally").inner_text() != "", "the checks should still have loaded"
    assert drawer.locator(".evidence-drawer-head").get_attribute("aria-expanded") == "false"
    assert drawer.locator(".evidence-drawer-body").is_hidden()
    assert errors == []


def test_a_shapeless_response_is_retried_on_the_next_open(browser, site_url):
    """A 200 carrying the wrong JSON must not poison the shared promise for the session."""
    page, requests, errors = _open_page(browser, site_url)
    body = (SITE_DIR / "data" / "claim-checks.json").read_text(encoding="utf-8")
    served = []

    def handler(route):
        served.append(len(served) + 1)
        route.fulfill(status=200, content_type="application/json",
                      body="{}" if len(served) == 1 else body)

    page.route("**/data/claim-checks.json", handler)
    page.evaluate(_OPEN_ENTRY, ENTRY_ID)
    drawer = page.locator(f'.entry[data-entry-id="{ENTRY_ID}"] .evidence-drawer')
    head = drawer.locator(".evidence-drawer-head")
    head.click()
    page.wait_for_timeout(900)
    assert "Check results unavailable right now." in drawer.locator(".evidence-drawer-body").inner_text()
    head.click()            # close
    page.wait_for_timeout(200)
    head.click()            # open again: this must go back to the network
    page.wait_for_timeout(900)
    assert len(served) == 2, served
    assert len(requests) == 2, requests
    assert drawer.locator(".evidence-tally").inner_text() != ""
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
