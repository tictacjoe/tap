"""Tests for build_legal_pages.py (TERMS.md / LICENSE.md -> HTML)."""
from pathlib import Path

import build_legal_pages as blp

ROOT = Path(__file__).parent


def test_render_page_has_title_and_body():
    html = blp.render_page("# Hi\n\ntext", "Terms of Use")
    assert "<title>Terms of Use — The Accountability Project</title>" in html
    assert "<h1>Hi</h1>" in html
    assert "<p>text</p>" in html
    assert 'href="./"' in html


def test_generated_pages_are_current():
    for md, out, title in blp.PAGES:
        fresh = blp.render_page((ROOT / md).read_text(encoding="utf-8"), title)
        assert (ROOT / out).read_text(encoding="utf-8") == fresh, (
            f"{out} is stale; run python3 build_legal_pages.py"
        )


def test_footer_links_point_at_html():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    assert 'href="terms.html"' in index
    assert 'href="license.html"' in index
    assert 'href="TERMS.md"' not in index
    about = (ROOT / "about.html").read_text(encoding="utf-8")
    assert 'href="terms.html"' in about and 'href="license.html"' in about
    assert 'href="TERMS.md"' not in about and 'href="LICENSE.md"' not in about


def test_render_page_lists_after_text():
    html = blp.render_page("Intro:\n- a\n- b", "T")
    assert "<li>a</li>" in html and "<li>b</li>" in html
    assert "- a" not in html


def test_render_page_numbered_list_after_text():
    assert "<ol>" in blp.render_page("Rules:\n1. x\n2. y", "T")
