"""Browser tests for the browse chips (2026-11-19): a row of tracker chips
under the search box replaced the "— browse by tracker —" button and its
dialog. An "Uncurated reporting" chip (2026-11-21) on its own centered line
at the top, then six tracker chips -- the five curated trackers plus
Claim-checks (OEA retired 2026-11-19) -- each opening its tracker in one
click, then two view chips (data-view, not data-tracker): Harms and Possible
Illegality. Tracker chips' hover titles carry the tracker's full name and
entry count once data has loaded.

The server holds back tracker.json (the ~14MB Reporting file) so the page
can be checked mid-load, the way a slow connection sees it. Skips if
Playwright or Chromium is missing."""

import functools
import http.server
import pathlib
import re
import threading
import time

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent
TRACKER_DELAY_S = 3


class _SlowTracker(http.server.SimpleHTTPRequestHandler):
    """Serves the site, but delays data/tracker.json so loading stays in progress."""

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path.split("?")[0].endswith("/data/tracker.json"):
            time.sleep(TRACKER_DELAY_S)
        super().do_GET()


@pytest.fixture(scope="module")
def site_url():
    handler = functools.partial(_SlowTracker, directory=str(SITE_DIR))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as exc:  # Chromium not installed
            pytest.skip(f"Chromium unavailable: {exc}")
        yield b
        b.close()


def _open(browser, site_url, width=1280, wait_loaded=True):
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.goto(site_url + "/index.html", wait_until="domcontentloaded")
    if wait_loaded:
        page.wait_for_function("allDataLoaded === true", timeout=60000)
    return page


def test_six_chips_in_order(site_url, browser):
    page = _open(browser, site_url)
    expected = page.evaluate(
        "visibleTrackerKeys(TRACKERS).filter(k => k !== 'tracker')"
        ".map(k => HEADLINE_TRACKER_MEDIUM[k].toUpperCase())"
    )
    chips = [t.strip() for t in page.locator("#browse-chips .browse-group .browse-chip[data-tracker]").all_inner_texts()]
    assert len(chips) == 6  # OEA retired 2026-11-19
    assert chips == expected
    assert chips[-1] == "CLAIM-CHECKS"
    assert "REPORTING" not in chips
    # 2026-11-21 (Joe): Reporting gets one chip of its own, first, above the groups.
    first = page.locator("#browse-chips .browse-chip").first
    assert first.get_attribute("data-tracker") == "tracker"
    assert first.inner_text().strip().upper() == "UNCURATED REPORTING"
    # The two cross-tracker view chips sit last, after every tracker chip.
    every = page.locator("#browse-chips .browse-chip").evaluate_all(
        "els => els.map(e => e.dataset.view || e.dataset.tracker)")
    assert every[-2:] == ["harms", "illegality"]
    assert len(every) == 9
    assert page.locator("#browse-instead").count() == 0
    assert page.locator("#browse-backdrop").count() == 0
    page.close()


def test_chip_click_opens_tracker(site_url, browser):
    page = _open(browser, site_url)
    page.click('.browse-chip[data-tracker="prosecution"]')
    assert page.evaluate("activeTracker") == "prosecution"
    assert page.evaluate("document.getElementById('tabs').value") == "prosecution"
    page.close()


def test_titles_fill_after_load(site_url, browser):
    page = _open(browser, site_url, wait_loaded=False)
    page.wait_for_selector("#browse-chips .browse-chip", state="attached", timeout=10000)
    during = page.locator(".browse-chip[data-tracker]").evaluate_all("els => els.map(e => e.title)")
    assert during and all(not re.search(r"\d", t) for t in during), during
    page.wait_for_function("allDataLoaded === true", timeout=60000)
    pairs = page.locator(".browse-chip[data-tracker]").evaluate_all(
        "els => els.map(e => [e.title, TRACKERS[e.dataset.tracker].data.length])"
    )
    for title, n in pairs:
        m = re.search(r"\((\d+) entries\)$", title)
        assert m, title
        assert int(m.group(1)) == n
    page.close()


def test_hidden_during_search(site_url, browser):
    page = _open(browser, site_url)
    assert page.locator("#browse-chips").is_visible()
    page.fill("#global-search", "court")
    page.wait_for_timeout(300)
    assert not page.locator("#browse-chips").is_visible()
    page.fill("#global-search", "")
    page.wait_for_timeout(300)
    assert page.locator("#browse-chips").is_visible()
    page.close()


def test_phone_width_wraps_without_scroll(site_url, browser):
    page = _open(browser, site_url, width=375)
    assert page.evaluate("document.documentElement.scrollWidth") <= 375
    tops = page.locator(".browse-chip").evaluate_all("els => els.map(e => e.offsetTop)")
    assert len(set(tops)) > 1
    page.close()


def test_claimchecks_chip_color(site_url, browser):
    page = _open(browser, site_url)
    bg = page.locator('.browse-chip[data-tracker="communitytopics"]').evaluate(
        "e => getComputedStyle(e).backgroundColor"
    )
    assert bg == "rgb(79, 91, 102)"
    page.close()


def test_chips_are_readable_and_tappable(site_url, browser):
    # Spec: about 12px text, easy to tap. html is font-size 80%, so rem
    # values render smaller than they read; check computed size and height.
    page = _open(browser, site_url, width=375)
    sizes = page.locator(".browse-chip").evaluate_all(
        "els => els.map(e => [parseFloat(getComputedStyle(e).fontSize), e.getBoundingClientRect().height])"
    )
    for font_px, height_px in sizes:
        assert 11.5 <= font_px <= 12.5, font_px
        assert height_px >= 24, height_px
    page.close()


def test_trackers_label_and_groups(site_url, browser):
    # 2026-11-19 (Joe): a "Trackers" label above the chips, and Claim-checks
    # plus the two cross-tracker views in their own, slightly separated group.
    page = _open(browser, site_url)
    assert page.locator("#browse-chips .browse-label").inner_text().strip().upper() == "TRACKERS"
    groups = page.locator("#browse-chips .browse-group").evaluate_all(
        "gs => gs.map(g => [...g.querySelectorAll('.browse-chip')].map(e => e.dataset.view || e.dataset.tracker))")
    assert len(groups) == 2
    assert "communitytopics" not in groups[0] and len(groups[0]) == 5
    assert groups[1] == ["communitytopics", "harms", "illegality"]
    # The gap between groups is wider than the gap between chips in a group.
    outer = page.locator("#browse-chips").evaluate("e => parseFloat(getComputedStyle(e).rowGap)")
    inner = page.locator("#browse-chips .browse-group").first.evaluate("e => parseFloat(getComputedStyle(e).rowGap)")
    assert outer > inner
    # Hairline rule above the second group (mockup option 2).
    border = page.locator("#browse-chips .browse-group-extra").evaluate(
        "e => [getComputedStyle(e).borderTopStyle, parseFloat(getComputedStyle(e).borderTopWidth)]")
    assert border[0] == "solid" and border[1] >= 1
    page.close()


def test_uncurated_reporting_chip(site_url, browser):
    # 2026-11-21 (Joe): an "Uncurated reporting" chip at the top center of the
    # chips, on its own line under the TRACKERS label. It opens the Reporting
    # tracker, and the database dropdown's matching option reads the same.
    page = _open(browser, site_url)
    chip = page.locator('#browse-chips .browse-reporting-row .browse-chip[data-tracker="tracker"]')
    assert chip.count() == 1
    assert chip.inner_text().strip().upper() == "UNCURATED REPORTING"
    assert re.search(r"\((\d+) entries\)$", chip.get_attribute("title"))
    geo = page.evaluate("""() => {
      const row = document.getElementById('browse-chips').getBoundingClientRect();
      const label = document.querySelector('#browse-chips .browse-label').getBoundingClientRect();
      const chip = document.querySelector('.browse-reporting-row .browse-chip').getBoundingClientRect();
      const groupTop = Math.min(...[...document.querySelectorAll('#browse-chips .browse-group .browse-chip')]
        .map(e => e.getBoundingClientRect().top));
      return {rowMid: row.left + row.width / 2, chipMid: chip.left + chip.width / 2,
              labelBottom: label.bottom, chipTop: chip.top, chipBottom: chip.bottom, groupTop};
    }""")
    assert abs(geo["rowMid"] - geo["chipMid"]) <= 2, geo
    assert geo["chipTop"] >= geo["labelBottom"] - 1, geo
    assert geo["chipBottom"] <= geo["groupTop"], geo
    chip.click()
    assert page.evaluate("activeTracker") == "tracker"
    assert page.evaluate("document.getElementById('tabs').value") == "tracker"
    text = page.evaluate("document.querySelector('#tabs option[value=\"tracker\"]').textContent")
    assert re.fullmatch(r"Uncurated reporting \(\d+\)", text), text
    page.close()
