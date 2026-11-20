"""Possible Illegality view (Task 8, 2026-11-19): the dropdown option, the
#illegality address, the filter/sort/search controls, row click-through to
the entry's home tracker (moved ids included) and Back to the view.

data/illegality.json is written by publish.py and is not committed here, so
each test serves a fixture file through page.route(). The fixture rows point
at REAL published entries (read from data/*.json below), so the join in
buildIllegalityRows() runs against the same data the live page loads.

Server/browser fixtures copied from test_moved_redirect_browser.py; skips
without Playwright/Chromium.
"""

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


def _first(name):
    """The first published entry of one data file (real ids, real glance)."""
    return json.loads((SITE_DIR / "data" / name).read_text(encoding="utf-8"))[0]


# Three real entries from three trackers. Their published status_stage values
# give the default (status) order; the law names below give a different
# order under the Law sort, so a sort change is visible.
PROS = _first("prosecution.json")
DEREG = _first("deregulation.json")
GSR = _first("government-services.json")

LAWS = {
    "apa": {"name": "Administrative Procedure Act", "label": "civil"},
    "bribery": {"name": "Bribery", "cite": "18 U.S.C. 201", "label": "criminal"},
    "ica": {"name": "Impoundment Control Act", "label": "civil"},
}


def _violation(law, who, why):
    return {"law": law, "who": who, "why": why}


SMALL = {
    "version": 1,
    "laws": LAWS,
    "entries": {
        PROS["id"]: [_violation("apa", "Fixture Agency", "Prosecution fixture reason.")],
        DEREG["id"]: [_violation("ica", "Fixture Office", "Searchable zebra reason (site search matches whole words).")],
        GSR["id"]: [_violation("bribery", "Fixture Official", "Criminal fixture reason.")],
    },
    "progress": {"screened": 7, "total": 900},
}


def _fulfill(body):
    # One-argument handler (see test_mobile_overflow.py's note on why).
    return lambda route: route.fulfill(body=json.dumps(body), content_type="application/json")


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


def _goto(browser, site_url, fragment="", data=SMALL, viewport=None):
    """Open the page with `data` served as data/illegality.json (None = 404).
    Collects uncaught page errors AND console errors."""
    if viewport:  # phone: real mobile emulation, as in test_mobile_overflow.py
        ctx = browser.new_context(viewport=viewport, device_scale_factor=3, is_mobile=True, has_touch=True)
    else:
        ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.set_default_timeout(5000)  # fail fast instead of Playwright's 30s
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    if data is None:
        page.route("**/data/illegality.json", lambda route: route.fulfill(status=404, body=""))
    else:
        page.route("**/data/illegality.json", _fulfill(data))
    page.goto(f"{site_url}/index.html" + (f"#{fragment}" if fragment else ""), wait_until="networkidle")
    page.wait_for_timeout(1500)
    return page, errors


# #tabs is visually hidden on the first (Records) screen, so choose a view
# the way test_mobile_overflow.py does: set the value, fire "change".
_SELECT_VIEW = """(value) => {
    const select = document.getElementById('tabs');
    select.value = value;
    select.dispatchEvent(new Event('change', {bubbles: true}));
}"""


def _select_view(page, value):
    page.evaluate(_SELECT_VIEW, value)
    page.wait_for_timeout(200)


def _open_view(page):
    _select_view(page, "illegality")


def _sort_by_header(page, key):
    """Desktop sort: click the column-header button (one-liner rows,
    2026-11-19). The full #ill-sort dropdown is shown only at phone width,
    but stays in sync, so its value is still checked below."""
    page.locator(f'.ill-sort-btn[data-sort="{key}"]').click()
    page.wait_for_timeout(200)


def _row_ids(page):
    return page.eval_on_selector_all(".ill-entry-link", "els => els.map(a => a.dataset.id)")


def test_option_follows_harms_and_shows_rows(browser, site_url):
    page, errors = _goto(browser, site_url)
    values = page.eval_on_selector_all("#tabs option", "os => os.map(o => o.value)")
    texts = page.eval_on_selector_all("#tabs option", "os => os.map(o => o.textContent)")
    i = values.index("illegality")
    assert values[i - 1] == "harms"
    assert texts[i] == "Possible Illegality"
    _open_view(page)
    assert page.evaluate("activeTracker") == "illegality"
    assert page.evaluate("location.hash") == "#illegality"
    assert page.locator(".ill-title").inner_text() == "Possible Illegality"
    assert "Reviewed so far: 7 of 900 entries" in page.locator(".ill-progress").inner_text()
    assert page.locator(".ill-counts").inner_text().startswith("3 entries")
    assert "unchallenged" in page.locator(".ill-counts").inner_text()
    # Default (status) order: Unchallenged first, Reversed or withdrawn last.
    assert _row_ids(page) == [DEREG["id"], PROS["id"], GSR["id"]]
    # The tracker's own controls bar and count are hidden, like Harms.
    assert page.locator("#tab-controls").is_hidden()
    assert errors == []


def test_hash_on_load_opens_view(browser, site_url):
    page, errors = _goto(browser, site_url, "illegality")
    assert page.evaluate("activeTracker") == "illegality"
    assert page.evaluate("location.hash") == "#illegality"
    assert page.locator(".ill-entry-link").count() == 3
    assert page.locator("#tabs").input_value() == "illegality"
    assert errors == []


def test_leaving_view_clears_hash(browser, site_url):
    page, errors = _goto(browser, site_url, "illegality")
    _select_view(page, "harms")
    assert page.evaluate("location.hash") == "#harms"
    _select_view(page, "prosecution")
    assert page.evaluate("location.hash") == ""
    assert errors == []


def test_sort_by_law_reorders(browser, site_url):
    page, errors = _goto(browser, site_url)
    _open_view(page)
    _sort_by_header(page, "law")
    # Administrative Procedure Act, Bribery, Impoundment Control Act.
    assert _row_ids(page) == [PROS["id"], GSR["id"], DEREG["id"]]
    assert page.locator('.ill-sort-btn[data-sort="law"]').get_attribute("aria-pressed") == "true"
    assert page.locator("#ill-sort").input_value() == "law"
    assert errors == []


def test_label_filter_criminal(browser, site_url):
    page, errors = _goto(browser, site_url)
    _open_view(page)
    page.select_option("#ill-label", "criminal")
    assert _row_ids(page) == [GSR["id"]]
    # Header counts describe everything listed, not the filtered subset.
    assert page.locator(".ill-counts").inner_text().startswith("3 entries")
    page.select_option("#ill-tracker", "deregulation")
    assert page.locator(".ill-empty").inner_text() == "No entries match."
    assert errors == []


def test_search_filters_and_keeps_focus(browser, site_url):
    page, errors = _goto(browser, site_url)
    _open_view(page)
    page.click("#ill-search")
    page.keyboard.type("zebra", delay=20)
    assert _row_ids(page) == [DEREG["id"]]
    # Typing kept going into the same box: focus and caret survived re-renders.
    assert page.evaluate("document.activeElement.id") == "ill-search"
    assert page.locator("#ill-search").input_value() == "zebra"
    assert page.evaluate("document.getElementById('ill-search').selectionStart") == 5
    page.keyboard.press("Backspace")
    page.keyboard.type("x", delay=20)
    assert page.locator("#ill-search").input_value() == "zebrx"
    assert page.locator(".ill-empty").inner_text() == "No entries match."
    assert errors == []


def test_row_click_opens_entry_in_home_tracker(browser, site_url):
    page, errors = _goto(browser, site_url)
    _open_view(page)
    page.locator(f'.ill-entry-link[data-id="{PROS["id"]}"]').click()
    page.wait_for_timeout(300)
    assert page.evaluate("activeTracker") == "prosecution"
    assert page.locator(f'.entry.open[data-entry-id="{PROS["id"]}"]').count() == 1
    assert errors == []


def test_moved_id_lands_on_new_tracker(browser, site_url):
    moved = {"version": 1, "laws": LAWS, "entries": {"moved-fx": [_violation("bribery", "W", "Why.")]},
             "progress": {"screened": 1, "total": 1}}
    page, errors = _goto(browser, site_url, data=moved)
    # Same in-page fixture as test_moved_redirect_browser.py's _setup().
    page.evaluate("""() => {
      const fx = mapTrumpFamilyEntry({id: "moved-fx", title: "Fixture", category: "crypto",
        family_members: ["Eric Trump"], business_entity: {name: "World Liberty Financial"},
        government_nexus: {action: "a", official: {name: "Steve Witkoff", role: "Envoy"}},
        financial_stake: {summary: "s", figures: [], caveat: "c"}, status: "Ongoing", sources: [],
        glance: {what: "Moved fixture"}});
      TRACKERS.trumpfamily.hidden = false;
      TRACKERS.trumpfamily.data = [fx];
      MOVED_IDS = {"moved-fx": {from: "prosecution", to: "trumpfamily", date: "2026-10-20"}};
    }""")
    _open_view(page)
    page.locator('.ill-entry-link[data-id="moved-fx"]').click()
    page.wait_for_timeout(300)
    assert page.evaluate("activeTracker") == "trumpfamily"
    assert page.locator('.entry.open[data-entry-id="moved-fx"]').count() == 1
    assert errors == []


def test_back_returns_to_view_at_same_scroll(browser, site_url):
    # 60 real CLA entries so the list is tall enough to scroll.
    pros = json.loads((SITE_DIR / "data" / "prosecution.json").read_text(encoding="utf-8"))[:60]
    big = {"version": 1, "laws": LAWS,
           "entries": {e["id"]: [_violation("apa", "Who " + e["id"], "Why.")] for e in pros},
           "progress": {"screened": 60, "total": 60}}
    page, errors = _goto(browser, site_url, data=big)
    _open_view(page)
    _sort_by_header(page, "law")
    page.evaluate("window.scrollTo(0, 1500)")
    page.wait_for_timeout(200)
    y = page.evaluate("window.scrollY")
    assert y > 1000
    link = page.locator(".ill-entry-link").nth(30)
    link.scroll_into_view_if_needed()
    y = page.evaluate("window.scrollY")
    link.click()
    page.wait_for_timeout(500)
    assert page.evaluate("activeTracker") == "prosecution"
    page.go_back()
    page.wait_for_timeout(500)
    assert page.evaluate("activeTracker") == "illegality"
    assert page.evaluate("location.hash") == "#illegality"
    assert abs(page.evaluate("window.scrollY") - y) <= 2
    # Control choices survive the round trip (module-level illegalityState).
    assert page.locator("#ill-sort").input_value() == "law"
    assert errors == []


def test_missing_file_is_harmless(browser, site_url):
    page, errors = _goto(browser, site_url, data=None)
    assert page.evaluate("JSON.stringify(ILLEGALITY_DATA)") == json.dumps(
        {"version": 1, "laws": {}, "entries": {}, "progress": {"screened": 0, "total": 0}}, separators=(",", ":"))
    assert page.locator(LOAD_ERROR_BANNER).count() == 0
    _open_view(page)
    assert page.locator(".ill-empty").inner_text() == "None listed yet."
    # The 404 itself logs a console resource error; only page errors count here.
    assert [e for e in errors if "404" not in e and "Failed to load resource" not in e] == []


def test_fits_phone_width(browser, site_url):
    page, errors = _goto(browser, site_url, data=SMALL, viewport={"width": 390, "height": 844})
    _open_view(page)
    widths = page.evaluate("[window.innerWidth, document.documentElement.scrollWidth]")
    assert widths == [390, 390]
    assert errors == []


def test_typing_keeps_the_same_search_box(browser, site_url):
    # Review fix: the search box must never be replaced while typing (a
    # replaced box loses the phone keyboard on iOS and breaks Android
    # predictive text). A marker property set before typing must still be on
    # the box in the DOM, and that box must still have focus.
    page, errors = _goto(browser, site_url)
    _open_view(page)
    page.click("#ill-search")
    page.evaluate("document.getElementById('ill-search').__marker = 'same-box'")
    page.keyboard.type("zebra", delay=20)
    assert _row_ids(page) == [DEREG["id"]]
    assert page.evaluate("document.getElementById('ill-search').__marker") == "same-box"
    assert page.evaluate("document.activeElement.__marker") == "same-box"
    assert errors == []


def test_select_change_keeps_focus_on_the_select(browser, site_url):
    # #ill-sort is the phone sort dropdown (one-liner rows, 2026-11-19).
    page, errors = _goto(browser, site_url, viewport={"width": 390, "height": 844})
    _open_view(page)
    page.evaluate("document.getElementById('ill-sort').__marker = 'same-select'")
    page.focus("#ill-sort")
    page.select_option("#ill-sort", "law")
    assert _row_ids(page) == [PROS["id"], GSR["id"], DEREG["id"]]
    assert page.evaluate("document.activeElement.id") == "ill-sort"
    assert page.evaluate("document.activeElement.__marker") == "same-select"
    assert errors == []


def test_wrongly_typed_fields_fall_back_to_empty(browser, site_url):
    # Only top-level fields of the right type are taken from the file.
    bad = {"version": 1, "laws": LAWS, "entries": ["not", "an", "object"],
           "progress": {"screened": "7", "total": 900}}
    page, errors = _goto(browser, site_url, data=bad)
    data = page.evaluate("ILLEGALITY_DATA")
    assert data["entries"] == {}
    assert data["progress"] == {"screened": 0, "total": 0}
    assert data["laws"] == LAWS
    assert page.locator(LOAD_ERROR_BANNER).count() == 0
    assert errors == []
