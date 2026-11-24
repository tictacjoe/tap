#!/usr/bin/env python3
"""
front_strip.py -- builds data/front-strip.json, the data behind the
front-page findings strip (the ledger row of four numbers plus two
featured cards above the search box: one life/health harm and one entry
describing possible illegality).

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

The possible-illegality card (Joe, 2026-11-23) rotates the same way with
its own state (`featured_illegality`, `history_illegality`):
  * Pool: entries in data/illegality.json held by a visible curated
    tracker (not User Topics), with a valid Glance "what" line.
  * Ranking: most recently updated, then tracker, then id.
  * Never the same entry as the life/health card that run.

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
    by_id = {}  # entry id -> (tracker key, entry), for the illegality card
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
            # First tracker wins, like buildIllegalityRows() in index.html.
            if entry.get("id") and entry["id"] not in by_id:
                by_id[entry["id"]] = (key, entry)
            harm = _harm(entry)
            if not harm or harm_tier(harm.get("kind"), harm.get("tier")) != 1:
                continue
            # Averted harms never happened: the #harms view keeps them out of
            # its headline number ("plus N averted"), so the strip does too,
            # and never features one.
            if harm.get("certainty") == "averted":
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

    previous = previous if isinstance(previous, dict) else {}
    featured, history = _rotate(pool, previous.get("featured"), previous.get("history"), today)
    taken = (featured["tracker"], featured["id"]) if featured else None
    ill_pool = [c for c in _illegality_pool(illegality, by_id) if (c["tracker"], c["id"]) != taken]
    featured_ill, history_ill = _rotate(ill_pool, previous.get("featured_illegality"),
                                        previous.get("history_illegality"), today)
    return {"as_of": today.isoformat(), "stats": stats, "featured": featured,
            "history": history, "featured_illegality": featured_ill,
            "history_illegality": history_ill}


def _rotate(pool, prev_featured, prev_history, today):
    """One card's rotation step: (featured or None, new history list)."""
    history = [h for h in (prev_history or []) if isinstance(h, dict)]
    featured = _choose(pool, prev_featured, history, today)
    if featured and not featured.get("_kept"):
        history.insert(0, {"tracker": featured["tracker"], "id": featured["id"],
                           "since": featured["since"]})
    if featured:
        featured.pop("_kept", None)
        featured.pop("updated", None)
    return featured, history[:HISTORY_MAX]


def _illegality_pool(illegality, by_id):
    """Candidates for the possible-illegality card, best first. Each shows
    the entry's first possible-violation record (law, who, why) and how many
    more it has."""
    laws = illegality.get("laws") if isinstance(illegality.get("laws"), dict) else {}
    entries = illegality.get("entries") if isinstance(illegality.get("entries"), dict) else {}
    pool = []
    for entry_id, records in entries.items():
        if entry_id not in by_id or not isinstance(records, list) or not records:
            continue
        key, entry = by_id[entry_id]
        glance = entry.get("glance") if isinstance(entry.get("glance"), dict) else {}
        first = records[0] if isinstance(records[0], dict) else {}
        law = laws.get(first.get("law")) if isinstance(laws.get(first.get("law")), dict) else {}
        if not _line(glance.get("what"), 110) or not first.get("law"):
            continue
        pool.append({
            "tracker": key, "id": entry_id, "label": _LABELS[key],
            "what": glance["what"], "status": entry.get("status_stage", ""),
            "law": law.get("name") or first["law"], "cite": law.get("cite", ""),
            "law_label": law.get("label", ""),
            "who": first.get("who", ""), "why": first.get("why", ""),
            "more_laws": len(records) - 1,
            "updated": entry.get("last_substantive_update", ""),
        })
    pool.sort(key=lambda c: (-(_day(c["updated"]) or date.min).toordinal(), c["tracker"], c["id"]))
    return pool


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
    ref = lambda f: f["tracker"] + "/" + f["id"] if f else "none"
    print(f"stats {s['stats']}; featured {ref(s['featured'])}; illegality {ref(s['featured_illegality'])}")
