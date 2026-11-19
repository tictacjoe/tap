"""Browser tests for the Sources card's place and default state (2026-11-15,
Joe: "expand sources by default and place it to the right of the what happened
timelines"). Each case opens a real entry by its #tracker/<id> deep link and
checks, at three widths, that Sources is open and sits where it should:
  - 3 columns (wide) and 2 columns (mid): top of the second column, beside
    What happened;
  - 1 column (phone): the card right after What happened.
The site is served from this repo's own directory. Skips if Playwright or
Chromium is missing."""

import functools
import http.server
import json
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent


def _first_with_sources(file_name, has_sources):
    for e in json.loads((SITE_DIR / "data" / file_name).read_text()):
        if has_sources(e):
            return e["id"]
    raise AssertionError(f"no entry with sources in {file_name}")


# One entry per detail-card builder: Cabinet-Level (evidence URLs),
# Deregulation, and the shared govservices branch (GSR/TFS/DAI).
# Each also has a Broader Pattern (`cause`), for the third-column check.
CASES = [
    ("prosecution", _first_with_sources(
        "prosecution.json", lambda e: e.get("cause") and any(i.get("source_url") for i in e.get("evidence") or []))),
    ("deregulation", _first_with_sources("deregulation.json", lambda e: e.get("cause") and bool(e.get("sources")))),
    ("govservices", _first_with_sources("government-services.json", lambda e: e.get("cause") and bool(e.get("sources")))),
]

# Which column the card's visible columns put it in, and its position there.
_PLACEMENT = """(id) => {
    const card = document.querySelector('.entry.open[data-entry-id="' + id + '"]');
    if (!card) return null;
    const cols = [...card.querySelectorAll('.entry-cols > .entry-col')]
        .filter(c => getComputedStyle(c).display !== 'none');
    const where = label => {
        for (let ci = 0; ci < cols.length; ci++) {
            const kids = [...cols[ci].children];
            const k = kids.findIndex(el => {
                const lab = el.querySelector('.field-label');
                return lab && lab.textContent.trim() === label;
            });
            if (k !== -1) return [ci, k];
        }
        return null;
    };
    const details = card.querySelector('details.field-toggle:has(.exhibit-list)');
    return {
        columns: cols.length,
        sources: where('Sources'),
        pattern: where('Broader Pattern'),
        what: where('What happened'),
        open: !!(details && details.open),
    };
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


def _placement(browser, site_url, tracker, entry_id, width):
    context = browser.new_context(viewport={"width": width, "height": 900})
    page = context.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/index.html#{tracker}/{entry_id}", wait_until="networkidle")
    page.wait_for_timeout(1500)
    result = page.evaluate(_PLACEMENT, entry_id)
    context.close()
    assert errors == []
    assert result is not None, "deep link did not open the entry"
    return result


@pytest.mark.parametrize("tracker,entry_id", CASES)
@pytest.mark.parametrize("width", [1900, 1280])
def test_sources_open_and_beside_what_happened(browser, site_url, tracker, entry_id, width):
    r = _placement(browser, site_url, tracker, entry_id, width)
    assert r["columns"] >= 2
    assert r["open"], "Sources should be expanded by default"
    assert r["what"] == [0, 0]
    assert r["sources"] == [1, 0], "Sources should top the column beside What happened"


@pytest.mark.parametrize("tracker,entry_id", CASES)
def test_sources_follow_what_happened_on_phone(browser, site_url, tracker, entry_id):
    r = _placement(browser, site_url, tracker, entry_id, 390)
    assert r["columns"] == 1
    assert r["open"]
    assert r["what"] == [0, 0]
    assert r["sources"] == [0, 1], "Sources should come right after What happened"


@pytest.mark.parametrize("tracker,entry_id", CASES)
def test_broader_pattern_tops_third_column(browser, site_url, tracker, entry_id):
    # 2026-11-15: Broader Pattern sits to the right of Sources (top of column 3).
    r = _placement(browser, site_url, tracker, entry_id, 1900)
    assert r["columns"] == 3
    assert r["pattern"] == [2, 0], "Broader Pattern should top the third column, right of Sources"
