#!/usr/bin/env python3
"""Render TERMS.md and LICENSE.md into styled terms.html / license.html.

Styling is borrowed from about.html's <style> block at build time so the
legal pages match the site. Output is deterministic (no timestamps).
Run from anywhere: python3 build_legal_pages.py
"""
import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).parent
# (source markdown, output html, page title)
PAGES = [
    ("TERMS.md", "terms.html", "Terms of Use"),
    ("LICENSE.md", "license.html", "License"),
]


def _about_style():
    """Return the <style>...</style> block from about.html."""
    about = (ROOT / "about.html").read_text(encoding="utf-8")
    m = re.search(r"<style>.*?</style>", about, re.S)
    if m is None:
        raise RuntimeError("no <style> block found in about.html")
    return m.group(0)


_LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")


def _space_lists(md_text):
    """Insert a blank line before a list that directly follows a text line.

    Python-Markdown needs that blank line; the source .md files omit it.
    """
    out = []
    prev = ""
    for line in md_text.split("\n"):
        if _LIST_ITEM.match(line) and prev.strip() and not _LIST_ITEM.match(prev):
            out.append("")
        out.append(line)
        prev = line
    return "\n".join(out)


def render_page(md_text, title):
    body = markdown.markdown(
        _space_lists(md_text), extensions=["tables", "sane_lists", "nl2br"]
    )
    t = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{t} — The Accountability Project</title>
{_about_style()}
</head>
<body>

<main>
  <p><a class="back-link" href="./">&larr; Back to TAP</a></p>

{body}
</main>

</body>
</html>
"""


def main():
    for md, out, title in PAGES:
        text = (ROOT / md).read_text(encoding="utf-8")
        (ROOT / out).write_text(render_page(text, title), encoding="utf-8")
        print(f"wrote {out}")


if __name__ == "__main__":
    main()
