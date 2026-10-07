"""Browser tests for deep links to Reporting cards (connector spec sec-7.2): a recent and an old
item open and highlight, an unknown or hidden-category id shows the note, curated links still work,
Headlines jump and Back reach an old item. Served from this repo on a free port; skips without
Playwright/Chromium."""

import functools
import http.server
import json
import pathlib
import threading

import pytest

sync_api = pytest.importorskip("playwright.sync_api")

SITE_DIR = pathlib.Path(__file__).parent
CURATED_ID = "bondi-tirrell-ethics-jack-smith-purge-2025"
NOTE = "isn't on TAP's Reporting tab"


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


def _goto(browser, site_url, fragment):
    page = browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{site_url}/index.html" + (f"#{fragment}" if fragment else ""), wait_until="networkidle")
    page.wait_for_timeout(1500)
    return page, errors


def _ids(page):
    """(ids drawn on the Reporting tab's default list, every visible Reporting id oldest first)."""
    return page.evaluate("""() => [
        [...document.querySelectorAll('#entries .entry[data-entry-id]')].map(e => e.dataset.entryId),
        [...TRACKERS.tracker.data].sort((a, b) => (a.date || '').localeCompare(b.date || '')).map(e => e.id)]""")


def _hidden_category_id():
    """An id whose category the site removes from Reporting (no category at all -> Uncategorized)."""
    posts = json.loads((SITE_DIR / "data" / "tracker.json").read_text())
    for post in posts:
        for entry in post.get("entries") or []:
            if not entry.get("category") and not post.get("category") and entry.get("id"):
                return entry["id"]
    pytest.skip("no uncategorised Reporting item in the published data")


def test_a_recent_reporting_link_opens_and_highlights_its_card(browser, site_url):
    page, errors = _goto(browser, site_url, "tracker/x")  # land on Reporting to learn a drawn id
    drawn, _ = _ids(page)
    page, errors = _goto(browser, site_url, "tracker/" + drawn[0])
    card = page.locator(f'.entry[data-entry-id="{drawn[0]}"]')
    assert card.count() == 1
    assert "open" in card.get_attribute("class") and "deep-linked" in card.get_attribute("class")
    assert page.locator(".deep-link-note").count() == 0
    assert errors == []


def test_an_old_reporting_item_past_the_render_cap_is_drawn_and_opened(browser, site_url):
    page, _ = _goto(browser, site_url, "tracker/x")
    drawn, every = _ids(page)
    old = next(i for i in every if i not in set(drawn))  # the oldest undrawn item, from 2025
    page, errors = _goto(browser, site_url, "tracker/" + old)
    card = page.locator(f'.entry[data-entry-id="{old}"]')
    assert card.count() == 1
    assert "linked-item" in card.get_attribute("class") and "open" in card.get_attribute("class")
    assert "deep-linked" in card.get_attribute("class")
    assert page.locator("#entries > .entry").first.get_attribute("data-entry-id") == old
    # Once the highlight ends the card must still say why it sits above newer items.
    assert card.locator(".linked-item-tag").text_content().strip() == "Linked item"
    assert errors == []


@pytest.mark.parametrize("which", ["unknown", "hidden"])
def test_an_unknown_or_hidden_reporting_id_shows_the_note(browser, site_url, which):
    item = "ffffffffffffffff" if which == "unknown" else _hidden_category_id()
    page, errors = _goto(browser, site_url, "tracker/" + item)
    note = page.locator("#entries > .deep-link-note")
    assert note.count() == 1 and NOTE in note.inner_text()
    assert page.evaluate("activeTracker") == "tracker"
    assert errors == []


def test_curated_links_still_open_and_now_highlight(browser, site_url):
    page, errors = _goto(browser, site_url, "prosecution/" + CURATED_ID)
    card = page.locator(f'.entry[data-entry-id="{CURATED_ID}"]')
    assert "open" in card.get_attribute("class") and "deep-linked" in card.get_attribute("class")
    assert errors == []


def test_the_highlight_fades(browser, site_url):
    page, _ = _goto(browser, site_url, "prosecution/" + CURATED_ID)
    page.wait_for_timeout(page.evaluate("DEEP_LINK_HIGHLIGHT_MS") + 300)
    assert page.locator(".entry.deep-linked").count() == 0
    # The transition must outlive the class, or the highlight snaps off instead of fading.
    card = page.locator(f'.entry[data-entry-id="{CURATED_ID}"]')
    assert card.evaluate("c => getComputedStyle(c).transitionDuration") != "0s"


def test_reporting_cards_offer_copy_link_with_their_id(browser, site_url):
    page, _ = _goto(browser, site_url, "tracker/x")
    drawn, _ = _ids(page)
    btn = page.locator(f'.entry[data-entry-id="{drawn[0]}"] .share-link-btn')
    assert btn.get_attribute("data-share-tracker") == "tracker"
    assert page.evaluate("([t, i]) => buildShareUrl(t, i)", ["tracker", drawn[0]]).endswith("#tracker/" + drawn[0])


def test_a_second_link_replaces_the_first_drawn_card_and_back_redraws_it(browser, site_url):
    page, _ = _goto(browser, site_url, "tracker/x")
    drawn, every = _ids(page)
    old = [i for i in every if i not in set(drawn)][:2]
    page.evaluate("(id) => { history.pushState({type: 'entry', tracker: 'tracker', id}, '', location.href);"
                  " goToTrackerHome('tracker'); openCardById(id); }", old[0])
    page.evaluate("(id) => { history.pushState({type: 'entry', tracker: 'tracker', id}, '', location.href);"
                  " goToTrackerHome('tracker'); openCardById(id); }", old[1])
    assert page.locator(".entry.linked-item").count() == 1
    assert page.locator(f'.entry[data-entry-id="{old[1]}"]').count() == 1
    page.go_back()
    page.wait_for_timeout(800)
    assert page.locator(".entry.linked-item").count() == 1
    assert page.locator(f'.entry[data-entry-id="{old[0]}"].open').count() == 1


def test_a_headlines_jump_to_an_old_reporting_row_opens_it_and_back_forward_replay(browser, site_url):
    """The real Headlines button, not a simulated jump: load Headlines rows until a Reporting row whose
    card is outside the 300 drawn appears, click it, then Back (Headlines) and Forward (the card again)."""
    page, errors = _goto(browser, site_url, "")  # the plain page; Headlines is reached from there
    page.evaluate("selectDatabaseTab('headlines')")
    page.wait_for_timeout(800)
    for _ in range(15):
        more = page.locator("#headlines-load-more-btn")
        if not more.is_visible():
            break
        more.click()
        page.wait_for_timeout(300)
    buttons = page.locator(".headline-row-tracker")
    last = next((i for i in range(buttons.count() - 1, -1, -1)
                 if "Reporting" in (buttons.nth(i).get_attribute("title") or "") and buttons.nth(i).is_visible()), None)
    if last is None:
        pytest.skip("no visible Reporting row among the loaded Headlines rows")
    buttons.nth(last).click()
    page.wait_for_timeout(1000)
    item = page.evaluate("history.state.id")
    if page.locator(f'#entries > .entry:not(.linked-item)[data-entry-id="{item}"]').count():
        pytest.skip("the oldest loaded Reporting row is among the 300 drawn")
    assert page.locator(f'.entry.linked-item.open[data-entry-id="{item}"]').count() == 1
    page.go_back()
    page.wait_for_timeout(1000)
    assert page.evaluate("activeTracker") == "headlines"
    page.go_forward()
    page.wait_for_timeout(1000)
    assert page.locator(f'.entry.linked-item.open[data-entry-id="{item}"]').count() == 1
    assert page.locator(".entry.linked-item").count() == 1
    assert errors == []
