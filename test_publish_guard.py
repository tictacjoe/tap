"""Publish guard (tap-data spec 2026-10-17-tap-trump-family-phase-b-design.md sec-7)."""
import json
import subprocess
import sys
from pathlib import Path

import hidden_trackers
import publish

SITE = Path(__file__).parent

INDEX_HIDDEN = """const TRACKERS = {
  govservices: {
    label: "x",
  },
  trumpfamily: {
    label: "Trump Family",
    hidden: true,
  },
};
"""


def test_parser_reads_hidden_flags(tmp_path):
    p = tmp_path / "index.html"
    p.write_text(INDEX_HIDDEN)
    assert hidden_trackers.site_hidden_trackers(p) == {"trumpfamily"}
    p.write_text(INDEX_HIDDEN.replace("    hidden: true,\n", ""))
    assert hidden_trackers.site_hidden_trackers(p) == set()


def _working(tmp_path, moved):
    w = tmp_path / "working"
    (w / "trumpfamily").mkdir(parents=True)
    (w / "trumpfamily/moved_ids.json").write_text(json.dumps(moved))
    return w


def test_moved_targets_hidden(tmp_path):
    site = tmp_path / "site"
    site.mkdir()
    (site / "index.html").write_text(INDEX_HIDDEN)
    w = _working(tmp_path, {"m1": {"from": "prosecution", "to": "trumpfamily", "date": "2026-10-20"}})
    assert publish.moved_targets_hidden(w, site) == {"trumpfamily"}
    assert publish.moved_targets_hidden(_working(tmp_path / "b", {}), site) == set()
    (site / "index.html").write_text(INDEX_HIDDEN.replace("    hidden: true,\n", ""))
    assert publish.moved_targets_hidden(w, site) == set()


def test_real_index_matches_sync_parser():
    assert hidden_trackers.site_hidden_trackers(SITE / "index.html") == {"trumpfamily"}
