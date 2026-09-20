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
