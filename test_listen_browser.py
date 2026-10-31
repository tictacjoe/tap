"""Browser tests for the Listen button and its player bar (spec:
tap-data/docs/superpowers/specs/2026-10-31-tap-entry-listen-button-design.md).
The site is served from this repo's own directory on a free port. Real speech
can't be heard or checked in a headless browser, so an init script swaps in a
fake speechSynthesis that records every utterance it is handed and never
finishes one on its own -- the reading stays "in progress" for as long as the
test needs. A second variant removes speech entirely, as on a browser without
it. Skips if Playwright or Chromium is missing."""

import functools
import http.server
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

_FAKE_SPEECH = """(() => {
    window.__spoken = [];
    window.__cancels = 0;
    window.SpeechSynthesisUtterance = function (text) { this.text = text; };
    const synth = {
        speaking: false, pending: false, paused: false,
        speak(u) { window.__spoken.push(u.text); this.speaking = true; },
        cancel() { window.__cancels++; this.speaking = false; },
        pause() { this.paused = true; },
        resume() { this.paused = false; },
        getVoices() { return []; },
        addEventListener() {},
    };
    Object.defineProperty(window, 'speechSynthesis', { value: synth, configurable: true });
})();"""

_NO_SPEECH = """(() => {
    Object.defineProperty(window, 'speechSynthesis', { value: undefined, configurable: true });
    Object.defineProperty(window, 'SpeechSynthesisUtterance', { value: undefined, configurable: true });
})();"""

_SELECT_VIEW = """(value) => {
    const select = document.getElementById('tabs');
    select.value = value;
    select.dispatchEvent(new Event('change', {bubbles: true}));
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


def _open(browser, site_url, view="prosecution", speech=True, viewport=None):
    context = browser.new_context(viewport=viewport or {"width": 1280, "height": 900})
    context.add_init_script(_FAKE_SPEECH if speech else _NO_SPEECH)
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.evaluate(_SELECT_VIEW, view)
    page.wait_for_timeout(900)
    return page, errors


def _listen_buttons(page):
    return page.locator(".entry .listen-btn")


def test_listen_starts_reading_and_shows_bar(browser, site_url):
    page, errors = _open(browser, site_url)
    assert page.locator("#listen-bar").is_hidden()
    _listen_buttons(page).first.click()
    bar = page.locator("#listen-bar")
    assert bar.is_visible()
    assert bar.locator(".listen-bar-section").inner_text() == "At a glance"
    assert bar.locator(".listen-bar-title").inner_text().strip() != ""
    assert "Keep your screen on while listening." in bar.locator(".listen-bar-note").inner_text()
    assert page.evaluate("window.__spoken[0]").startswith("Cabinet-Level Accountability.")
    assert page.evaluate("document.body.classList.contains('listen-active')")
    assert errors == []


def test_listen_click_does_not_toggle_card(browser, site_url):
    page, _ = _open(browser, site_url)
    btn = _listen_buttons(page).first
    card = btn.locator("xpath=ancestor::*[contains(concat(' ', @class, ' '), ' entry ')][1]")
    before = "open" in (card.get_attribute("class") or "").split()
    btn.click()
    after = "open" in (card.get_attribute("class") or "").split()
    assert before == after


def test_reading_survives_tab_switch(browser, site_url):
    page, _ = _open(browser, site_url)
    _listen_buttons(page).first.click()
    cancels = page.evaluate("window.__cancels")
    page.evaluate(_SELECT_VIEW, "deregulation")
    page.wait_for_timeout(600)
    assert page.locator("#listen-bar").is_visible()
    assert page.evaluate("window.__cancels") == cancels


def test_next_and_stop(browser, site_url):
    page, _ = _open(browser, site_url)
    _listen_buttons(page).first.click()
    section = page.locator("#listen-bar .listen-bar-section")
    first = section.inner_text()
    page.locator("#listen-bar .listen-next").click()
    assert section.inner_text() != first
    toggle = page.locator("#listen-bar .listen-toggle")
    assert toggle.inner_text() == "Pause"
    toggle.click()
    assert toggle.inner_text() == "Resume"
    page.locator("#listen-bar .listen-stop").click()
    assert page.locator("#listen-bar").is_hidden()
    assert not page.evaluate("document.body.classList.contains('listen-active')")


def test_second_entry_replaces_first(browser, site_url):
    page, _ = _open(browser, site_url)
    buttons = _listen_buttons(page)
    buttons.nth(0).click()
    title = page.locator("#listen-bar .listen-bar-title")
    first_title = title.inner_text()
    cancels = page.evaluate("window.__cancels")
    buttons.nth(1).click()
    assert title.inner_text() != first_title
    assert page.evaluate("window.__cancels") > cancels


def test_same_entry_button_toggles_pause(browser, site_url):
    page, _ = _open(browser, site_url)
    btn = _listen_buttons(page).first
    btn.click()
    count = page.evaluate("window.__spoken.length")
    btn.click()
    assert page.locator("#listen-bar .listen-toggle").inner_text() == "Resume"
    assert page.evaluate("window.__spoken.length") == count


def test_no_button_without_speech(browser, site_url):
    page, errors = _open(browser, site_url, speech=False)
    assert page.locator(".entry").count() > 0
    assert _listen_buttons(page).count() == 0
    assert errors == []


def test_no_button_on_reporting(browser, site_url):
    page, _ = _open(browser, site_url, view="tracker")
    assert page.locator(".entry").count() > 0
    assert _listen_buttons(page).count() == 0


def test_bar_fits_phone_width(browser, site_url):
    page, _ = _open(browser, site_url, viewport={"width": 390, "height": 844})
    _listen_buttons(page).first.click()
    assert page.locator("#listen-bar").is_visible()
    assert page.evaluate("document.documentElement.scrollWidth <= document.documentElement.clientWidth")
    box = page.locator("#listen-bar").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390
