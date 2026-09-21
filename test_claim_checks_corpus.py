"""Invariants of the published data/claim-checks.json against the real published entries
(skipped when the working repo is absent)."""
import json
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).parent
TAP_DATA = Path.home() / "gjoe/tap-data"
PUBLIC_STATES = {"supports", "partly", "not_found", "unopened", "differs"}
CHECK_KEYS = {"state", "why", "host", "date", "kind", "archive"}

pytestmark = pytest.mark.skipif(
    not (TAP_DATA / "tracker/claim_checks_public.py").exists(),
    reason="tap-data working repo not present")


def _module():
    sys.path.insert(0, str(TAP_DATA / "tracker"))
    import claim_checks_public
    return claim_checks_public


def _published():
    entries = json.loads((SITE / "data" / "prosecution.json").read_text())
    return {e["id"]: e for e in entries}


def _checks_file():
    return json.loads((SITE / "data" / "claim-checks.json").read_text())


def test_every_check_points_at_a_real_evidence_position_and_uses_a_public_state():
    entries = _published()
    data = _checks_file()
    assert data["version"] == 1
    for entry_id, positions in data["checks"].items():
        assert entry_id in entries, entry_id
        for position, check in positions.items():
            assert 0 <= int(position) < len(entries[entry_id]["evidence"]), (entry_id, position)
            assert set(check) == CHECK_KEYS, (entry_id, position)
            assert check["state"] in PUBLIC_STATES, (entry_id, position)
            assert check["kind"] in ("fact", "interpretation")
            assert isinstance(check["archive"], bool)


def test_no_internal_field_reaches_the_public_file():
    text = (SITE / "data" / "claim-checks.json").read_text()
    for forbidden in ("source_excerpt", "claim_text", "verdict_rationale", "corroborating_sources", "human_review"):
        assert forbidden not in text, forbidden


def test_no_published_why_is_machine_text_and_no_state_is_claimed_falsely():
    """Every rationale in the live file is reader-facing prose: the screen in
    claim_checks_public must leave no pipeline vocabulary, evidence position or
    tool internal behind, no unopened check may carry a rationale at all, and no
    "claim not found" may rest on a page the checker could not read."""
    ccp = _module()
    for entry_id, positions in _checks_file()["checks"].items():
        for position, check in positions.items():
            why = check["why"]
            where = (entry_id, position, why[:120])
            assert not ccp.INTERNAL_VOCAB.search(why), where
            assert not ccp.EVIDENCE_REF.search(why), where
            assert not ccp.TOOL_INTERNALS.search(why), where
            if check["state"] == "unopened":
                assert why == "", where
            if check["state"] == "not_found":
                assert not ccp.READ_FAILURE.search(why), where
                assert not ccp.PARTIAL_READ.search(why), where


def test_as_of_is_the_latest_check_date():
    data = _checks_file()
    dates = [c["date"] for positions in data["checks"].values() for c in positions.values()]
    assert data["as_of"] == max(dates)


def test_the_file_regenerates_exactly_from_the_internal_claims():
    claims_path = TAP_DATA / "tracker/output/atomic-claims/claims.json"
    if not claims_path.exists():
        pytest.skip("internal claims.json not present")
    claims = json.loads(claims_path.read_text())
    public, _ = _module().build_public_checks(claims, _published())
    assert public == _checks_file()


def test_published_checks_plus_unchecked_items_equal_the_evidence_item_count():
    entries = _published()
    checks = _checks_file()["checks"]
    total = sum(len(e["evidence"]) for e in entries.values())
    published = sum(len(p) for p in checks.values())
    unchecked = sum(1 for entry_id, entry in entries.items()
                    for position in range(len(entry["evidence"]))
                    if str(position) not in checks.get(entry_id, {}))
    assert 0 < published <= total
    assert published + unchecked == total
