import json

from publish import publish_json_entries


def test_publish_json_entries_preserves_section_summaries(tmp_path):
    source_dir = tmp_path / "entries"
    source_dir.mkdir()
    entry = {
        "id": "sample-entry",
        "what_changed": "Agency repealed the rule.",
        "section_summaries": {
            "what_changed": "Agency repealed the rule outright.",
            "confidence_note": "High confidence, agency-sourced figures.",
        },
    }
    (source_dir / "sample-entry.json").write_text(json.dumps(entry))

    dest_file = tmp_path / "output" / "deregulation.json"
    included, excluded_count = publish_json_entries(source_dir, dest_file, excluded_ids=set())

    assert excluded_count == 0
    assert included[0]["section_summaries"] == entry["section_summaries"]

    published = json.loads(dest_file.read_text())
    assert published[0]["section_summaries"] == entry["section_summaries"]


def test_publish_json_entries_excludes_entries_without_touching_others(tmp_path):
    source_dir = tmp_path / "entries"
    source_dir.mkdir()
    kept = {"id": "kept-entry", "section_summaries": {"what_changed": "Kept."}}
    excluded = {"id": "excluded-entry", "section_summaries": {"what_changed": "Excluded."}}
    (source_dir / "kept-entry.json").write_text(json.dumps(kept))
    (source_dir / "excluded-entry.json").write_text(json.dumps(excluded))

    dest_file = tmp_path / "output" / "deregulation.json"
    included, excluded_count = publish_json_entries(
        source_dir, dest_file, excluded_ids={"excluded-entry"}
    )

    assert excluded_count == 1
    assert len(included) == 1
    assert included[0]["id"] == "kept-entry"


from pathlib import Path

import pytest

from publish import load_glance_checker

TAP_DATA = Path.home() / "gjoe/tap-data"


def _one_entry_dir(tmp_path, entry):
    source_dir = tmp_path / "entries"
    source_dir.mkdir()
    (source_dir / "e.json").write_text(json.dumps(entry))
    return source_dir


def test_publish_strips_a_malformed_glance_but_keeps_the_entry(tmp_path, capsys):
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "glance": {"who": ""}})
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(),
        check_glance=lambda g: ["glance.who is required"])
    assert included[0]["id"] == "e"
    assert "glance" not in included[0]
    assert "malformed glance stripped from e" in capsys.readouterr().out
    assert "glance" not in json.loads((tmp_path / "out.json").read_text())[0]


def test_publish_keeps_a_valid_glance(tmp_path):
    glance = {"who": "W"}
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "glance": glance})
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(), check_glance=lambda g: [])
    assert included[0]["glance"] == glance


def test_publish_never_publishes_glance_drafts(tmp_path):
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "_glance_draft": {"who": "W"}})
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(), check_glance=lambda g: [])
    assert "_glance_draft" not in included[0]


def test_publish_without_a_checker_leaves_glance_untouched(tmp_path):
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "glance": {"who": "W"}})
    included, _ = publish_json_entries(source_dir, tmp_path / "out.json", excluded_ids=set())
    assert included[0]["glance"] == {"who": "W"}


@pytest.mark.skipif(not (TAP_DATA / "tracker/validate_glance.py").exists(),
                    reason="tap-data working repo not present")
def test_load_glance_checker_imports_the_working_repos_validator():
    check = load_glance_checker(TAP_DATA)
    assert check({}) != []  # an empty block is invalid


from types import SimpleNamespace

from publish import load_update_markers


def _stub_markers(timeline, seen=None):
    """A stand-in for the update_markers module: build_timeline returns a
    fixed value and records what it was called with."""
    def build(entry, fields, warn=None):
        if seen is not None:
            seen.append((dict(entry), tuple(fields)))
        return timeline
    return SimpleNamespace(build_timeline=build)


def test_publish_adds_the_timeline_the_builder_returns(tmp_path):
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "what_changed": "x"})
    timeline = {"what_changed": {"base": "x", "updates": []}}
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(),
        update_markers=_stub_markers(timeline), timeline_fields=("what_changed",))
    assert included[0]["timeline"] == timeline
    assert json.loads((tmp_path / "out.json").read_text())[0]["timeline"] == timeline


def test_publish_adds_no_timeline_key_when_the_builder_returns_none(tmp_path):
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "what_changed": "x"})
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(),
        update_markers=_stub_markers(None), timeline_fields=("what_changed",))
    assert "timeline" not in included[0]


def test_publish_gives_the_builder_the_published_entry_and_the_field_list(tmp_path):
    seen = []
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "_internal": 1, "status": "s"})
    publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(),
        update_markers=_stub_markers(None, seen), timeline_fields=("status", "confidence_note"))
    entry, fields = seen[0]
    assert fields == ("status", "confidence_note")
    assert "_internal" not in entry  # the builder sees the already-stripped entry


def test_publish_warns_and_overwrites_a_timeline_key_already_in_the_source(tmp_path, capsys):
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "timeline": {"stale": True}})
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(),
        update_markers=_stub_markers(None), timeline_fields=("status",))
    assert "timeline" not in included[0]
    assert "already has a 'timeline' key" in capsys.readouterr().out


def test_publish_without_update_markers_leaves_the_entry_alone(tmp_path):
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "timeline": {"x": 1}})
    included, _ = publish_json_entries(source_dir, tmp_path / "out.json", excluded_ids=set())
    assert included[0]["timeline"] == {"x": 1}


@pytest.mark.skipif(not (TAP_DATA / "tracker/update_markers.py").exists(),
                    reason="tap-data working repo not present")
def test_load_update_markers_imports_the_working_repos_parser():
    module = load_update_markers(TAP_DATA)
    assert module.parse_field("Base. Update 2026-08-02: more.")["updates"][0]["date"] == "2026-08-02"


@pytest.mark.skipif(not (TAP_DATA / "tracker/update_markers.py").exists(),
                    reason="tap-data working repo not present")
def test_real_parser_through_publish_keeps_prose_untouched_and_adds_the_timeline(tmp_path):
    module = load_update_markers(TAP_DATA)
    prose = "Base. Update 2026-08-02: later. Added 2026-08-17: latest."
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "what_changed": prose, "status": "Plain."})
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(),
        update_markers=module, timeline_fields=("what_changed", "status"))
    assert included[0]["what_changed"] == prose
    timeline = included[0]["timeline"]
    assert list(timeline) == ["what_changed"]
    assert [u["label"] for u in timeline["what_changed"]["updates"]] == ["Update", "Added"]


@pytest.mark.skipif(not (TAP_DATA / "tracker/update_markers.py").exists(),
                    reason="tap-data working repo not present")
def test_publishing_twice_gives_byte_identical_files(tmp_path):
    module = load_update_markers(TAP_DATA)
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "confidence_note": "B. Update 2026-08-02: x."})
    for name in ("a.json", "b.json"):
        publish_json_entries(source_dir, tmp_path / name, excluded_ids=set(),
                             update_markers=module, timeline_fields=("confidence_note",))
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


def _real_glance(**overrides):
    glance = {
        "who": "Example Agency Administrator",
        "what": "Rolled back an example safety rule with no replacement",
        "harm": {"kind": "physical", "certainty": "projected", "who": "Workers at example sites"},
        "reviewed": "2026-09-20",
    }
    glance.update(overrides)
    return glance


@pytest.mark.skipif(not (TAP_DATA / "tracker/validate_glance.py").exists(),
                    reason="tap-data working repo not present")
def test_real_validator_through_the_publish_guard_strips_an_over_limit_glance(tmp_path, capsys):
    check = load_glance_checker(TAP_DATA)
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "glance": _real_glance(what="w" * 111)})
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(), check_glance=check)
    assert included[0]["id"] == "e"
    assert "glance" not in included[0]
    out = capsys.readouterr().out
    assert "malformed glance stripped from" in out
    assert "max 110" in out


@pytest.mark.skipif(not (TAP_DATA / "tracker/validate_glance.py").exists(),
                    reason="tap-data working repo not present")
def test_real_validator_through_the_publish_guard_keeps_a_valid_glance(tmp_path, capsys):
    check = load_glance_checker(TAP_DATA)
    glance = _real_glance()
    source_dir = _one_entry_dir(tmp_path, {"id": "e", "glance": glance})
    included, _ = publish_json_entries(
        source_dir, tmp_path / "out.json", excluded_ids=set(), check_glance=check)
    assert included[0]["glance"] == glance
    assert "malformed glance" not in capsys.readouterr().out


from publish import load_claim_checks, publish_claim_checks


def _claims_file(tmp_path, records):
    path = tmp_path / "claims.json"
    path.write_text(json.dumps({r["claim_id"]: r for r in records}))
    return path


def _claim_record(**over):
    record = {
        "claim_id": "entry-a::ev000", "entry_id": "entry-a", "evidence_index": 0,
        "claim_text": "the evidence", "source_url": "https://www.npr.org/x",
        "verdict": "confirmed", "verdict_rationale": "supported.", "fetch_status": "ok",
        "date_verified": "2026-09-15", "fact_or_interpretation": "fact", "source_excerpt": "SECRET",
    }
    record.update(over)
    return record


_ENTRY_A = {"id": "entry-a", "evidence": [{"description": "the evidence", "source_url": "https://www.npr.org/x"}]}

_needs_tap_data = pytest.mark.skipif(not (TAP_DATA / "tracker/claim_checks_public.py").exists(),
                                     reason="tap-data working repo not present")


@_needs_tap_data
def test_load_claim_checks_imports_the_working_repos_module():
    module = load_claim_checks(TAP_DATA)
    assert module.public_state({"verdict": "confirmed"}) == "supports"


@_needs_tap_data
def test_publish_claim_checks_writes_the_public_file_and_reports(tmp_path, capsys):
    module = load_claim_checks(TAP_DATA)
    claims = _claims_file(tmp_path, [_claim_record()])
    dest = tmp_path / "data" / "claim-checks.json"
    report = publish_claim_checks(module, claims, [_ENTRY_A], dest)
    assert report["published"] == 1
    written = json.loads(dest.read_text())
    assert written["checks"]["entry-a"]["0"]["state"] == "supports"
    assert "SECRET" not in dest.read_text()
    assert "1 published" in capsys.readouterr().out


@_needs_tap_data
def test_publish_claim_checks_without_a_claims_file_warns_and_writes_nothing(tmp_path, capsys):
    module = load_claim_checks(TAP_DATA)
    dest = tmp_path / "data" / "claim-checks.json"
    assert publish_claim_checks(module, tmp_path / "missing.json", [_ENTRY_A], dest) is None
    assert not dest.exists()
    assert "WARNING" in capsys.readouterr().out


@_needs_tap_data
def test_publish_claim_checks_dry_run_writes_nothing(tmp_path):
    module = load_claim_checks(TAP_DATA)
    dest = tmp_path / "data" / "claim-checks.json"
    publish_claim_checks(module, _claims_file(tmp_path, [_claim_record()]), [_ENTRY_A], dest, dry_run=True)
    assert not dest.exists()


@_needs_tap_data
def test_publish_claim_checks_is_byte_identical_when_run_twice(tmp_path):
    module = load_claim_checks(TAP_DATA)
    claims = _claims_file(tmp_path, [_claim_record()])
    for name in ("a.json", "b.json"):
        publish_claim_checks(module, claims, [_ENTRY_A], tmp_path / name)
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


@_needs_tap_data
def test_publish_claim_checks_drops_a_check_whose_evidence_changed(tmp_path, capsys):
    module = load_claim_checks(TAP_DATA)
    changed = {"id": "entry-a", "evidence": [{"description": "reworded", "source_url": "https://www.npr.org/x"}]}
    dest = tmp_path / "data" / "claim-checks.json"
    report = publish_claim_checks(module, _claims_file(tmp_path, [_claim_record()]), [changed], dest)
    assert report["dropped_stale"] == 1 and json.loads(dest.read_text())["checks"] == {}
    assert "entry-a::ev000" in capsys.readouterr().out
