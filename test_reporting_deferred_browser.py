"""Browser tests for Reporting's deferred load: data/tracker.json (the big uncurated archive) is
fetched only after the curated trackers have rendered, and a failed fetch leaves the curated
tabs working. Served from this repo on a free port; skips without Playwright/Chromium."""

import functools
import http.server
import pathlib
import re
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


_contexts = []


@pytest.fixture(autouse=True)
def _close_contexts():
    """Close every context a test opened, so held routes and pages don't pile up."""
    yield
    while _contexts:
        _contexts.pop().close()


def _new_page(browser):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    _contexts.append(context)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    return page, errors


def test_curated_records_render_while_reporting_is_held(browser, site_url):
    page, errors = _new_page(browser)
    held = []
    page.route("**/data/tracker.json", lambda r: held.append(r))
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_function("curatedLoaded === true", timeout=60000)
    assert page.evaluate("reportingLoaded") is False
    assert page.locator("#headlines-view .headline-row").count() > 0
    assert errors == []
    # Reporting's request arrives after the first render; let it through.
    for _ in range(50):
        if held:
            break
        page.wait_for_timeout(100)
    assert held
    held[0].continue_()
    page.wait_for_function("reportingLoaded === true", timeout=60000)
    assert page.evaluate("TRACKERS.tracker.data.length") > 1000


def test_reporting_is_requested_only_after_curated_data(browser, site_url):
    page, _ = _new_page(browser)
    held, held_p = [], []
    page.route("**/data/tracker.json", lambda r: held.append(r))
    # The boot reads the slim index (data/index/<file>), so that is the file held.
    page.route("**/data/index/prosecution.json", lambda r: held_p.append(r))
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_timeout(1500)
    assert held == []  # curated is still incomplete, so Reporting has not been asked for
    assert held_p
    held_p[0].continue_()
    page.wait_for_function("curatedLoaded === true", timeout=60000)
    for _ in range(50):
        if len(held) == 1:
            break
        page.wait_for_timeout(100)
    assert len(held) == 1
    held[0].continue_()


def test_a_failed_reporting_file_leaves_curated_working(browser, site_url):
    page, _ = _new_page(browser)
    page.route("**/data/tracker.json", lambda r: r.fulfill(status=404, body=""))
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_function("curatedLoaded === true", timeout=60000)
    page.wait_for_function("reportingFailed === true", timeout=60000)
    banner = page.locator("main .regex-error").first.inner_text()
    assert "Could not load: tracker.json (HTTP 404)" in banner
    assert "Other databases are unaffected." in banner
    assert page.locator("#headlines-view .headline-row").count() > 0


# ---- Reporting views wait for the data (Task 3) ----

def _open_held(browser, site_url, fragment=""):
    """Open the site with tracker.json held; returns (page, held, errors). Curated is loaded."""
    page, errors = _new_page(browser)
    held = []
    page.route("**/data/tracker.json", lambda r: held.append(r))
    page.goto(f"{site_url}/index.html" + (f"#{fragment}" if fragment else ""), wait_until="domcontentloaded")
    page.wait_for_function("curatedLoaded === true", timeout=60000)
    return page, held, errors


def _release(page, held):
    for _ in range(50):
        if held:
            break
        page.wait_for_timeout(100)
    assert held
    held[0].continue_()
    page.wait_for_function("reportingLoaded === true", timeout=60000)


def test_reporting_labels_say_loading_then_show_counts(browser, site_url):
    page, held, _ = _open_held(browser, site_url)
    assert page.locator("#feed-tab-reporting").inner_text() == "Reporting feed, uncurated (loading…)"
    assert page.locator('#tabs option[value="tracker"]').text_content() == "Uncurated reporting (loading…)"
    _release(page, held)
    assert re.search(r"\(\d+\)$", page.locator("#feed-tab-reporting").inner_text())
    assert re.search(r"\(\d+\)$", page.locator('#tabs option[value="tracker"]').text_content())


def test_reporting_feed_opened_early_shows_loading_then_rows(browser, site_url):
    page, held, _ = _open_held(browser, site_url)
    page.click("#feed-tab-reporting")
    assert page.locator("#headlines-view").inner_text().strip() == "Loading Reporting…"
    _release(page, held)
    page.wait_for_function("document.querySelectorAll('#headlines-view .headline-row').length > 0", timeout=30000)


def test_reporting_tab_opened_early_shows_loading_then_cards(browser, site_url):
    page, held, _ = _open_held(browser, site_url)
    page.evaluate("selectDatabaseTab('tracker')")
    assert page.locator("#entries").inner_text().strip() == "Loading Reporting…"
    assert "0 of 0" not in page.locator("#count").inner_text()
    _release(page, held)
    page.wait_for_function("document.querySelectorAll('#entries .entry').length > 0", timeout=30000)


def test_reporting_deep_link_before_load_opens_the_card(browser, site_url):
    # Learn a drawn id from an unheld page, as test_reporting_deeplink_browser._ids() does.
    probe, _ = _new_page(browser)
    probe.goto(f"{site_url}/index.html#tracker/x", wait_until="domcontentloaded")
    probe.wait_for_function("reportingLoaded === true", timeout=60000)
    probe.wait_for_selector("#entries .entry[data-entry-id]", timeout=30000)
    rid = probe.evaluate("document.querySelector('#entries .entry[data-entry-id]').dataset.entryId")
    page, held, _ = _open_held(browser, site_url, "tracker/" + rid)
    _release(page, held)
    card = page.locator(f'.entry[data-entry-id="{rid}"]')
    page.wait_for_function("document.querySelector('.entry.deep-linked')", timeout=30000)
    classes = card.get_attribute("class")
    assert "open" in classes and "deep-linked" in classes
    assert page.locator(".deep-link-note").count() == 0


def test_reporting_arrival_keeps_an_open_curated_card(browser, site_url):
    page, held, _ = _open_held(browser, site_url)
    page.evaluate("selectDatabaseTab('deregulation')")
    page.locator(".entry .entry-head").first.click()
    assert "open" in page.locator(".entry").first.get_attribute("class")
    # Really scroll first, so the scrollY comparison below means something.
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(300)
    y = page.evaluate("window.scrollY")
    assert y > 0
    _release(page, held)
    assert "open" in page.locator(".entry").first.get_attribute("class")
    assert page.evaluate("window.scrollY") == y


def test_reporting_failure_shows_a_note_not_a_spinner(browser, site_url):
    page, _ = _new_page(browser)
    page.route("**/data/tracker.json", lambda r: r.fulfill(status=404, body=""))
    page.goto(f"{site_url}/index.html", wait_until="domcontentloaded")
    page.wait_for_function("reportingFailed === true", timeout=60000)
    page.evaluate("selectDatabaseTab('tracker')")
    assert "Reporting couldn't be loaded." in page.locator("#entries").inner_text()
    assert page.locator('#tabs option[value="tracker"]').text_content().endswith("(unavailable)")
    # A deep link while Reporting is unavailable adds no misleading "not on the tab" note.
    page.evaluate("openCardById('no-such-id')")
    assert page.locator(".deep-link-note").count() == 0


def test_global_search_before_reporting_fills_in_on_arrival(browser, site_url):
    """Searching while Reporting is held shows curated hits plus a 'still loading' note;
    when Reporting arrives the same term is re-searched and the note is replaced."""
    page, held, _ = _open_held(browser, site_url)
    page.evaluate("ensureFullEntries()")  # search waits for the full curated entries (phase 3b)
    page.fill("#global-search", "EPA")
    assert "Reporting still loading…" in page.locator("#count").inner_text()
    assert page.locator("#entries .entry").count() > 0
    _release(page, held)
    page.wait_for_function(
        "document.getElementById('count').textContent.includes('in Reporting (uncurated)')",
        timeout=30000)
    count = page.locator("#count").inner_text()
    assert "still loading" not in count
    assert page.input_value("#global-search") == "EPA"


def test_global_search_over_cap_still_says_reporting_is_loading(browser, site_url):
    """A broad term overflows the per-group cap; that count line must still carry the note."""
    page, held, _ = _open_held(browser, site_url)
    page.evaluate("ensureFullEntries()")  # search waits for the full curated entries (phase 3b)
    page.fill("#global-search", "the")
    count = page.locator("#count").inner_text()
    assert "shown of" in count, count
    assert "Reporting still loading…" in count
    _release(page, held)


def test_search_cards_stay_open_when_reporting_arrives(browser, site_url):
    """An expanded curated search-result card must survive Reporting's arrival: the Reporting
    group is appended and the count line updated, without rebuilding the results."""
    page, held, _ = _open_held(browser, site_url)
    page.evaluate("ensureFullEntries()")  # search waits for the full curated entries (phase 3b)
    page.fill("#global-search", "EPA")
    card = page.locator('#entries section[data-group="curated"] .entry').first
    card.locator(".entry-head").click()
    assert "open" in card.get_attribute("class")
    card_id = card.get_attribute("data-entry-id")
    page.mouse.wheel(0, 400)
    page.wait_for_timeout(300)
    _release(page, held)
    page.wait_for_function(
        "document.getElementById('count').textContent.includes('in Reporting (uncurated)')",
        timeout=30000)
    same = page.locator(f'#entries .entry[data-entry-id="{card_id}"]').first
    assert "open" in same.get_attribute("class")
    assert page.locator('#entries section[data-group="reporting"]').count() == 1
    assert "in Reporting (uncurated)" in page.locator("#count").inner_text()
    assert "still loading" not in page.locator("#count").inner_text()
