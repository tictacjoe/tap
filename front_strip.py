#!/usr/bin/env python3
"""
front_strip.py -- builds data/front-strip.json, the data behind the
front-page findings strip: the ledger row of four numbers above the
search box (curated entries, harms to life or health, entries describing
possible illegality, uncurated reporting).

Spec: tap-data docs/superpowers/specs/2026-11-23-front-strip-design.md.
The spec's two featured cards (and their 3-day rotation) were removed
2026-11-24 (Joe), from the page and from this file; the file now holds
only `as_of` and `stats`.

Called by publish.py near the end of a run, after every data/*.json file
is written. Like feed.py it reads the PUBLISHED site data, so entries in
publish_exclude.txt can never show up here.

Run standalone to rebuild from the current site data:
    python3 front_strip.py --site ~/gjoe/tap-site
"""

import argparse
import json
from datetime import date
from pathlib import Path

from feed import FEED_SOURCES  # (file, site key, label, titleField) per curated tracker

# Trackers that never count toward the life/health number
# (mirrors HARMS_EXCLUDED_KEYS in index.html; Reporting isn't in FEED_SOURCES).
HARM_EXCLUDED_KEYS = {"communitytopics"}

# Same table as HARM_KIND_DEFAULT_TIER in index.html.
_KIND_DEFAULT_TIER = {"physical": 1, "livelihood": 2, "money": 3}

def harm_tier(kind, override):
    """Python twin of harmTier() in index.html: 1, 2, 3 or None."""
    if override in (1, 2, 3):
        return override
    return _KIND_DEFAULT_TIER.get(kind)


# Same lists as GLANCE_HARM_LABELS / GLANCE_CERTAINTIES in index.html.
_HARM_KINDS = {"physical", "rights", "livelihood", "money", "environment", "institutional"}
_CERTAINTIES = {"documented", "projected", "alleged", "averted"}


def _line(value, max_len):
    """isValidGlance()'s line(): non-blank one-line string of <= max_len chars."""
    return (isinstance(value, str) and value.strip() != "" and len(value) <= max_len
            and "\n" not in value and "\r" not in value)


def _harm(entry):
    """The entry's glance.harm dict if its Glance passes the same check as
    isValidGlance() in index.html (so this count always matches the #harms
    view), else None."""
    glance = entry.get("glance")
    if not isinstance(glance, dict):
        return None
    harm = glance.get("harm")
    if not (_line(glance.get("who"), 50) and _line(glance.get("what"), 110)
            and isinstance(harm, dict) and harm.get("kind") in _HARM_KINDS
            and harm.get("certainty") in _CERTAINTIES and _line(harm.get("who"), 40)):
        return None
    # Optional tier override: absent, or exactly the integer 1, 2 or 3
    # (bool is an int subclass in Python, so rule it out explicitly).
    if "tier" in harm and (isinstance(harm["tier"], bool) or harm["tier"] not in (1, 2, 3)):
        return None
    return harm


def _load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def build_front_strip(site_dir, hidden, today):
    """Return the front-strip dict: {"as_of": ..., "stats": {...}}."""
    site_dir = Path(site_dir)
    entries_total = 0
    life_health = 0
    for filename, key, _label, _title in FEED_SOURCES:
        if key in hidden:
            continue
        data = _load(site_dir / "data" / filename, [])
        if not isinstance(data, list):
            continue
        entries_total += len(data)
        if key in HARM_EXCLUDED_KEYS:
            continue
        for entry in data:
            harm = _harm(entry)
            if not harm or harm_tier(harm.get("kind"), harm.get("tier")) != 1:
                continue
            # Averted harms never happened: the #harms view keeps them out of
            # its headline number ("plus N averted"), so the strip does too.
            if harm.get("certainty") == "averted":
                continue
            life_health += 1

    illegality = _load(site_dir / "data" / "illegality.json", {})
    if not isinstance(illegality, dict):
        illegality = {}
    # Reporting (the uncurated archive) lives in tracker.json, not in
    # FEED_SOURCES; same number as the "Uncurated reporting (N)" option.
    reporting = [] if "tracker" in hidden else _load(site_dir / "data" / "tracker.json", [])
    stats = {
        "entries": entries_total,
        "life_health": life_health,
        "illegality": len(illegality.get("entries", {})),
        "reporting": len(reporting) if isinstance(reporting, list) else 0,
    }
    return {"as_of": today.isoformat(), "stats": stats}


def write_front_strip(site_dir, hidden, today, dry_run=False):
    """Build data/front-strip.json and write it (unless dry_run)."""
    path = Path(site_dir) / "data" / "front-strip.json"
    strip = build_front_strip(site_dir, hidden, today)
    if not dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(strip, indent=2) + "\n", encoding="utf-8")
    return strip


if __name__ == "__main__":
    import hidden_trackers
    parser = argparse.ArgumentParser(description="Rebuild data/front-strip.json from site data")
    parser.add_argument("--site", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()
    site = Path(args.site).expanduser()
    s = write_front_strip(site, hidden_trackers.site_hidden_trackers(site / "index.html"), date.today())
    print(f"stats {s['stats']}")
