"""Browser tests for tracker colors: chips on Records rows, left borders on
curated cards. Skips if Playwright or Chromium is missing."""

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


def _open(browser, site_url):
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(800)
    return page


def test_rows_have_tracker_chips(browser, site_url):
    page = _open(browser, site_url)
    counts = page.eval_on_selector_all(
        "#headlines-view .headline-entry",
        "els => els.map(e => e.querySelectorAll('.tracker-chip').length)")
    assert counts and all(c == 1 for c in counts)
    # The chip carries the tracker name as text, not color alone.
    texts = page.eval_on_selector_all(
        "#headlines-view .headline-entry .tracker-chip", "els => els.map(e => e.textContent.trim())")
    assert all(texts)

    page.locator("#feed-tab-reporting").click()
    page.wait_for_timeout(500)
    rows = page.locator("#headlines-view .headline-entry")
    assert rows.count() > 0
    assert page.locator("#headlines-view .tracker-chip").count() == 0
    label = page.locator("#headlines-view .headline-row-tracker").first.inner_text()
    assert "reporting" in label.lower()


COLORS = {
    "prosecution": "rgb(122, 63, 143)",
    "govservices": "rgb(0, 132, 106)",
    "deregulation": "rgb(176, 86, 26)",
    "dai": "rgb(52, 98, 176)",
    "trumpfamily": "rgb(163, 48, 63)",
    "oea": "rgb(138, 122, 10)",
}


@pytest.mark.parametrize("key", list(COLORS))
def test_cards_have_left_border_and_chip(browser, site_url, key):
    page = _open(browser, site_url)
    page.evaluate(f"goToTrackerHome('{key}')")
    page.wait_for_timeout(800)
    card = page.locator(".entry.curated-card").first
    if card.count() == 0:
        pytest.skip(f"no {key} entries loaded")
    assert card.evaluate("e => getComputedStyle(e).borderLeftColor") == COLORS[key]
    assert card.evaluate("e => getComputedStyle(e).borderLeftWidth") == "6px"
    chip = card.locator(".tracker-chip")
    assert chip.count() == 1
    assert chip.evaluate("e => getComputedStyle(e).backgroundColor") == COLORS[key]
    assert chip.evaluate("e => e.textContent.trim()")
    assert chip.evaluate("e => getComputedStyle(e).color") == (
        "rgb(0, 0, 0)" if key == "oea" else "rgb(255, 255, 255)")
    # Chip leads the header line.
    assert card.locator(".entry-title").first.evaluate(
        "e => e.firstElementChild.classList.contains('tracker-chip')")


def test_search_result_cards_have_chip(browser, site_url):
    page = _open(browser, site_url)
    page.fill("#global-search", "the")
    page.dispatch_event("#global-search", "input")
    page.wait_for_timeout(1200)
    cards = page.locator(".search-group .entry.curated-card")
    assert cards.count() > 0
    assert cards.first.locator(".tracker-chip").count() == 1
    assert page.locator(".search-group .entry:not(.curated-card) .tracker-chip").count() == 0


@pytest.mark.parametrize("key", ["deregulation", "govservices"])
def test_domain_tags_neutral(browser, site_url, key):
    page = _open(browser, site_url)
    # Glance cards carry no domain tag, so draw the old-style card (the one
    # that still shows it) from a real entry with glanceEnabled switched off.
    html = page.evaluate("""key => {
        const cfg = Object.assign({}, TRACKERS[key], { glanceEnabled: false });
        const entry = cfg.data.find(e => e.domain);
        if (!entry) return null;
        const card = buildEntryCard(entry, cfg, "", "", "", false, {});
        document.body.appendChild(card);
        return card.querySelector('.domain-tag') ? 'ok' : 'no-tag';
    }""", key)
    assert html == "ok"
    tag = page.locator(".entry .domain-tag").last
    style = lambda prop: tag.evaluate(f"e => getComputedStyle(e).{prop}")
    assert style("backgroundColor") == "rgba(0, 0, 0, 0)"
    assert style("color") == "rgb(29, 34, 32)"
    assert style("borderTopWidth") == "1px"
    assert style("borderTopColor") == "rgb(169, 172, 154)"
    # Category is not a color: no domain tag carries inline background/color.
    assert page.locator(".domain-tag[style*='background']").count() == 0
