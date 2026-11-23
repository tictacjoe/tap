#!/usr/bin/env python3
"""
front_strip.py -- builds data/front-strip.json, the data behind the
front-page findings strip (the ledger row of four numbers plus one
featured life/health harm card above the search box).

Spec: tap-data docs/superpowers/specs/2026-11-23-front-strip-design.md

Called by publish.py near the end of a run, after every data/*.json file
is written. Like feed.py it reads the PUBLISHED site data, so entries in
publish_exclude.txt can never show up here.

Featured-entry rotation, in plain words:
  * Pool: tier-1 (life and health) entries with a pull quote and a
    "who was harmed" line.
  * Ranking: "documented" certainty first, then most recently updated,
    then id (so ties always break the same way).
  * Hold: a pick stays up for HOLD_DAYS days.
  * No repeats: a new pick skips anything featured in the last
    NO_REPEAT_DAYS days, unless everything was (then take the top one).
  * The rotation state is the previous front-strip.json itself (its
    `featured` and `history`), so no extra state file is needed.

Run standalone to rebuild from the current site data:
    python3 front_strip.py --site ~/gjoe/tap-site
"""

import argparse
import json
from datetime import date
from pathlib import Path

from feed import FEED_SOURCES  # (file, site key, label, titleField) per curated tracker

HOLD_DAYS = 3
NO_REPEAT_DAYS = 14
HISTORY_MAX = 30
# Trackers that never count toward the life/health number or get featured
# (mirrors HARMS_EXCLUDED_KEYS in index.html; Reporting isn't in FEED_SOURCES).
HARM_EXCLUDED_KEYS = {"communitytopics"}

# Same table as HARM_KIND_DEFAULT_TIER in index.html.
_KIND_DEFAULT_TIER = {"physical": 1, "livelihood": 2, "money": 3}

# Display labels for the card (the feed uses "Claim-check" for User Topics,
# which is never featured, so the feed's labels are fine here).
_LABELS = {key: label for _file, key, label, _title in FEED_SOURCES}


def harm_tier(kind, override):
    """Python twin of harmTier() in index.html: 1, 2, 3 or None."""
    if override in (1, 2, 3):
        return override
    return _KIND_DEFAULT_TIER.get(kind)


def _harm(entry):
    """The entry's glance.harm dict, or None if it has no usable one."""
    glance = entry.get("glance")
    if not isinstance(glance, dict):
        return None
    harm = glance.get("harm")
    if not isinstance(harm, dict) or not harm.get("kind"):
        return None
    return harm


def _load(path, default):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _day(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _rank_key(c):
    """Sort key: documented first, newest update first, then id A-Z."""
    return (0 if c["certainty"] == "documented" else 1,
            # negate the date by sorting on its ordinal, descending
            -(_day(c["updated"]) or date.min).toordinal(),
            c["tracker"], c["id"])


def build_front_strip(site_dir, hidden, today, previous):
    """Return the front-strip dict (see the spec for its shape)."""
    site_dir = Path(site_dir)
    entries_total = 0
    life_health = 0
    pool = []
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
            life_health += 1
            if entry.get("pull_quote") and harm.get("who") and entry.get("id"):
                pool.append({
                    "tracker": key, "id": entry["id"], "label": _LABELS[key],
                    "what": entry["glance"].get("what", ""), "who": harm["who"],
                    "status": entry.get("status_stage", ""),
                    "pull_quote": entry["pull_quote"],
                    "certainty": harm.get("certainty", ""),
                    "updated": entry.get("last_substantive_update", ""),
                })
    pool.sort(key=_rank_key)

    illegality = _load(site_dir / "data" / "illegality.json", {})
    claim_checks = _load(site_dir / "data" / "claim-checks.json", {})
    stats = {
        "entries": entries_total,
        "life_health": life_health,
        "illegality": len(illegality.get("entries", {})) if isinstance(illegality, dict) else 0,
        "claim_checks": len(claim_checks.get("checks", [])) if isinstance(claim_checks, dict) else 0,
    }

    previous = previous if isinstance(previous, dict) else {}
    history = [h for h in previous.get("history", []) if isinstance(h, dict)]
    featured = _choose(pool, previous.get("featured"), history, today)
    if featured and not featured.get("_kept"):
        history.insert(0, {"tracker": featured["tracker"], "id": featured["id"],
                           "since": featured["since"]})
    if featured:
        featured.pop("_kept", None)
        featured.pop("updated", None)
    return {"as_of": today.isoformat(), "stats": stats, "featured": featured,
            "history": history[:HISTORY_MAX]}


def _choose(pool, prev_featured, history, today):
    """Pick the featured entry per the rotation rules; None if pool empty."""
    if not pool:
        return None
    by_ref = {(c["tracker"], c["id"]): c for c in pool}
    # (a) keep the current pick while it's inside the hold window and
    #     still in the pool (matched on tracker AND id).
    if isinstance(prev_featured, dict):
        ref = (prev_featured.get("tracker"), prev_featured.get("id"))
        since = _day(prev_featured.get("since"))
        if ref in by_ref and since and (today - since).days < HOLD_DAYS:
            return {**by_ref[ref], "since": since.isoformat(), "_kept": True}
    # (b) top-ranked entry not featured within NO_REPEAT_DAYS ...
    recent = {(h.get("tracker"), h.get("id")) for h in history
              if (_day(h.get("since")) or date.min) > date.fromordinal(
                  max(1, today.toordinal() - NO_REPEAT_DAYS))}
    for c in pool:
        if (c["tracker"], c["id"]) not in recent:
            return {**c, "since": today.isoformat()}
    # (c) ... or, if everything was featured recently, the top-ranked one.
    return {**pool[0], "since": today.isoformat()}


def write_front_strip(site_dir, hidden, today, dry_run=False):
    """Build from the previous data/front-strip.json and write the new one."""
    path = Path(site_dir) / "data" / "front-strip.json"
    previous = _load(path, None)
    strip = build_front_strip(site_dir, hidden, today, previous)
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
    f = s["featured"]
    print(f"stats {s['stats']}; featured {f['tracker'] + '/' + f['id'] if f else 'none'}")
