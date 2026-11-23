"""Browser tests for the top bar that replaced the floating side buttons.
Serves this repo's directory on a free port; page.route stubs
data/site_meta.json. Skips if Playwright or Chromium is missing."""

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


def _open(browser, site_url, meta=None):
    """meta: JSON body for site_meta.json, or None to answer 404."""
    context = browser.new_context(viewport={"width": 1280, "height": 900})
    page = context.new_page()
    if meta is None:
        page.route("**/data/site_meta.json", lambda r: r.fulfill(status=404, body="nope"))
    else:
        page.route(
            "**/data/site_meta.json",
            lambda r: r.fulfill(status=200, content_type="application/json", body=meta),
        )
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(800)
    return page


def test_top_bar_links(browser, site_url):
    page = _open(browser, site_url, '{"updated":"2026-11-01"}')
    assert page.get_attribute("#top-bar-about", "href").endswith("about.html")
    assert page.locator(".nav-actions").count() == 0
    for sel in ("#start-over-btn", "#suggest-claim-link"):
        assert page.locator(f"#top-bar {sel}").count() == 1
    # Back to Top left the bar for a floating button (2026-11-20).
    assert page.locator("#top-bar #back-to-top-btn").count() == 0
    assert page.locator("#suggest-claim-link").inner_text().strip().endswith("Suggest a topic")
    page.click("#suggest-claim-link")
    assert page.locator("#suggest-backdrop").is_visible()


def test_top_bar_shows_updated_date(browser, site_url):
    page = _open(browser, site_url, '{"updated":"2026-11-01"}')
    assert page.locator("#top-bar-updated").inner_text() == "Updated Nov 1, 2026"


def test_top_bar_without_site_meta(browser, site_url):
    page = _open(browser, site_url, None)
    assert page.locator("#top-bar-updated").inner_text() == ""
    text = page.locator("#top-bar").inner_text()
    assert "Invalid" not in text and "undefined" not in text


def test_top_bar_sticks_and_drops_the_date_when_scrolled(browser, site_url):
    # 2026-11-20 (Joe): sticky bar; scrolled, it hides the Updated date.
    page = _open(browser, site_url, '{"updated":"2026-11-01"}')
    page.mouse.wheel(0, 2500)
    page.wait_for_timeout(600)
    assert page.locator("#top-bar").bounding_box()["y"] == 0
    assert page.locator("#top-bar #start-over-btn").is_visible()
    assert not page.locator("#top-bar-updated").is_visible()


def test_floating_back_to_top_appears_after_scrolling(browser, site_url):
    page = _open(browser, site_url, '{"updated":"2026-11-01"}')
    fab = page.locator("#back-to-top-btn")
    assert not fab.is_visible()
    page.mouse.wheel(0, 2500)
    page.wait_for_timeout(600)
    assert fab.is_visible()
    fab.click()
    page.wait_for_timeout(1200)
    assert page.evaluate("window.scrollY") == 0
    assert not fab.is_visible()


def test_subscribe_link_points_at_feed_and_fits_on_phone(browser, site_url):
    # Subscribe link (2026-11-23): top-bar link to the RSS feed (feed.xml,
    # written by publish.py via feed.py).
    page = _open(browser, site_url, '{"updated":"2026-11-01"}')
    link = page.locator("#top-bar #top-bar-subscribe")
    assert link.count() == 1
    assert link.get_attribute("href") == "feed.xml"
    assert link.inner_text().strip() == "Subscribe"
    assert "RSS" in (link.get_attribute("title") or "")
    # Phone: every top-bar item stays inside the 390px screen.
    ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    phone = ctx.new_page()
    phone.goto(site_url + "/index.html", wait_until="networkidle")
    phone.wait_for_timeout(800)
    assert phone.locator("#top-bar-subscribe").is_visible()
    widest = phone.evaluate("""() => Math.max(...[...document.querySelectorAll('#top-bar *')]
        .map(el => el.getBoundingClientRect().right))""")
    assert widest <= 390
    ctx.close()
