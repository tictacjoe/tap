"""Browser tests for status pills and the staged status filter (UX refresh
spec 5.6).

No published entry carries `status_stage` yet, so with real data the site
must look exactly as it did before: no pills, no new status filters, and
Cabinet-Level keeps its computed "Status Stage" text, `status_category`
filter and "Group by status". The other tests route the real data files
through page.route with `status_stage` added, to show what switches on once
a tracker's backfill is complete. Skips if Playwright or Chromium is missing.
"""

import functools
import http.server
import json
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

STAGES = [
    "Reversed or withdrawn",
    "Court ruled",
    "In court",
    "Finding issued",
    "Under investigation",
    "Unchallenged",
]

# The six curated tracker files (tracker.json, the Reporting archive, is
# never touched).
CURATED_FILES = [
    "prosecution.json",
    "deregulation.json",
    "government-services.json",
    "oea.json",
    "trumpfamily.json",
    "dai.json",
]


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


def _fulfill_with(body):
    # A one-argument handler: Playwright passes (route, request) to a handler
    # that takes two parameters, so a default-argument lambda would get the
    # request as its body.
    return lambda route: route.fulfill(body=body, content_type="application/json")


def inject_status_stage(page, files, stage="Court ruled"):
    """Route each named data file to the real file with `status_stage` set on
    every entry. Shared with test_mobile_overflow.py."""
    for name in files:
        entries = json.loads((SITE_DIR / "data" / name).read_text(encoding="utf-8"))
        for entry in entries:
            entry["status_stage"] = stage
        page.route("**/data/" + name, _fulfill_with(json.dumps(entries)))


def _open(browser, site_url, inject=(), width=1280):
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    inject_status_stage(page, inject)
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(800)
    return page


_SELECT_VIEW = """(value) => {
    const select = document.getElementById('tabs');
    select.value = value;
    select.dispatchEvent(new Event('change', {bubbles: true}));
}"""


def _view(page, key):
    page.evaluate(_SELECT_VIEW, key)
    page.wait_for_timeout(500)


def _option_texts(page, selector):
    return page.eval_on_selector_all(selector + " option", "els => els.map(o => o.textContent.trim())")


def test_no_pill_without_field(browser, site_url):
    page = _open(browser, site_url)
    assert page.locator("#headlines-view .headline-entry").count() > 0
    assert page.locator(".status-pill").count() == 0
    assert not page.locator("#headlines-status-filter").is_visible()

    _view(page, "prosecution")
    assert page.locator("#entries .entry").count() > 0
    assert page.locator(".status-pill").count() == 0
    assert "Status Stage" in page.locator("#entries").inner_text()
    assert not page.locator("#status-filter").is_visible()
    # Cabinet-Level's filter is still the computed status_category one.
    options = _option_texts(page, "#filter")
    assert options[0] == "all statuses"
    assert "Court ruled" not in options
    assert any(o in options for o in ("No Formal Action Taken", "Active Litigation — Pending Ruling"))
    assert page.locator("#status-group-label").is_visible()

    _view(page, "deregulation")
    assert page.locator(".status-pill").count() == 0
    assert not page.locator("#status-filter").is_visible()
    page.context.close()


def test_pills_with_injected_field(browser, site_url):
    page = _open(browser, site_url, inject=["prosecution.json"])

    # Records feed: pills on Cabinet-Level rows only, right after the chip.
    rows = page.eval_on_selector_all(
        "#headlines-view .headline-entry",
        """els => els.map(e => {
            const pill = e.querySelector('.status-pill');
            return [e.dataset.tracker, pill ? pill.textContent.trim() : null,
                    pill ? pill.previousElementSibling.classList.contains('headline-row-tracker') : null];
        })""")
    cla = [r for r in rows if r[0] == "prosecution"]
    other = [r for r in rows if r[0] != "prosecution"]
    assert cla and other
    assert all(r[1] == "⚖ Court ruled" and r[2] for r in cla)
    assert all(r[1] is None for r in other)
    # Not every curated tracker has the field, so the feed filter stays hidden.
    assert not page.locator("#headlines-status-filter").is_visible()

    _view(page, "prosecution")
    cards = page.locator("#entries .entry")
    assert cards.count() > 0
    pills = page.eval_on_selector_all(
        "#entries .entry .entry-title",
        """els => els.map(t => {
            const pill = t.querySelector('.status-pill');
            return pill ? [pill.textContent.trim(), pill.previousElementSibling
                && pill.previousElementSibling.classList.contains('tracker-chip')] : null;
        })""")
    assert pills and all(p == ["⚖ Court ruled", True] for p in pills)
    assert "Status Stage" not in page.locator("#entries").inner_text()

    # The existing filter switches to status_stage, all six in order; no
    # second status dropdown next to it.
    assert _option_texts(page, "#filter") == ["all statuses"] + STAGES
    assert not page.locator("#status-filter").is_visible()
    page.select_option("#filter", "Court ruled")
    page.wait_for_timeout(300)
    assert page.locator("#entries .entry").count() == cards.count()
    page.select_option("#filter", "In court")
    page.wait_for_timeout(300)
    assert page.locator("#entries .entry").count() == 0
    page.select_option("#filter", "")
    page.wait_for_timeout(300)

    # Group by status groups on status_stage.
    page.locator("#status-group-toggle").check()
    page.wait_for_timeout(500)
    names = page.eval_on_selector_all(".official-group-name", "els => els.map(e => e.textContent.trim())")
    assert names == ["Court ruled"]

    # Another tracker without the field: unchanged.
    _view(page, "deregulation")
    assert page.locator("#entries .status-pill").count() == 0
    assert not page.locator("#status-filter").is_visible()
    page.context.close()


def test_status_filters_when_every_tracker_has_field(browser, site_url):
    page = _open(browser, site_url, inject=CURATED_FILES)

    # Records feed: the third control appears, with all six stages.
    sel = page.locator("#headlines-status-filter")
    assert sel.is_visible()
    assert _option_texts(page, "#headlines-status-filter") == ["All statuses"] + STAGES
    before = page.locator("#headlines-view .headline-entry").count()
    assert before > 0
    assert page.locator("#headlines-view .headline-entry .status-pill").count() == before
    page.select_option("#headlines-status-filter", "In court")
    page.wait_for_timeout(500)
    assert page.locator("#headlines-view .headline-entry").count() == 0
    page.select_option("#headlines-status-filter", "Court ruled")
    page.wait_for_timeout(500)
    assert page.locator("#headlines-view .headline-entry").count() == before

    # A domain-filtered tracker gets its own status dropdown next to the
    # domain one.
    _view(page, "deregulation")
    assert page.locator("#status-filter").is_visible()
    assert _option_texts(page, "#status-filter") == ["All statuses"] + STAGES
    n = page.locator("#entries .entry").count()
    assert n > 0
    assert page.locator("#entries .entry .status-pill").count() == n
    page.select_option("#status-filter", "Unchallenged")
    page.wait_for_timeout(300)
    assert page.locator("#entries .entry").count() == 0
    page.select_option("#status-filter", "")
    page.wait_for_timeout(300)
    assert page.locator("#entries .entry").count() == n

    # Global search: curated cards carry the pill too.
    page.fill("#global-search", "rule")
    page.wait_for_timeout(800)
    curated = page.locator("section.search-group").first
    assert curated.locator(".entry").count() > 0
    assert curated.locator(".entry .status-pill").count() == curated.locator(".entry").count()
    page.context.close()


def test_rows_use_compact_pills_at_phone_width(browser, site_url):
    page = _open(browser, site_url, inject=["prosecution.json"], width=400)
    compact = page.eval_on_selector_all(
        "#headlines-view .headline-entry[data-tracker='prosecution'] .status-pill",
        "els => els.map(e => [e.textContent.trim(), e.getAttribute('aria-label'), e.getAttribute('title')])")
    assert compact
    assert all(c == ["⚖", "Court ruled", "Court ruled"] for c in compact)
    page.context.close()
