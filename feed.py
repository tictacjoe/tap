#!/usr/bin/env python3
"""
feed.py -- builds feed.xml, TAP's RSS 2.0 "what's new" feed.

Called by publish.py at the end of a run (after every data/*.json file is
written), so the feed always matches what the site is showing. It reads
the PUBLISHED site data, not tap-data, which means excluded entries
(publish_exclude.txt) are already filtered out and can't leak.

What goes in:
  * One <item> per curated entry, newest `date_added` first, capped at
    `limit` items (default 50) so the file stays small.
  * Every curated tracker except ones still hidden on the site
    (hidden_trackers.site_hidden_trackers reads that from index.html).
  * NOT Reporting (tracker.json): that's a third-party archive TAP does
    not verify, so it shouldn't arrive in a reader's feed looking like a
    TAP entry.

Each item links to the entry's deep link (#<siteKey>/<id>), the same URL
the "Copy link" button produces, and uses it as the stable <guid> so feed
readers never show an entry twice.

Run standalone to (re)build the feed from the current site data:
    python3 feed.py --site ~/gjoe/tap-site
"""

import argparse
import json
from datetime import date, datetime
from email.utils import format_datetime
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

SITE_URL = "https://tictacjoe.github.io/tap/"

# (data file, site tracker key used in deep links, label, titleField fallback)
# Labels and titleFields mirror the TRACKERS config in index.html.
FEED_SOURCES = [
    ("deregulation.json", "deregulation", "Corporate Deregulation", "rule_name"),
    ("prosecution.json", "prosecution", "Cabinet-Level Accountability", "official"),
    ("government-services.json", "govservices", "Government Service Redirection", "title"),
    ("trumpfamily.json", "trumpfamily", "Trump Family", "title"),
    ("dai.json", "dai", "DHS and ICE", "title"),
    ("community-topics.json", "communitytopics", "Claim-check", "topic"),
]


def _parse_day(value):
    """'2026-10-18' (or '2026-10-18T...') -> date, else None."""
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _rfc822(day):
    """RSS wants RFC 822 dates, e.g. 'Wed, 04 Mar 2026 12:00:00 +0000'.
    Noon UTC so the day doesn't shift backward in US time zones."""
    from datetime import timezone
    return format_datetime(datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc))


def _item_text(entry, label, title_field):
    """(title, description) for one entry.

    Title: the glance one-liner ("what") is the best headline TAP writes;
    fall back to the tracker's titleField. Description: short_summary
    (or a claim-check's summary), then glance.what, plus the status.
    """
    glance = entry.get("glance") if isinstance(entry.get("glance"), dict) else {}
    headline = glance.get("what") or entry.get(title_field) or entry.get("id", "")
    body = entry.get("short_summary") or entry.get("summary") or glance.get("what") or ""
    status = entry.get("status_stage")
    # glance one-liners have no closing period; add one before "Status:".
    if body and body[-1] not in ".!?":
        body += "."
    if status:
        body = f"{body} Status: {status}." if body else f"Status: {status}."
    return f"{label}: {headline}", body.strip()


def collect_items(site_dir, hidden):
    """All feed-eligible entries as dicts, unsorted."""
    items = []
    for filename, key, label, title_field in FEED_SOURCES:
        if key in hidden:
            continue
        path = Path(site_dir) / "data" / filename
        if not path.exists():
            continue
        for entry in json.loads(path.read_text(encoding="utf-8")):
            day = _parse_day(entry.get("date_added"))
            if not day or not entry.get("id"):
                continue  # no date -> can't place it in a "what's new" feed
            title, description = _item_text(entry, label, title_field)
            link = f"{SITE_URL}#{quote(key, safe='')}/{quote(entry['id'], safe='')}"
            items.append({"day": day, "title": title, "description": description,
                          "link": link, "category": label})
    return items


def build_feed(site_dir, hidden, today, limit=50):
    """Return the RSS 2.0 document as a string."""
    items = collect_items(site_dir, hidden)
    # Newest first; tie-break on link so output is stable run to run
    # (keeps `git diff` on feed.xml quiet when nothing changed).
    items.sort(key=lambda i: (i["day"], i["link"]), reverse=True)
    items = items[:limit]
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "<channel>",
        "<title>TAP — The Accountability Project: new entries</title>",
        f"<link>{SITE_URL}</link>",
        f'<atom:link href="{SITE_URL}feed.xml" rel="self" type="application/rss+xml"/>',
        "<description>Newly added, sourced entries on executive branch actions "
        "since January 2025.</description>",
        "<language>en-us</language>",
        f"<lastBuildDate>{_rfc822(today)}</lastBuildDate>",
    ]
    for i in items:
        out += [
            "<item>",
            f"<title>{escape(i['title'])}</title>",
            f"<link>{escape(i['link'])}</link>",
            f'<guid isPermaLink="true">{escape(i["link"])}</guid>',
            f"<category>{escape(i['category'])}</category>",
            f"<pubDate>{_rfc822(i['day'])}</pubDate>",
            f"<description>{escape(i['description'])}</description>",
            "</item>",
        ]
    out += ["</channel>", "</rss>", ""]
    return "\n".join(out)


def write_feed(site_dir, hidden, today, limit=50, dry_run=False):
    """Write <site>/feed.xml; return the number of items."""
    xml_text = build_feed(site_dir, hidden, today, limit)
    count = xml_text.count("<item>")
    if not dry_run:
        (Path(site_dir) / "feed.xml").write_text(xml_text, encoding="utf-8")
    return count


if __name__ == "__main__":
    import hidden_trackers
    parser = argparse.ArgumentParser(description="Rebuild feed.xml from site data")
    parser.add_argument("--site", default=str(Path(__file__).resolve().parent))
    args = parser.parse_args()
    site = Path(args.site).expanduser()
    n = write_feed(site, hidden_trackers.site_hidden_trackers(site / "index.html"), date.today())
    print(f"wrote feed.xml ({n} items)")
