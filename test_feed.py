"""Tests for feed.py -- the RSS "what's new" feed publish.py writes."""

import json
import xml.etree.ElementTree as ET
from datetime import date

from feed import build_feed, write_feed, FEED_SOURCES


def _write(site, name, entries):
    (site / "data").mkdir(parents=True, exist_ok=True)
    (site / "data" / name).write_text(json.dumps(entries))


def _items(xml_text):
    return ET.fromstring(xml_text).find("channel").findall("item")


def test_items_newest_first_with_deep_links_and_glance_titles(tmp_path):
    _write(tmp_path, "deregulation.json", [
        {"id": "old-rule", "rule_name": "Old Rule", "date_added": "2026-01-02",
         "glance": {"what": "Repealed the old rule"}, "short_summary": "Old summary.",
         "status_stage": "Unchallenged"},
    ])
    _write(tmp_path, "government-services.json", [
        {"id": "new-cut", "title": "New Cut", "date_added": "2026-03-04",
         "glance": {"what": "Cut the new program"}, "status_stage": "Court ruled"},
    ])
    items = _items(build_feed(tmp_path, hidden=set(), today=date(2026, 11, 23)))
    assert [i.findtext("guid") for i in items] == [
        "https://tictacjoe.github.io/tap/#govservices/new-cut",
        "https://tictacjoe.github.io/tap/#deregulation/old-rule",
    ]
    first = items[0]
    assert first.findtext("title") == "Government Service Redirection: Cut the new program"
    assert first.findtext("link") == "https://tictacjoe.github.io/tap/#govservices/new-cut"
    assert "Status: Court ruled" in first.findtext("description")
    assert first.findtext("pubDate").startswith("Wed, 04 Mar 2026")
    # short_summary is preferred over glance.what as the description body
    assert items[1].findtext("description").startswith("Old summary.")


def test_hidden_trackers_and_missing_dates_are_skipped(tmp_path):
    _write(tmp_path, "dai.json", [
        {"id": "hidden-one", "title": "T", "date_added": "2026-05-05"},
    ])
    _write(tmp_path, "prosecution.json", [
        {"id": "no-date", "official": "Someone"},
        {"id": "dated", "official": "Someone Else", "date_added": "2026-05-06"},
    ])
    items = _items(build_feed(tmp_path, hidden={"dai"}, today=date(2026, 11, 23)))
    assert [i.findtext("guid").rsplit("/", 1)[1] for i in items] == ["dated"]
    # falls back to the tracker's titleField when there is no glance
    assert items[0].findtext("title") == "Cabinet-Level Accountability: Someone Else"


def test_limit_and_community_topics_use_topic_and_summary(tmp_path):
    _write(tmp_path, "community-topics.json", [
        {"id": f"c{n}", "topic": f"Topic {n}", "summary": f"Summary {n}",
         "date_added": f"2026-10-{n:02d}"} for n in range(1, 6)
    ])
    items = _items(build_feed(tmp_path, hidden=set(), today=date(2026, 11, 23), limit=3))
    assert len(items) == 3
    assert items[0].findtext("title") == "Claim-check: Topic 5"
    assert items[0].findtext("description").startswith("Summary 5")


def test_xml_escapes_special_characters(tmp_path):
    _write(tmp_path, "trumpfamily.json", [
        {"id": "a&b", "title": "Deals <with> \"friends\" & family", "date_added": "2026-10-18"},
    ])
    xml_text = build_feed(tmp_path, hidden=set(), today=date(2026, 11, 23))
    item = _items(xml_text)[0]  # parses => well-formed
    assert item.findtext("title") == 'Trump Family: Deals <with> "friends" & family'
    assert item.findtext("link").endswith("#trumpfamily/a%26b")


def test_write_feed_creates_feed_xml_and_respects_dry_run(tmp_path):
    _write(tmp_path, "deregulation.json", [
        {"id": "r", "rule_name": "R", "date_added": "2026-01-02"},
    ])
    assert write_feed(tmp_path, hidden=set(), today=date(2026, 11, 23), dry_run=True) == 1
    assert not (tmp_path / "feed.xml").exists()
    assert write_feed(tmp_path, hidden=set(), today=date(2026, 11, 23)) == 1
    assert "<rss" in (tmp_path / "feed.xml").read_text(encoding="utf-8")


def test_feed_sources_cover_every_curated_data_file():
    # Reporting (tracker.json) is deliberately not in the feed: it's a
    # third-party archive TAP doesn't verify.
    assert {s[0] for s in FEED_SOURCES} == {
        "deregulation.json", "prosecution.json", "government-services.json",
        "trumpfamily.json", "dai.json", "community-topics.json",
    }
