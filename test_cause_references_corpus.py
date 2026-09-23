"""Invariants of published `cause` / `cause_references` across all three
trackers (spec 2026-09-23 sec-6 test 4). A later copy edit to `cause` can
silently break a link -- the renderer drops a stale match without error --
so this catches it at publish time instead."""
import json
from pathlib import Path

import pytest

SITE = Path(__file__).parent
FILES = {
    "prosecution": "prosecution.json",
    "deregulation": "deregulation.json",
    "government-services": "government-services.json",
}
LABEL = "[TAP Analysis, not sourced]"


def _entries(tracker):
    data = json.loads((SITE / "data" / FILES[tracker]).read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data["entries"]


IDS = {t: {e["id"] for e in _entries(t)} for t in FILES}


@pytest.mark.parametrize("tracker", FILES)
def test_every_cause_reference_matches_its_cause_and_targets_a_real_entry(tracker):
    problems = []
    for e in _entries(tracker):
        cause = e.get("cause") or ""
        for ref in e.get("cause_references") or []:
            if ref.get("match") not in cause:
                problems.append((e["id"], "match not in cause", ref.get("match")))
            if ref.get("tracker") not in IDS:
                problems.append((e["id"], "unknown tracker", ref.get("tracker")))
            elif ref.get("id") not in IDS[ref["tracker"]]:
                problems.append((e["id"], "missing target", ref.get("tracker"), ref.get("id")))
    assert problems == []


@pytest.mark.parametrize("tracker", FILES)
def test_cause_references_never_appear_without_a_cause(tracker):
    bad = [e["id"] for e in _entries(tracker) if e.get("cause_references") and not e.get("cause")]
    assert bad == []


@pytest.mark.parametrize("tracker", ["deregulation", "government-services"])
def test_gsr_and_cdr_causes_open_with_the_analysis_label(tracker):
    bad = [e["id"] for e in _entries(tracker) if e.get("cause") and not e["cause"].startswith(LABEL)]
    assert bad == []
