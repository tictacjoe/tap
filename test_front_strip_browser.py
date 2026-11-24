"""Front-page findings strip (2026-11-23, spec tap-data
docs/superpowers/specs/2026-11-23-front-strip-design.md): placement above
the search box, graceful failure when data/front-strip.json is missing or
broken, the phone tap-to-open line, and both links.

The fixture's featured entry is a REAL published entry (first tier-1
entry with a pull quote in dai.json), so "Read the entry" opens a card
that actually exists. Server/browser fixtures copied from
test_illegality_browser.py; skips without Playwright/Chromium.
"""

import functools
import http.server
import json
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent


def _real_featured():
    for e in json.loads((SITE_DIR / "data" / "dai.json").read_text(encoding="utf-8")):
        harm = (e.get("glance") or {}).get("harm") or {}
        if harm.get("kind") == "physical" and e.get("pull_quote") and harm.get("who"):
            return e
    raise AssertionError("no tier-1 DAI entry with a pull quote")


REAL = _real_featured()
STRIP = {
    "as_of": "2026-11-23",
    "stats": {"entries": 1953, "life_health": 7, "illegality": 6, "reporting": 5},
    "featured": {
        "tracker": "dai", "id": REAL["id"], "label": "DHS and ICE",
        "what": REAL["glance"]["what"], "who": REAL["glance"]["harm"]["who"],
        "status": REAL.get("status_stage", ""), "pull_quote": REAL["pull_quote"],
        "certainty": "documented", "since": "2026-11-23",
    },
    "history": [],
    "featured_illegality": {
        "tracker": "dai", "id": REAL["id"], "label": "DHS and ICE",
        "what": REAL["glance"]["what"], "status": "", "law": "Due process",
        "cite": "U.S. Const. amend. V", "law_label": "civil", "who": "ICE",
        "why": "A judge ruled.", "more_laws": 0, "since": "2026-11-23",
    },
    "history_illegality": [],
}
PHONE = {"width": 390, "height": 844}


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


def _goto(browser, site_url, body="fixture", viewport=None):
    """Open the page. body: "fixture" (STRIP), "real" (no route: the
    committed data/front-strip.json), None (404), or a raw string."""
    if viewport:
        ctx = browser.new_context(viewport=viewport, device_scale_factor=3, is_mobile=True, has_touch=True)
    else:
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(5000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    if body is None:
        page.route("**/data/front-strip.json", lambda route: route.fulfill(status=404, body=""))
    elif body == "fixture":
        page.route("**/data/front-strip.json",
                   lambda route: route.fulfill(body=json.dumps(STRIP), content_type="application/json"))
    elif body != "real":
        page.route("**/data/front-strip.json",
                   lambda route: route.fulfill(body=body, content_type="application/json"))
    page.goto(f"{site_url}/index.html", wait_until="networkidle")
    page.wait_for_timeout(1500)
    return page, errors


def test_strip_renders_above_search(browser, site_url):
    page, errors = _goto(browser, site_url)
    strip = page.locator("#front-strip")
    assert strip.is_visible()
    assert strip.bounding_box()["y"] < page.locator("#search-mode-box").bounding_box()["y"]
    assert page.locator(".fs-num").all_inner_texts() == ["1,953", "7", "6", "5"]
    assert page.locator("#fs-card-harm").is_visible()
    assert page.locator("#fs-card-illegality").is_visible()
    assert not page.locator(".fs-toggle").first.is_visible()  # desktop: no fold line
    assert errors == []


def _search_still_works(page):
    """The rest of the page still loads and searches normally."""
    page.fill("#global-search", "EPA")
    page.wait_for_timeout(800)
    assert page.locator("#entries .entry").count() > 0


@pytest.mark.parametrize("body", [None, "{not json"], ids=["404", "malformed"])
def test_bad_file_leaves_page_unchanged(browser, site_url, body):
    page, errors = _goto(browser, site_url, body=body)
    assert page.locator("#front-strip").is_hidden()
    assert page.locator("#front-strip").inner_html() == ""
    _search_still_works(page)
    assert errors == []


def test_phone_toggle(browser, site_url):
    page, errors = _goto(browser, site_url, viewport=PHONE)
    toggle = page.locator(".fs-feature-harm .fs-toggle")
    card = page.locator("#fs-card-harm")
    other = page.locator("#fs-card-illegality")
    assert page.locator(".fs-feature-illegality .fs-toggle").is_visible()
    assert toggle.is_visible()
    assert card.is_hidden()
    # Nothing in the strip may poke past its own box (phone overflow).
    overflow = page.evaluate("""() => {
        const box = document.querySelector('#front-strip').getBoundingClientRect();
        return [...document.querySelectorAll('#front-strip *')]
          .filter(el => el.getBoundingClientRect().right > box.right + 0.5)
          .map(el => el.className);
    }""")
    assert overflow == []
    toggle.click()
    assert card.is_visible()
    assert other.is_hidden()  # each card folds on its own
    assert toggle.get_attribute("aria-expanded") == "true"
    toggle.click()
    assert card.is_hidden()
    assert toggle.get_attribute("aria-expanded") == "false"
    assert errors == []


def test_entry_link_opens_card(browser, site_url):
    page, errors = _goto(browser, site_url)
    page.locator(".fs-feature-harm .fs-entry-link").click()
    page.wait_for_timeout(800)
    card = page.locator(f'#entries .entry[data-entry-id="{REAL["id"]}"]').first
    assert card.is_visible()
    assert errors == []


def test_harms_link_opens_harms_view_and_counts_match(browser, site_url):
    real = json.loads((SITE_DIR / "data" / "front-strip.json").read_text(encoding="utf-8"))
    page, errors = _goto(browser, site_url, body="real")
    page.locator(".fs-harms-link").click()
    page.wait_for_timeout(800)
    assert page.locator(".harms-list").is_visible()
    # averted rows never happened and are left out of the strip's number
    tier1 = page.locator('.harms-tier[data-tier="1"] .harm-row:not(.harm-line-averted)').count()
    assert tier1 == real["stats"]["life_health"]
    assert errors == []


@pytest.mark.parametrize("goto,selector", [("harms", ".harms-list"), ("illegality", ".ill-view")])
def test_number_links_open_views(browser, site_url, goto, selector):
    page, errors = _goto(browser, site_url)
    page.locator(f'.fs-num-link[data-goto="{goto}"]').click()
    page.wait_for_timeout(800)
    assert page.locator(selector).is_visible()
    assert errors == []


def test_entries_number_opens_all_trackers(browser, site_url):
    page, errors = _goto(browser, site_url)
    page.locator('.fs-num-link[data-goto="all"]').click()
    page.wait_for_timeout(800)
    assert page.locator("#tabs").input_value() == ""  # Records, no single database
    assert page.locator("#entries .entry").count() > 0 or page.locator("#entries").inner_text() != ""
    assert errors == []


def test_illegality_link_opens_view(browser, site_url):
    page, errors = _goto(browser, site_url)
    page.locator(".fs-illegality-link").click()
    page.wait_for_timeout(800)
    assert page.locator(".ill-view").is_visible()
    assert errors == []
