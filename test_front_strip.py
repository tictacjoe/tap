"""Tests for front_strip.py -- data for the front-page findings strip
(spec: tap-data docs/superpowers/specs/2026-11-23-front-strip-design.md).
The featured cards and their rotation were removed 2026-11-24."""

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
    _write(tmp_path, "tracker.json", [{"t": 1}, {"t": 2}, {"t": 3}])
    strip = build_front_strip(tmp_path, set(), TODAY)
    assert strip["stats"] == {"entries": 3, "life_health": 1, "illegality": 2, "reporting": 3}
    # hidden Reporting counts as zero
    assert build_front_strip(tmp_path, {"tracker"}, TODAY)["stats"]["reporting"] == 0
    assert strip["as_of"] == "2026-11-23"


def test_tier_override_counts_and_hidden_excluded(tmp_path):
    _write(tmp_path, "government-services.json", [_harm_entry("liv", kind="livelihood", tier=1)])
    _write(tmp_path, "dai.json", [_harm_entry("hid")])
    strip = build_front_strip(tmp_path, {"dai"}, TODAY)
    assert strip["stats"]["entries"] == 1
    assert strip["stats"]["life_health"] == 1


def test_output_is_stats_only(tmp_path):
    # Featured cards removed 2026-11-24: no featured/history keys any more.
    _write(tmp_path, "deregulation.json", [_harm_entry("a")])
    _write(tmp_path, "illegality.json", {"entries": {"a": [{"law": "apa"}]}})
    assert set(build_front_strip(tmp_path, set(), TODAY)) == {"as_of", "stats"}


def test_write_front_strip_dry_run_and_bad_previous(tmp_path):
    _write(tmp_path, "deregulation.json", [_harm_entry("a")])
    (tmp_path / "data" / "front-strip.json").write_text("{not json")
    strip = write_front_strip(tmp_path, set(), TODAY, dry_run=True)
    assert strip["stats"]["life_health"] == 1
    assert (tmp_path / "data" / "front-strip.json").read_text() == "{not json"
    write_front_strip(tmp_path, set(), TODAY)
    written = json.loads((tmp_path / "data" / "front-strip.json").read_text())
    assert written == strip


def test_averted_excluded_from_count(tmp_path):
    # Review I1: averted harms never happened -- the #harms view keeps them
    # out of its headline number, so the strip does too.
    _write(tmp_path, "government-services.json", [
        _harm_entry("averted-top", certainty="averted", updated="2026-11-22"),
        _harm_entry("real", updated="2026-01-01"),
    ])
    assert build_front_strip(tmp_path, set(), TODAY)["stats"]["life_health"] == 1


def test_invalid_glance_not_counted(tmp_path):
    # Review I2: same validity rule as isValidGlance() in index.html, so the
    # strip can't count an entry the #harms view drops.
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
    strip = build_front_strip(tmp_path, set(), TODAY)
    assert strip["stats"]["life_health"] == 0
