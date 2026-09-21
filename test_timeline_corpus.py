"""Invariants of the published `timeline` objects, checked against the real
data/*.json (skipped when the working repo is absent)."""
import json
import re
import sys
from pathlib import Path

import pytest

SITE = Path(__file__).parent
TAP_DATA = Path.home() / "gjoe/tap-data"
FILES = {
    "deregulation": "deregulation.json",
    "government-services": "government-services.json",
    "prosecution": "prosecution.json",
}
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

pytestmark = pytest.mark.skipif(
    not (TAP_DATA / "tracker/update_markers.py").exists(),
    reason="tap-data working repo not present")


def _markers():
    sys.path.insert(0, str(TAP_DATA / "tracker"))
    import update_markers
    return update_markers


def _entries(tracker):
    return json.loads((SITE / "data" / FILES[tracker]).read_text())


def _no_ws(text):
    return re.sub(r"\s+", "", text)


@pytest.mark.parametrize("tracker", FILES)
def test_every_timeline_reassembles_to_its_prose_field(tracker):
    for entry in _entries(tracker):
        for field, part in (entry.get("timeline") or {}).items():
            rebuilt = part["base"] + "".join(u["text"] for u in part["updates"])
            assert _no_ws(rebuilt) == _no_ws(entry[field]), (entry.get("id"), field)


@pytest.mark.parametrize("tracker", FILES)
def test_every_update_has_valid_dates_and_a_consistent_effective_date(tracker):
    for entry in _entries(tracker):
        for field, part in (entry.get("timeline") or {}).items():
            inherited = None
            for u in part["updates"]:
                assert u["label"] in ("Update", "Added")
                assert u["text"].startswith(u["label"]), (entry.get("id"), field)
                if u["date"] is not None:
                    assert DATE.match(u["date"]), (entry.get("id"), field)
                    inherited = u["date"]
                assert u["effective_date"] == inherited, (entry.get("id"), field)


@pytest.mark.parametrize("tracker", FILES)
def test_every_marker_carrying_field_has_a_timeline_entry(tracker):
    markers = _markers()
    for entry in _entries(tracker):
        for field in markers.TIMELINE_FIELDS[tracker]:
            text = entry.get(field)
            if isinstance(text, str) and markers.MARKER_RE.search(text):
                assert field in (entry.get("timeline") or {}), (entry.get("id"), field)
