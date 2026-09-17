#!/usr/bin/env python3
"""
build_docs.py

Converts the Markdown reports in the PRIVATE working repo's
docs/reports/webdocs/ (~/gjoe/tap-data/docs/reports/webdocs/*.md,
non-recursive) into styled public HTML pages in the PUBLIC site repo
(~/gjoe/tap-site/docs/).

This does NOT commit or push anything -- it only writes files into the
site repo's working directory. You review with `git diff` in the site
repo and commit/push yourself, same discipline as publish.py.

The .md source files are only ever read, never modified.

Usage:
  python3 build_docs.py
  python3 build_docs.py --working ~/gjoe/tap-data --site ~/gjoe/tap-site
"""

import argparse
import html
import re
import sys
from pathlib import Path

try:
    import markdown
except ImportError:
    print("ERROR: the 'markdown' package is required.")
    print("Install it with: pip install --break-system-packages markdown")
    sys.exit(1)


_MD_LINK_RE = re.compile(r"\]\(([^)]+?)\.md\)")


def rewrite_report_links(text: str) -> str:
    """Rewrite links to other reports (`](some-report.md)`) to point at
    the generated HTML file instead (`](some-report.html)`)."""
    return _MD_LINK_RE.sub(r"](\1.html)", text)


_LIST_ITEM_RE = re.compile(r'^\s*(?:[-*+]|\d+\.)\s')
_FENCE_RE = re.compile(r'^\s*```')


def ensure_blank_line_before_lists(text: str) -> str:
    """Insert a blank line before a Markdown list's first item when it
    immediately follows non-blank, non-list text with no separating blank
    line -- CommonMark (and python-markdown) requires that blank line to
    recognize the list at all; without it, the whole block renders as one
    <p> with literal list-marker characters.

    Fenced code blocks (```` ``` ````, plain or language-tagged like
    ```` ```python ````) are passed through untouched -- list-shaped lines
    inside a code sample (e.g. markdown-syntax examples) must not be
    rewritten."""
    lines = text.split("\n")
    result = []
    prev_is_list_or_blank = True
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            result.append(line)
            prev_is_list_or_blank = False
            continue
        if in_fence:
            result.append(line)
            continue
        is_list = bool(_LIST_ITEM_RE.match(line))
        if is_list and not prev_is_list_or_blank:
            result.append("")
        result.append(line)
        prev_is_list_or_blank = is_list or line.strip() == ""
    return "\n".join(result)


def convert_report(markdown_text: str) -> str:
    """Apply the text transforms, then convert Markdown to an HTML
    fragment."""
    text = rewrite_report_links(markdown_text)
    text = ensure_blank_line_before_lists(text)
    return markdown.markdown(text, extensions=["fenced_code", "tables"])


def extract_title(markdown_text: str) -> str:
    """Pull the H1 title out of a report's raw Markdown, for the index
    page listing."""
    for line in markdown_text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def strip_leading_h1(markdown_text: str) -> str:
    """Remove the report's own top-level "# Title" line so the body
    doesn't re-emit it as a second <h1> below the masthead's -- the
    masthead (render_page) already shows the title once.

    Skips past any leading blank lines and single-line HTML comments
    first (generate_webdocs.py prepends an AUTO_GENERATED_HEADER comment
    before the real H1), so the H1 line is found and removed regardless
    of what precedes it. Only removes a genuine top-level heading ("# "
    exactly, never "## " or deeper) and only that one line -- everything
    else, including the leading blanks/comment, is left untouched. If no
    such line appears before real content starts, the text is returned
    unchanged."""
    lines = markdown_text.splitlines(keepends=True)
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped == "" or (stripped.startswith("<!--") and stripped.endswith("-->")):
            continue
        if line.startswith("# "):
            return "".join(lines[:i] + lines[i + 1:])
        break
    return markdown_text


# CSS lifted from about.html's <style> block, plus additions for
# elements about.html doesn't use: h3, blockquote, pre/code, hr, and
# the report-index listing.
_TEMPLATE_CSS = """
  :root {
    --paper: #EDEFE7;
    --paper-card: #F7F8F2;
    --ink: #1D2220;
    --ink-soft: #52564F;
    --ink-faint: #8A8D82;
    --rule: #C7CABB;
    --rule-strong: #A9AC9A;
    --brass: #96762C;
    --brass-light: #EFE7D2;
  }

  * { box-sizing: border-box; }

  body {
    margin: 0;
    background: var(--paper);
    color: var(--ink);
    font-family: Georgia, 'Iowan Old Style', 'Times New Roman', serif;
    line-height: 1.6;
  }

  header.masthead {
    max-width: 880px;
    margin: 0 auto;
    padding: 3rem 1.5rem 1.5rem;
    text-align: center;
    border-bottom: 3px double var(--rule-strong);
  }
  header.masthead h1 {
    margin: 0;
    font-size: 2.2rem;
    letter-spacing: 0.03em;
    font-weight: 400;
  }
  header.masthead .tagline {
    margin: 0.6rem 0 0;
    font-size: 0.85rem;
    letter-spacing: 0.03em;
    color: var(--brass);
    font-style: italic;
  }

  main {
    max-width: 700px;
    margin: 0 auto;
    padding: 2rem 1.5rem 4rem;
  }

  main h2 {
    font-size: 1.3rem;
    font-weight: 400;
    letter-spacing: 0.02em;
    border-bottom: 1px solid var(--rule);
    padding-bottom: 0.4rem;
    margin-top: 2.5rem;
  }
  main h3 {
    font-size: 1.05rem;
    font-weight: 600;
    color: var(--brass);
    margin-top: 2rem;
  }

  main p { color: var(--ink-soft); }
  main strong { color: var(--ink); }
  main a { color: var(--brass); }

  main blockquote {
    margin: 1.5rem 0;
    padding: 0.8rem 1.2rem;
    border-left: 3px solid var(--brass);
    background: var(--paper-card);
    font-style: italic;
    color: var(--ink-soft);
  }

  main pre {
    background: var(--paper-card);
    border: 1px solid var(--rule);
    padding: 1rem;
    overflow-x: auto;
    font-size: 0.85rem;
  }
  main code {
    font-family: ui-monospace, monospace;
    background: var(--paper-card);
    padding: 0.1rem 0.3rem;
    font-size: 0.9em;
  }
  main pre code {
    background: none;
    padding: 0;
  }

  main hr {
    border: none;
    border-top: 1px solid var(--rule);
    margin: 2.5rem 0;
  }

  main table {
    width: 100%;
    border-collapse: collapse;
    margin: 1.2rem 0;
    font-size: 0.95rem;
  }
  main th, main td {
    text-align: left;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid var(--rule);
    vertical-align: top;
  }
  main th {
    color: var(--ink);
    font-weight: 600;
    border-bottom: 2px solid var(--rule-strong);
  }
  main td { color: var(--ink-soft); }

  .report-index { list-style: none; padding: 0; }
  .report-index li {
    margin-bottom: 1.5rem;
    padding-bottom: 1.5rem;
    border-bottom: 1px solid var(--rule);
  }
  .report-index li a {
    font-size: 1.1rem;
    color: var(--ink);
    text-decoration: none;
    font-weight: 600;
  }
  .report-index li a:hover { color: var(--brass); }

  .back-link {
    display: inline-block;
    margin-top: 2rem;
    margin-right: 1.5rem;
    font-family: ui-monospace, monospace;
    font-size: 0.78rem;
    letter-spacing: 0.03em;
    text-transform: uppercase;
    color: var(--brass);
    text-decoration: none;
  }
  .back-link:hover { text-decoration: underline; }
"""

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title} — The Accountability Project</title>
<style>{css}</style>
</head>
<body>
<header class="masthead">
<h1>{title}</h1>
<p class="tagline">TAP — Docs</p>
</header>
<main>
{body}
{back_links}
</main>
<script data-goatcounter="https://tap-site.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
</body>
</html>
"""


def render_page(title: str, body_html: str, back_links: list) -> str:
    """`back_links` is a list of (label, href) tuples, rendered in order
    as `.back-link` anchors after the body."""
    links_html = "\n".join(
        f'<a class="back-link" href="{href}">&larr; {label}</a>'
        for label, href in back_links
    )
    # title comes from the report's raw Markdown H1 and is interpolated
    # raw into HTML below (<title>, <h1>) -- escape it. body_html already
    # comes from markdown.markdown(), which handles its own escaping.
    return _PAGE_TEMPLATE.format(title=html.escape(title), css=_TEMPLATE_CSS, body=body_html, back_links=links_html)


def render_index(reports: list) -> str:
    """`reports` is a list of {"slug", "title"} dicts. tap-project-overview
    always sorts first; the rest alphabetically by title."""
    def sort_key(report):
        if report["slug"] == "tap-project-overview":
            return (0, "")
        return (1, report["title"])

    ordered = sorted(reports, key=sort_key)
    items = "\n".join(
        # r["title"] is raw text from the report's Markdown H1 -- escape it.
        f'<li><a href="{r["slug"]}.html">{html.escape(r["title"])}</a></li>'
        for r in ordered
    )
    body = f'<ul class="report-index">\n{items}\n</ul>'
    return render_page("Docs", body, back_links=[("Back to TAP", "../index.html")])


# Reserved for any future webdocs/ file that shouldn't be published (e.g.
# a draft accidentally left out of docs/reports/drafts/) -- empty for now,
# since docs/reports/webdocs/ only ever holds files meant to go public.
_EXCLUDED_REPORTS = set()


def build_docs(working: Path, site: Path) -> None:
    """Convert every *.md file directly in working/docs/reports/webdocs/
    (Path.glob("*.md") only matches direct children, so any nested
    subfolder is skipped automatically; also never _EXCLUDED_REPORTS)
    into a styled HTML page under site/docs/, plus an index page listing
    all of them."""
    reports_dir = working / "docs" / "reports" / "webdocs"
    output_dir = site / "docs"
    output_dir.mkdir(parents=True, exist_ok=True)

    md_files = [
        md_file for md_file in sorted(reports_dir.glob("*.md"))
        if md_file.name not in _EXCLUDED_REPORTS
    ]

    # site/docs/ is a fully generated directory for these report pages --
    # so prune any existing *.html file that won't be (re)written this run
    # (e.g. its .md source was deleted). Compute the full set of expected
    # outputs first (every slug about to be generated, plus the
    # always-rewritten index.html) so a report that's merely being
    # regenerated is never mistaken for stale. Hand-authored .md reference
    # files that also live in site/docs/ (tap-about.md, etc.) are untouched
    # -- this only ever globs and deletes *.html.
    expected_names = {f"{md_file.stem}.html" for md_file in md_files}
    expected_names.add("index.html")
    for existing in sorted(output_dir.glob("*.html")):
        if existing.name not in expected_names:
            existing.unlink()
            print(f"  pruned stale: docs/{existing.name}")

    reports = []
    for md_file in md_files:
        try:
            raw = md_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"  WARNING: skipping {md_file.name}: {exc}")
            stale_output = output_dir / f"{md_file.stem}.html"
            if stale_output.exists():
                print(f"  WARNING: docs/{stale_output.name} was NOT pruned (previous output kept)")
            continue

        title = extract_title(raw)
        body_text = strip_leading_h1(raw)
        body_html = convert_report(body_text)
        page_html = render_page(title, body_html, back_links=[
            ("All Docs", "index.html"),
            ("Back to TAP", "../index.html"),
        ])

        slug = md_file.stem
        (output_dir / f"{slug}.html").write_text(page_html, encoding="utf-8")
        reports.append({"slug": slug, "title": title})
        print(f"  converted: {md_file.name} -> docs/{slug}.html")

    index_html = render_index(reports)
    (output_dir / "index.html").write_text(index_html, encoding="utf-8")
    print(f"  wrote docs/index.html ({len(reports)} report(s))")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--working", default=str(Path.home() / "gjoe/tap-data"),
                         help="Path to the private working repo")
    parser.add_argument("--site", default=str(Path.home() / "gjoe/tap-site"),
                         help="Path to the public site repo")
    args = parser.parse_args()

    working = Path(args.working)
    site = Path(args.site)

    if not working.exists():
        print(f"ERROR: working repo not found at {working}")
        sys.exit(1)
    if not site.exists():
        print(f"ERROR: site repo not found at {site}")
        sys.exit(1)

    print("=== reports ===")
    build_docs(working, site)
    print()
    print("---")
    print("Done. Now review and commit in the site repo:")
    print(f"  cd {site}")
    print(f"  git diff docs/")
    print(f"  git add docs/")
    print(f"  git commit -m \"docs: publish updated reports\"")
    print(f"  git push")


if __name__ == "__main__":
    main()
