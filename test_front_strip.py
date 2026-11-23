"""Tests for front_strip.py -- data for the front-page findings strip
(spec: tap-data docs/superpowers/specs/2026-11-23-front-strip-design.md)."""

import json
from datetime import date

from front_strip import build_front_strip, write_front_strip, harm_tier

TODAY = date(2026, 11, 23)


def _write(site, name, data):
    (site / "data").mkdir(parents=True, exist_ok=True)
    (site / "data" / name).write_text(json.dumps(data))


def _harm_entry(entry_id, kind="physical", certainty="documented", updated="2026-11-01",
                quote="A quote.", who="Some people", tier=None):
    harm = {"kind": kind, "certainty": certainty, "who": who}
    if tier is not None:
        harm["tier"] = tier
    entry = {"id": entry_id, "glance": {"who": "An official", "what": f"What {entry_id}", "harm": harm},
             "last_substantive_update": updated, "status_stage": "Court ruled"}
    if quote:
        entry["pull_quote"] = quote
    return entry


def test_harm_tier_matches_site_rule():
    assert harm_tier("physical", None) == 1
    assert harm_tier("livelihood", None) == 2
    assert harm_tier("money", None) == 3
    assert harm_tier("rights", None) is None
    assert harm_tier("rights", 1) == 1
    assert harm_tier("physical", 7) == 1  # out-of-range override ignored


def test_stats_count_curated_trackers_and_tier1(tmp_path):
    _write(tmp_path, "deregulation.json", [_harm_entry("a"), _harm_entry("b", kind="money")])
    _write(tmp_path, "community-topics.json", [{"id": "c", "topic": "T"}])
    _write(tmp_path, "illegality.json", {"entries": {"a": {}, "b": {}}})
    _write(tmp_path, "claim-checks.json", {"checks": [1, 2, 3]})
    strip = build_front_strip(tmp_path, set(), TODAY, None)
    assert strip["stats"] == {"entries": 3, "life_health": 1, "illegality": 2, "claim_checks": 3}
    assert strip["as_of"] == "2026-11-23"


def test_tier_override_counts_and_hidden_excluded(tmp_path):
    _write(tmp_path, "government-services.json", [_harm_entry("liv", kind="livelihood", tier=1)])
    _write(tmp_path, "dai.json", [_harm_entry("hid")])
    strip = build_front_strip(tmp_path, {"dai"}, TODAY, None)
    assert strip["stats"]["entries"] == 1
    assert strip["stats"]["life_health"] == 1
    assert strip["featured"]["id"] == "liv"


def test_ranking_prefers_documented_then_newest(tmp_path):
    _write(tmp_path, "government-services.json", [
        _harm_entry("alleged-newest", certainty="alleged", updated="2026-11-20"),
        _harm_entry("doc-old", updated="2026-10-01"),
        _harm_entry("doc-new", updated="2026-11-10"),
    ])
    f = build_front_strip(tmp_path, set(), TODAY, None)["featured"]
    assert f["id"] == "doc-new"
    assert f["tracker"] == "govservices"
    assert f["label"] == "Government Service Redirection"
    assert f["what"] == "What doc-new"
    assert f["who"] == "Some people"
    assert f["status"] == "Court ruled"
    assert f["pull_quote"] == "A quote."
    assert f["certainty"] == "documented"
    assert f["since"] == "2026-11-23"


def _prev(entry_id, since, history=None):
    return {"featured": {"tracker": "govservices", "id": entry_id, "since": since},
            "history": history if history is not None else [
                {"tracker": "govservices", "id": entry_id, "since": since}]}


def test_hold_keeps_pick_for_three_days(tmp_path):
    _write(tmp_path, "government-services.json", [
        _harm_entry("top", updated="2026-11-20"), _harm_entry("x", updated="2026-01-01")])
    prev = _prev("x", "2026-11-21")
    kept = build_front_strip(tmp_path, set(), date(2026, 11, 23), prev)
    assert kept["featured"]["id"] == "x"
    assert kept["featured"]["since"] == "2026-11-21"
    assert len(kept["history"]) == 1  # a kept pick isn't re-added
    changed = build_front_strip(tmp_path, set(), date(2026, 11, 24), prev)
    assert changed["featured"]["id"] == "top"


def test_no_repeat_within_14_days_then_fallback(tmp_path):
    _write(tmp_path, "government-services.json", [
        _harm_entry("first", updated="2026-11-20"), _harm_entry("second", updated="2026-11-10")])
    prev = {"featured": {"tracker": "govservices", "id": "first", "since": "2026-11-15"},
            "history": [{"tracker": "govservices", "id": "first", "since": "2026-11-15"}]}
    assert build_front_strip(tmp_path, set(), date(2026, 11, 24), prev)["featured"]["id"] == "second"
    # both featured recently -> fall back to the top-ranked one
    prev["history"].append({"tracker": "govservices", "id": "second", "since": "2026-11-12"})
    prev["featured"] = {"tracker": "govservices", "id": "second", "since": "2026-11-12"}
    assert build_front_strip(tmp_path, set(), date(2026, 11, 24), prev)["featured"]["id"] == "first"


def test_pick_replaced_when_it_leaves_pool(tmp_path):
    _write(tmp_path, "government-services.json", [_harm_entry("other")])
    prev = _prev("gone", "2026-11-22")
    assert build_front_strip(tmp_path, set(), TODAY, prev)["featured"]["id"] == "other"


def test_same_id_in_another_tracker_is_not_the_held_pick(tmp_path):
    _write(tmp_path, "dai.json", [_harm_entry("x")])
    _write(tmp_path, "government-services.json", [_harm_entry("y", updated="2026-01-01")])
    prev = _prev("x", "2026-11-22")  # held pick was govservices/x, which no longer exists
    f = build_front_strip(tmp_path, set(), TODAY, prev)["featured"]
    assert (f["tracker"], f["id"]) == ("dai", "x")
    assert f["since"] == "2026-11-23"


def test_empty_pool_gives_null_featured(tmp_path):
    _write(tmp_path, "deregulation.json", [_harm_entry("a", quote=None)])
    strip = build_front_strip(tmp_path, set(), TODAY, None)
    assert strip["featured"] is None
    assert strip["stats"]["life_health"] == 1


def test_history_capped_and_newest_first(tmp_path):
    _write(tmp_path, "government-services.json", [_harm_entry("new")])
    history = [{"tracker": "govservices", "id": f"old{n}", "since": "2026-01-01"} for n in range(30)]
    prev = {"featured": {"tracker": "govservices", "id": "old0", "since": "2026-01-01"}, "history": history}
    strip = build_front_strip(tmp_path, set(), TODAY, prev)
    assert len(strip["history"]) == 30
    assert strip["history"][0] == {"tracker": "govservices", "id": "new", "since": "2026-11-23"}


def test_write_front_strip_dry_run_and_bad_previous(tmp_path):
    _write(tmp_path, "deregulation.json", [_harm_entry("a")])
    (tmp_path / "data" / "front-strip.json").write_text("{not json")
    strip = write_front_strip(tmp_path, set(), TODAY, dry_run=True)
    assert strip["featured"]["id"] == "a"
    assert (tmp_path / "data" / "front-strip.json").read_text() == "{not json"
    write_front_strip(tmp_path, set(), TODAY)
    written = json.loads((tmp_path / "data" / "front-strip.json").read_text())
    assert written["featured"]["id"] == "a"


def test_averted_excluded_from_count_and_pool(tmp_path):
    # Review I1: averted harms never happened -- the #harms view keeps them
    # out of its headline number, so the strip does too, and never features one.
    _write(tmp_path, "government-services.json", [
        _harm_entry("averted-top", certainty="averted", updated="2026-11-22"),
        _harm_entry("real", updated="2026-01-01"),
    ])
    strip = build_front_strip(tmp_path, set(), TODAY, None)
    assert strip["stats"]["life_health"] == 1
    assert strip["featured"]["id"] == "real"


def test_invalid_glance_not_counted(tmp_path):
    # Review I2: same validity rule as isValidGlance() in index.html, so the
    # strip can't count (or feature) an entry the #harms view drops.
    bad = [
        _harm_entry("long-what"),
        _harm_entry("bad-cert", certainty="likely"),
        _harm_entry("bool-tier", kind="rights", tier=True),
        _harm_entry("no-glance-who"),
        _harm_entry("long-harm-who", who="x" * 41),
        _harm_entry("bad-kind", kind="spiritual", tier=1),
    ]
    bad[0]["glance"]["what"] = "w" * 111
    bad[3]["glance"].pop("who", None)
    _write(tmp_path, "dai.json", bad)
    strip = build_front_strip(tmp_path, set(), TODAY, None)
    assert strip["stats"]["life_health"] == 0
    assert strip["featured"] is None
