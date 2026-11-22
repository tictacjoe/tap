"""Browser tests for the sortable column labels on curated tracker row lists
(Joe, 2026-11-22). Clicking Updated, Status, Entry or Harm to sorts the list
by that column; a second click reverses it; the sort dropdown shows the
active column sort, and picking another dropdown sort clears it. The site is
served from this repo's own directory on a free port. Skips if Playwright or
Chromium is missing."""

import functools
import http.server
import pathlib
import re
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent

# Each row's sortable values, read straight from the drawn rows.
_ROWS = """() => [...document.querySelectorAll('#entries .entry-rowmode')].map(r => ({
  updated: r.querySelector('.entry-row-date').textContent,
  status: (r.querySelector('.status-pill') || {className: ''}).className,
  harm: r.querySelector('.entry-row-harm').textContent.trim(),
}))"""

# Stage order (STATUS_STAGES), as status-pill classes.
_STAGE_CLASSES = ["s-rev", "s-ruled", "s-court", "s-find", "s-inv", "s-none"]


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


def _open(browser, site_url, key="govservices"):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(site_url + "/index.html", wait_until="networkidle")
    page.wait_for_timeout(1200)
    page.evaluate(f"goToTrackerHome('{key}')")
    page.wait_for_timeout(800)
    if page.locator("#entries .entry-rowmode").count() < 2:
        pytest.skip(f"not enough {key} entries loaded")
    return page


def _sort(page, key):
    page.click(f'#entries .entry-row-sort[data-sort="{key}"]')
    page.wait_for_timeout(300)
    return page.evaluate(_ROWS)


def _stage(cls):
    return next((i for i, c in enumerate(_STAGE_CLASSES) if c in cls.split()), len(_STAGE_CLASSES))


def test_updated_sorts_newest_first_then_reverses(browser, site_url):
    page = _open(browser, site_url)
    dates = [r["updated"] for r in _sort(page, "updated")]
    assert dates == sorted(dates, reverse=True)
    btn = page.locator('#entries .entry-row-sort[data-sort="updated"]')
    assert btn.get_attribute("aria-pressed") == "true"
    assert btn.inner_text().endswith("▼")
    dates = [r["updated"] for r in _sort(page, "updated")]
    assert dates == sorted(dates)
    assert page.locator('#entries .entry-row-sort[data-sort="updated"]').inner_text().endswith("▲")
    page.close()


def test_status_sorts_in_stage_order(browser, site_url):
    page = _open(browser, site_url)
    stages = [_stage(r["status"]) for r in _sort(page, "status")]
    assert stages == sorted(stages)
    page.close()


def test_harm_sorts_alphabetically_ignoring_leading_symbols(browser, site_url):
    page = _open(browser, site_url)
    harms = [r["harm"] for r in _sort(page, "harm")]
    # The page sorts with localeCompare, so compare first characters only
    # (Python's ordering of punctuation inside the text differs).
    firsts = [re.sub(r"^[^a-z0-9]+", "", h.lower())[:1] for h in harms if h]
    assert firsts == sorted(firsts)
    assert harms[0][:1] != "~"  # "~42 million" sorts as "42 million"
    page.close()


def test_dropdown_shows_column_sort_and_clears_it(browser, site_url):
    page = _open(browser, site_url)
    _sort(page, "entry")
    assert page.evaluate("document.getElementById('sort-order').selectedOptions[0].textContent") == "Column: Entry ▲"
    page.select_option("#sort-order", "")
    page.wait_for_timeout(300)
    assert page.locator('#entries .entry-row-sort[aria-pressed="true"]').count() == 0
    page.close()
