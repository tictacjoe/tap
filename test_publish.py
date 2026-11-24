import json
from datetime import date

from publish import publish_json_entries, write_site_meta, publish_illegality, load_illegality


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
    out = capsys.readouterr().out
    assert "WARNING" in out
    # the warning must name the consequence: an old check file stays in place
    assert "claim-checks.json not written" in out
    assert "left unchanged and may now be stale" in out


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


def test_remove_retired_outputs_deletes_stale_oea_json(tmp_path, capsys):
    import publish as publish_mod
    # OEA retired 2026-11-19: a leftover data/oea.json is removed on publish.
    data = tmp_path / "data"
    data.mkdir()
    (data / "oea.json").write_text("[]")
    (data / "dai.json").write_text("[]")
    assert publish_mod.remove_retired_outputs(tmp_path) == ["oea.json"]
    assert not (data / "oea.json").exists() and (data / "dai.json").exists()
    assert publish_mod.remove_retired_outputs(tmp_path) == []
    assert publish_mod.remove_retired_outputs(tmp_path, dry_run=True) == []
    # A dry run lists what it would remove without deleting it.
    (data / "oea.json").write_text("[]")
    assert publish_mod.remove_retired_outputs(tmp_path, dry_run=True) == ["oea.json"]
    assert (data / "oea.json").exists()


def test_publish_has_no_oea_section():
    from pathlib import Path
    import publish as publish_mod
    assert "oea/entries" not in Path(publish_mod.__file__).read_text()


def test_publish_empty_trumpfamily_dir_writes_empty_array(tmp_path):
    src = tmp_path / "trumpfamily" / "entries"
    src.mkdir(parents=True)
    (src / ".gitkeep").write_text("")
    dest = tmp_path / "trumpfamily.json"
    included, excluded = publish_json_entries(src, dest, set())
    assert included == [] and excluded == 0
    assert json.loads(dest.read_text()) == []


# --- Phase B: moved-ids publish and the hidden-target guard (end to end) ---
import subprocess
import sys

_MOVE = {"m1": {"from": "prosecution", "to": "trumpfamily", "date": "2026-10-20"}}
_INDEX_HIDDEN = "const TRACKERS = {\n  trumpfamily: {\n    hidden: true,\n  },\n};\n"


def _e2e_dirs(tmp_path, moved):
    """Temp working + site dirs. The working repo's tracker/ items are symlinked
    one by one so the real glance/marker/claim loaders import, while
    tracker/moved_ids.json is this test's own file (never the real one)."""
    w = tmp_path / "working"
    (w / "trumpfamily").mkdir(parents=True)
    (w / "tracker").mkdir()
    real_tracker = Path(__file__).parent.parent / "tap-data" / "tracker"
    for item in real_tracker.iterdir():
        if item.name != "moved_ids.json":
            (w / "tracker" / item.name).symlink_to(item)
    (w / "tracker/moved_ids.json").write_text(json.dumps(moved))
    s = tmp_path / "site"
    (s / "data").mkdir(parents=True)
    (s / "index.html").write_text(_INDEX_HIDDEN)
    # publish.py runs the site's tools/build_index.js (which reads the REAL
    # index.html next to the script, through the symlink).
    (s / "tools").mkdir()
    (s / "tools" / "build_index.js").symlink_to(Path(__file__).parent / "tools" / "build_index.js")
    return w, s


def _run_publish(w, s, *extra):
    return subprocess.run([sys.executable, str(Path(__file__).parent / "publish.py"),
                           "--working", str(w), "--site", str(s), *extra],
                          capture_output=True, text=True)


def test_publish_refuses_when_moved_target_is_hidden(tmp_path):
    w, s = _e2e_dirs(tmp_path, _MOVE)
    r = _run_publish(w, s)
    assert r.returncode == 1
    assert "ERROR: moved entries target hidden tracker(s): trumpfamily." in r.stdout
    assert list((s / "data").glob("*.json")) == []


def test_publish_dry_run_only_warns_about_hidden_moved_target(tmp_path):
    w, s = _e2e_dirs(tmp_path, _MOVE)
    r = _run_publish(w, s, "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARNING: moved entries target hidden tracker(s): trumpfamily" in r.stdout


def test_publish_writes_empty_moved_ids(tmp_path):
    w, s = _e2e_dirs(tmp_path, {})
    r = _run_publish(w, s)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads((s / "data/moved-ids.json").read_text()) == {}


def test_publish_empty_dai_dir_writes_empty_array(tmp_path):
    src = tmp_path / "dai" / "entries"
    src.mkdir(parents=True)
    (src / ".gitkeep").write_text("")
    dest = tmp_path / "dai.json"
    included, excluded = publish_json_entries(src, dest, set())
    assert included == [] and excluded == 0
    assert json.loads(dest.read_text()) == []


def test_publish_main_has_a_dai_block():
    text = (Path(__file__).parent / "publish.py").read_text(encoding="utf-8")
    assert 'working / "dai" / "entries"' in text and 'site / "data" / "dai.json"' in text
    assert 'TIMELINE_FIELDS["dai"]' in text


def test_write_site_meta_writes_iso_date(tmp_path):
    dest = tmp_path / "site_meta.json"
    result = write_site_meta(dest, date(2026, 11, 1))
    assert result == {"updated": "2026-11-01"}
    assert json.loads(dest.read_text()) == {"updated": "2026-11-01"}


def test_write_site_meta_dry_run_writes_nothing(tmp_path):
    dest = tmp_path / "site_meta.json"
    write_site_meta(dest, date(2026, 11, 1), dry_run=True)
    assert not dest.exists()


def test_status_stage_passes_through(tmp_path):
    # publish keeps every non-underscore key, so the curated status_stage
    # field must reach the published JSON untouched.
    source_dir = tmp_path / "entries"
    source_dir.mkdir()
    entry = {"id": "staged-entry", "status_stage": "In court"}
    (source_dir / "staged-entry.json").write_text(json.dumps(entry))

    dest_file = tmp_path / "output" / "deregulation.json"
    included, _ = publish_json_entries(source_dir, dest_file, excluded_ids=set())

    assert included[0]["status_stage"] == "In court"
    assert json.loads(dest_file.read_text())[0]["status_stage"] == "In court"


def test_moved_to_site_keys_maps_tap_data_names_once():
    import publish as publish_mod
    moved = {"g": {"from": "government-services", "to": "dai", "date": "d"},
             "n": {"from": "oea", "to": "government-services", "date": "d"},
             "k": {"from": "prosecution", "to": "trumpfamily", "date": "d"}}
    assert publish_mod.moved_to_site_keys(moved) == {
        "g": {"from": "govservices", "to": "dai", "date": "d"},
        "n": {"from": "oea", "to": "govservices", "date": "d"},
        "k": {"from": "prosecution", "to": "trumpfamily", "date": "d"}}


# --- Possible Illegality (data/illegality.json) ---

def _illegality_tree(tmp_path, entry_ids, filed=None, laws=None, screened=""):
    """_e2e_dirs tree with trumpfamily entries `entry_ids` and an illegality/
    data folder. `filed` is {id: law_key} (one violation each)."""
    w, s = _e2e_dirs(tmp_path, {})
    ent = w / "trumpfamily" / "entries"
    ent.mkdir()
    for i in entry_ids:
        (ent / f"{i}.json").write_text(json.dumps({"id": i}))
    d = w / "illegality"
    (d / "entries").mkdir(parents=True)
    (d / "laws.json").write_text(json.dumps(
        laws if laws is not None else {"fraud": {"name": "Wire fraud", "label": "criminal"}}))
    (d / "screened-none.txt").write_text(screened)
    for fid, law in (filed or {}).items():
        (d / "entries" / f"{fid}.json").write_text(json.dumps({
            "id": fid, "reviewed": "2026-11-19", "source_version": "2026-11-19",
            "violations": [{"law": law, "who": "Someone", "why": "Because."}]}))
    return w, s


def test_illegality_empty_folder(tmp_path):
    w, s = _illegality_tree(tmp_path, ["a", "b"])
    r = _run_publish(w, s)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads((s / "data/illegality.json").read_text())
    assert out["entries"] == {} and out["progress"] == {"screened": 0, "total": 2}
    assert out["version"] == 1 and "=== illegality === 0 listed, 0 of 2 screened, 0 omitted" in r.stdout


def test_illegality_excluded_id_omitted(tmp_path):
    w, s = _illegality_tree(tmp_path, ["a", "b"], filed={"a": "fraud", "b": "fraud"})
    (s / "publish_exclude.txt").write_text("b\n")
    r = _run_publish(w, s)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads((s / "data/illegality.json").read_text())
    assert list(out["entries"]) == ["a"]
    # total counts published entries only; b is withheld, not screened.
    assert out["progress"] == {"screened": 1, "total": 1}
    assert "1 listed, 1 of 1 screened, 1 omitted" in r.stdout


def test_illegality_unknown_law_exits_1_before_writing(tmp_path):
    w, s = _illegality_tree(tmp_path, ["a"], filed={"a": "nope"})
    r = _run_publish(w, s)
    assert r.returncode == 1
    assert 'ERROR: illegality: a: violation 1: unknown law "nope"' in r.stdout
    assert list((s / "data").glob("*.json")) == []


def test_illegality_dry_run_warns_and_writes_nothing(tmp_path):
    w, s = _illegality_tree(tmp_path, ["a"], filed={"a": "nope"})
    r = _run_publish(w, s, "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARNING: illegality: a: violation 1: unknown law" in r.stdout
    assert list((s / "data").glob("*.json")) == []


def test_publish_illegality_screened_none_counts(tmp_path):
    w, s = _illegality_tree(tmp_path, ["a", "b"], screened="b 2026-11-19 nothing\n")
    mod = load_illegality(w)
    rep = publish_illegality(mod, w, s / "data/illegality.json", {"a", "b"}, set())
    assert rep == {"listed": 0, "screened": 1, "total": 2, "omitted": 0}


def _write_ill(w, fid, data):
    (w / "illegality" / "entries" / f"{fid}.json").write_text(json.dumps(data))


def test_illegality_malformed_violations_dry_run_no_crash(tmp_path):
    w, s = _illegality_tree(tmp_path, ["a", "b"])
    _write_ill(w, "a", {"id": "a", "reviewed": "2026-11-19", "source_version": "2026-11-19"})
    _write_ill(w, "b", {"id": "b", "reviewed": "2026-11-19", "source_version": "2026-11-19",
                        "violations": "text"})
    r = _run_publish(w, s, "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Traceback" not in r.stderr
    assert "WARNING: illegality: a: no violations" in r.stdout
    mod = load_illegality(w)
    rep = publish_illegality(mod, w, s / "data/illegality.json", {"a", "b"}, set(),
                             dry_run=True, problems=[])
    assert rep["listed"] == 0


def _cla_filed_tree(tmp_path):
    """A Cabinet-Level id with a file, so validate() asks the site."""
    w, s = _illegality_tree(tmp_path, [])
    cla = w / "prosecution" / "cabinet-level"
    cla.mkdir(parents=True)
    (cla / "c.json").write_text(json.dumps({"id": "c"}))
    _write_ill(w, "c", {"id": "c", "reviewed": "2026-11-19", "source_version": "2026-11-19",
                        "violations": [{"law": "fraud", "who": "Someone", "why": "Because."}]})
    return w, s


def test_illegality_concern_check_uses_site_and_errors_cleanly(tmp_path):
    w, s = _cla_filed_tree(tmp_path)
    r = _run_publish(w, s)
    assert r.returncode == 1
    assert "Traceback" not in r.stderr
    assert "ERROR: illegality: concern check script not found: " + str(s / "tools") in r.stdout


def test_illegality_concern_check_error_is_warning_on_dry_run(tmp_path):
    w, s = _cla_filed_tree(tmp_path)
    r = _run_publish(w, s, "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARNING: illegality: concern check script not found: " + str(s / "tools") in r.stdout


# --- Reporting: drop the unused unlabeled_sections field (lazy-load spec
# phase 1, tap-data docs/superpowers/specs/2026-11-23-site-lazy-load-design.md).
from publish import publish_tracker


def test_publish_tracker_drops_unlabeled_sections_and_keeps_everything_else(tmp_path):
    post = {
        "date": "2026-11-01",
        "title": "Day 1",
        "url": "https://example.com/p/day-1",
        "entries": [{"id": "r-1", "what_happened": "Thing.", "source_urls": ["https://a.example"]}],
        "unlabeled_sections": [{"heading": "Misc", "text": "never shown"}],
    }
    bare = {"date": "2026-11-02", "title": "Day 2", "entries": []}
    source = tmp_path / "posts.json"
    source.write_text(json.dumps([post, bare]))
    dest = tmp_path / "data" / "tracker.json"

    assert publish_tracker(source, dest) == 2

    published = json.loads(dest.read_text())
    assert "unlabeled_sections" not in published[0]
    expected = dict(post)
    del expected["unlabeled_sections"]
    assert published[0] == expected
    assert published[1] == bare


# --- Slim per-tracker index files (lazy-load phase 3b) ---
_INDEX_FILES = ["prosecution.json", "deregulation.json", "government-services.json",
                "trumpfamily.json", "dai.json"]
_INDEX_GLANCE = {"who": "EPA", "what": "Repealed the rule.",
                 "harm": {"kind": "physical", "certainty": "documented", "who": "Workers"}}


def _index_tree(tmp_path):
    """Temp working + site with one entry in each of the five curated trackers."""
    w, s = _e2e_dirs(tmp_path, {})
    one = {"date_added": "2026-01-01", "last_verified": "2026-01-02", "status_stage": "Unchallenged"}
    folders = {
        "prosecution/cabinet-level": {"id": "cla-1", "official": "Some Official", "offense_category": "Obstruction",
                                      "status": "Under investigation", "confidence_note": "HIGH. text",
                                      "incident_summary": "Something happened.", "evidence": [{"description": "Memo"}]},
        "deregulation/entries": {"id": "cdr-1", "rule_name": "Rule", "domain": "Air", "what_changed": "Changed.",
                                 "sources": [{"name": "A"}]},
        "government-services/entries": {"id": "gsr-1", "title": "Office", "domain": "Health", "what_changed": "Closed.",
                                        "sources": [{"name": "A"}]},
        "trumpfamily/entries": {"id": "tfs-1", "title": "Deal", "category": "Crypto", "family_members": ["Donald Jr."],
                                "what_changed": "A deal.", "sources": []},
        "dai/entries": {"id": "dai-1", "title": "Death", "category": "Deaths", "agencies": ["ICE"],
                        "what_changed": "Died.", "people": {"officials": [{"name": "Kim", "role": "Warden"}]}},
    }
    for folder, entry in folders.items():
        (w / folder).mkdir(parents=True, exist_ok=True)
        (w / folder / (entry["id"] + ".json")).write_text(json.dumps({**one, **entry}))
    return w, s


def test_publish_writes_index_files(tmp_path):
    w, s = _index_tree(tmp_path)
    r = _run_publish(w, s)
    assert r.returncode == 0, r.stdout + r.stderr
    for name in _INDEX_FILES:
        full = json.loads((s / "data" / name).read_text())
        slim = json.loads((s / "data" / "index" / name).read_text())
        assert full and [e["id"] for e in slim] == [e["id"] for e in full], name


def test_index_parity_failure_blocks_publish(tmp_path, monkeypatch, capsys):
    import publish
    w, s = _index_tree(tmp_path)
    real_run = subprocess.run

    def fake_run(cmd, *a, **kw):
        if any(str(c).endswith("build_index.js") for c in cmd):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="gsr-1: filter differs")
        return real_run(cmd, *a, **kw)

    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["publish.py", "--working", str(w), "--site", str(s)])
    with pytest.raises(SystemExit) as exc:
        publish.main()
    assert exc.value.code == 1
    assert "ERROR: index: gsr-1: filter differs" in capsys.readouterr().out


def test_index_failure_is_a_warning_on_dry_run(tmp_path):
    w, s = _index_tree(tmp_path)
    (s / "tools" / "build_index.js").unlink()  # no build script
    r = _run_publish(w, s, "--dry-run")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARNING: index: build script not found" in r.stdout


def test_index_node_missing_still_publishes_everything_else(tmp_path, monkeypatch, capsys):
    """I3: a failed index step must not leave a half-published site. Without
    node the run still writes every other output, removes the (now stale)
    index files so the site loads the full files, and exits 1 at the end."""
    import publish
    w, s = _index_tree(tmp_path)
    (s / "data" / "index").mkdir()
    for name in _INDEX_FILES:  # an older publish's index files
        (s / "data" / "index" / name).write_text("[]\n")
    real_which = publish.shutil.which
    monkeypatch.setattr(publish.shutil, "which", lambda c, *a, **kw: None if c == "node" else real_which(c, *a, **kw))
    monkeypatch.setattr(sys, "argv", ["publish.py", "--working", str(w), "--site", str(s)])
    with pytest.raises(SystemExit) as exc:
        publish.main()
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "ERROR: index:" in out
    for name in ["moved-ids.json", "illegality.json", "site_meta.json", "front-strip.json"] + _INDEX_FILES:
        assert (s / "data" / name).exists(), name
    assert (s / "feed.xml").exists()
    assert list((s / "data" / "index").glob("*.json")) == []


def test_index_parity_failure_removes_that_trackers_index(tmp_path, monkeypatch, capsys):
    """I3: on a parity failure the named tracker's index is removed (the tool
    does it; publish makes sure) and the other trackers' index files stay."""
    import publish
    w, s = _index_tree(tmp_path)
    real_run = subprocess.run

    def fake_run(cmd, *a, **kw):
        res = real_run(cmd, *a, **kw)
        if any(str(c).endswith("build_index.js") for c in cmd):
            return subprocess.CompletedProcess(cmd, 1, stdout=res.stdout, stderr="govservices: gsr-1: filter differs")
        return res

    monkeypatch.setattr(publish.subprocess, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["publish.py", "--working", str(w), "--site", str(s)])
    with pytest.raises(SystemExit) as exc:
        publish.main()
    assert exc.value.code == 1
    assert (s / "feed.xml").exists() and (s / "data" / "site_meta.json").exists()
    left = sorted(p.name for p in (s / "data" / "index").glob("*.json"))
    assert left == sorted(n for n in _INDEX_FILES if n != "government-services.json")
