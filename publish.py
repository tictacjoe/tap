#!/usr/bin/env python3
"""
publish.py

Copies data from the PRIVATE working repo (~/gjoe/tap-data/) into the
PUBLIC site repo's data/ folder, applying an exclude list so nothing
gets published until you've deliberately decided it's ready.

This does NOT commit or push anything -- it only writes files into the
site repo's working directory. You review with `git diff` in the site
repo and commit/push yourself. That review step is the actual safety
net; this script is just the copy-and-filter mechanism.

Directory assumptions (override with flags if yours differ):
  Working repo:  ~/gjoe/tap-data/
    prosecution/cabinet-level/*.json
    deregulation/entries/*.json
    government-services/entries/*.json
    community-topics/entries/*.json
    tracker/output/posts.json

  Site repo:     ~/gjoe/tap-site/
    data/prosecution.json
    data/deregulation.json
    data/government-services.json
    data/community-topics.json
    data/tracker.json
    publish_exclude.txt   <- entry IDs to exclude, one per line, '#' for comments

Usage:
  python3 publish.py
  python3 publish.py --working ~/gjoe/tap-data --site ~/gjoe/tap-site
  python3 publish.py --dry-run
"""

import json
import sys
import argparse
from pathlib import Path


def load_exclude_list(site_dir: Path) -> set:
    exclude_file = site_dir / "publish_exclude.txt"
    if not exclude_file.exists():
        return set()
    excluded = set()
    for line in exclude_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            excluded.add(line)
    return excluded


def strip_internal_fields(entry: dict) -> dict:
    """Working-repo entries can carry underscore-prefixed top-level
    fields (e.g. `_leaner_pass`) for internal editorial tracking --
    never meant for the public site. Strip any such key before
    publishing."""
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def publish_json_entries(source_dir: Path, dest_file: Path, excluded_ids: set,
                          dry_run: bool = False, check_glance=None,
                          update_markers=None, timeline_fields=()) -> tuple:
    """Read all *.json files in source_dir, exclude by FILENAME (stem,
    no .json extension) -- not a schema field, since prosecution and
    deregulation don't share a consistent id-field name (prosecution
    uses 'official', a full descriptive string; deregulation uses a
    clean 'id' slug). Filenames are consistent and visible via `ls`,
    so that's the exclude-list key for both. Write a single combined
    JSON array to dest_file. Returns (included, excluded_count).

    check_glance, when given, is called with each entry's glance block;
    a block with problems is stripped (the entry itself is still
    published) and a WARNING is printed, so a malformed block can never
    reach the site.

    update_markers, when given (the module from load_update_markers),
    builds each entry's `timeline` object from the text fields named in
    timeline_fields and adds it next to the untouched prose. `timeline`
    is a reserved key: one already present in a source entry is dropped
    with a WARNING."""
    files = sorted(source_dir.glob("*.json"))
    included = []
    excluded_count = 0

    for f in files:
        if f.stem in excluded_ids:
            excluded_count += 1
            print(f"    excluded: {f.stem}")
            continue
        with open(f) as fh:
            data = json.load(fh)
        published = strip_internal_fields(data)
        if check_glance is not None and "glance" in published:
            problems = check_glance(published["glance"])
            if problems:
                print(f"    WARNING: malformed glance stripped from {f.stem}: {'; '.join(problems)}")
                del published["glance"]
        if update_markers is not None:
            if "timeline" in published:
                print(f"    WARNING: {f.stem} already has a 'timeline' key; overwriting")
                del published["timeline"]
            timeline = update_markers.build_timeline(
                published, timeline_fields,
                warn=lambda message, stem=f.stem: print(f"    WARNING: {stem}: {message}"))
            if timeline:
                published["timeline"] = timeline
        included.append(published)

    if not dry_run:
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_file, "w") as fh:
            json.dump(included, fh, indent=2, ensure_ascii=False)
            fh.write("\n")

    return included, excluded_count


def publish_tracker(source_file: Path, dest_file: Path, dry_run: bool = False) -> int:
    """tracker is already a single combined posts.json -- straight copy,
    no per-entry exclude list applied (it's a scraped archive, not
    individually-authored research claims)."""
    if not source_file.exists():
        print(f"    WARNING: {source_file} not found, skipping tracker")
        return 0
    with open(source_file) as fh:
        data = json.load(fh)
    if not dry_run:
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_file, "w") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    return len(data)


def load_glance_checker(working: Path):
    """Imports check_glance from the working repo's tracker/validate_glance.py
    so the publish guard and the authoring tools share one set of rules."""
    tracker_dir = str(working / "tracker")
    if tracker_dir not in sys.path:
        sys.path.insert(0, tracker_dir)
    from validate_glance import check_glance
    return check_glance


def load_update_markers(working: Path):
    """Imports update_markers from the working repo's tracker/ folder so
    publish and the tests share one parser (same pattern as
    load_glance_checker)."""
    tracker_dir = str(working / "tracker")
    if tracker_dir not in sys.path:
        sys.path.insert(0, tracker_dir)
    import update_markers
    return update_markers


CLAIMS_RELATIVE = Path("tracker/output/atomic-claims/claims.json")


def load_claim_checks(working: Path):
    """Imports claim_checks_public from the working repo's tracker/ folder so
    publish and the tests share one mapping and one guard (same pattern as
    load_glance_checker / load_update_markers)."""
    tracker_dir = str(working / "tracker")
    if tracker_dir not in sys.path:
        sys.path.insert(0, tracker_dir)
    import claim_checks_public
    return claim_checks_public


def publish_claim_checks(module, claims_file: Path, published_entries: list,
                         dest_file: Path, dry_run: bool = False):
    """Write the public check file for the Evidence drawer from the internal
    claims.json, through the module's state mapping and stale guard. Returns the
    report dict, or None (with a WARNING) when claims.json is missing. Only
    entries in published_entries are considered, so an excluded entry can never
    leak a check."""
    if not claims_file.exists():
        print(f"    WARNING: {claims_file} not found, claim-checks.json not written")
        return None
    with open(claims_file, encoding="utf-8") as fh:
        claims = json.load(fh)
    entries = {e["id"]: e for e in published_entries if "id" in e}
    public, report = module.build_public_checks(
        claims, entries, warn=lambda message: print(f"    WARNING: {message}"))
    if not dry_run:
        dest_file.parent.mkdir(parents=True, exist_ok=True)
        with open(dest_file, "w", encoding="utf-8") as fh:
            json.dump(public, fh, indent=1, ensure_ascii=False)
            fh.write("\n")
    print(f"  claim checks: {report['published']} published, {report['dropped_stale']} dropped as stale, "
          f"{report['unchecked']} evidence items without a check, {report['withheld']} withheld for review")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--working", default=str(Path.home() / "gjoe/tap-data"),
                         help="Path to the private working repo")
    parser.add_argument("--site", default=str(Path.home() / "gjoe/tap-site"),
                         help="Path to the public site repo")
    parser.add_argument("--dry-run", action="store_true",
                         help="Show what would be published without writing files")
    args = parser.parse_args()

    working = Path(args.working)
    site = Path(args.site)

    if not working.exists():
        print(f"ERROR: working repo not found at {working}")
        sys.exit(1)
    if not site.exists():
        print(f"ERROR: site repo not found at {site}")
        print("Create it first (see setup instructions) before running publish.py")
        sys.exit(1)

    try:
        check_glance = load_glance_checker(working)
    except ImportError as exc:
        print(f"ERROR: cannot load validate_glance from {working / 'tracker'}: {exc}")
        sys.exit(1)

    try:
        update_markers = load_update_markers(working)
    except ImportError as exc:
        print(f"ERROR: cannot load update_markers from {working / 'tracker'}: {exc}")
        sys.exit(1)

    try:
        claim_checks = load_claim_checks(working)
    except ImportError as exc:
        print(f"ERROR: cannot load claim_checks_public from {working / 'tracker'}: {exc}")
        sys.exit(1)

    excluded_ids = load_exclude_list(site)
    print(f"Exclude list: {len(excluded_ids)} entry ID(s) — {sorted(excluded_ids) if excluded_ids else '(none)'}")
    print()

    # --- prosecution ---
    print("=== prosecution ===")
    prosecution_src = working / "prosecution" / "cabinet-level"
    if prosecution_src.exists():
        included, excl_count = publish_json_entries(
            prosecution_src, site / "data" / "prosecution.json",
            excluded_ids, dry_run=args.dry_run, check_glance=check_glance,
            update_markers=update_markers,
            timeline_fields=update_markers.TIMELINE_FIELDS["prosecution"]
        )
        print(f"  {len(included)} entries published, {excl_count} excluded")
        publish_claim_checks(claim_checks, working / CLAIMS_RELATIVE, included,
                             site / "data" / "claim-checks.json", dry_run=args.dry_run)
    else:
        print(f"  WARNING: {prosecution_src} not found, skipping")
    print()

    # --- deregulation ---
    print("=== deregulation ===")
    deregulation_src = working / "deregulation" / "entries"
    if deregulation_src.exists():
        included, excl_count = publish_json_entries(
            deregulation_src, site / "data" / "deregulation.json",
            excluded_ids, dry_run=args.dry_run, check_glance=check_glance,
            update_markers=update_markers,
            timeline_fields=update_markers.TIMELINE_FIELDS["deregulation"]
        )
        print(f"  {len(included)} entries published, {excl_count} excluded")
    else:
        print(f"  WARNING: {deregulation_src} not found, skipping")
    print()

    # --- government services (redirected) ---
    print("=== government-services ===")
    govservices_src = working / "government-services" / "entries"
    if govservices_src.exists():
        included, excl_count = publish_json_entries(
            govservices_src, site / "data" / "government-services.json",
            excluded_ids, dry_run=args.dry_run, check_glance=check_glance,
            update_markers=update_markers,
            timeline_fields=update_markers.TIMELINE_FIELDS["government-services"]
        )
        print(f"  {len(included)} entries published, {excl_count} excluded")
    else:
        print(f"  WARNING: {govservices_src} not found, skipping")
    print()

    # --- community topics ---
    print("=== community-topics ===")
    communitytopics_src = working / "community-topics" / "entries"
    if communitytopics_src.exists():
        included, excl_count = publish_json_entries(
            communitytopics_src, site / "data" / "community-topics.json",
            excluded_ids, dry_run=args.dry_run
        )
        print(f"  {len(included)} entries published, {excl_count} excluded")
    else:
        print(f"  WARNING: {communitytopics_src} not found, skipping")
    print()

    # --- tracker ---
    print("=== tracker ===")
    tracker_src = working / "tracker" / "output" / "posts.json"
    count = publish_tracker(tracker_src, site / "data" / "tracker.json", dry_run=args.dry_run)
    print(f"  {count} posts published (no per-entry exclude list applied)")
    print()

    print("---")
    if args.dry_run:
        print("DRY RUN — no files were written. Re-run without --dry-run to publish.")
    else:
        print(f"Done. Now review and commit in the site repo:")
        print(f"  cd {site}")
        print(f"  git diff data/")
        print(f"  git add data/")
        print(f"  git commit -m \"publish: update site data ($(date +%Y-%m-%d))\"")
        print(f"  git push")


if __name__ == "__main__":
    main()
