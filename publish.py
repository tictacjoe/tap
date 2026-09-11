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
                          dry_run: bool = False) -> tuple:
    """Read all *.json files in source_dir, exclude by FILENAME (stem,
    no .json extension) -- not a schema field, since prosecution and
    deregulation don't share a consistent id-field name (prosecution
    uses 'official', a full descriptive string; deregulation uses a
    clean 'id' slug). Filenames are consistent and visible via `ls`,
    so that's the exclude-list key for both. Write a single combined
    JSON array to dest_file. Returns (included, excluded_count)."""
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
        included.append(strip_internal_fields(data))

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

    excluded_ids = load_exclude_list(site)
    print(f"Exclude list: {len(excluded_ids)} entry ID(s) — {sorted(excluded_ids) if excluded_ids else '(none)'}")
    print()

    # --- prosecution ---
    print("=== prosecution ===")
    prosecution_src = working / "prosecution" / "cabinet-level"
    if prosecution_src.exists():
        included, excl_count = publish_json_entries(
            prosecution_src, site / "data" / "prosecution.json",
            excluded_ids, dry_run=args.dry_run
        )
        print(f"  {len(included)} entries published, {excl_count} excluded")
    else:
        print(f"  WARNING: {prosecution_src} not found, skipping")
    print()

    # --- deregulation ---
    print("=== deregulation ===")
    deregulation_src = working / "deregulation" / "entries"
    if deregulation_src.exists():
        included, excl_count = publish_json_entries(
            deregulation_src, site / "data" / "deregulation.json",
            excluded_ids, dry_run=args.dry_run
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
            excluded_ids, dry_run=args.dry_run
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
