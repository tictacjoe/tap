"""The site's hidden trackers (TRACKERS[key].hidden) and the connector's
HIDDEN_TRACKERS must be the same set, so a tracker is never public in one
and hidden in the other. Spec: tap-data
docs/superpowers/specs/2026-10-17-tap-trump-family-tracker-design.md."""
import re
from pathlib import Path

import pytest

SITE = Path(__file__).parent
DATA_PY = Path.home() / "gjoe/tap-data/connector/tap_connector/data.py"


def site_hidden():
    html = (SITE / "index.html").read_text(encoding="utf-8")
    block = html[html.index("const TRACKERS = {"):]
    block = block[:block.index("\n};")]
    hidden, current = set(), None
    for line in block.splitlines():
        m = re.match(r"^  ([a-z]+): \{", line)
        if m:
            current = m.group(1)
        elif re.match(r"^\s+hidden: true,", line):
            hidden.add(current)
    return hidden


@pytest.mark.skipif(not DATA_PY.exists(), reason="tap-data working repo not present")
def test_site_and_connector_hide_the_same_trackers():
    m = re.search(r"^HIDDEN_TRACKERS = \{([^}]*)\}", DATA_PY.read_text(encoding="utf-8"), re.M)
    connector = set(re.findall(r'"([a-z]+)"', m.group(1)))
    assert site_hidden() == connector == {"trumpfamily"}
