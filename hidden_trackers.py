"""Which TRACKERS entries in index.html carry `hidden: true`. One parser for
the sync test and publish.py's Phase B guard (tap-data spec
docs/superpowers/specs/2026-10-17-tap-trump-family-phase-b-design.md sec-7)."""
import re
from pathlib import Path


def site_hidden_trackers(index_html):
    html = Path(index_html).read_text(encoding="utf-8")
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
