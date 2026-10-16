from pathlib import Path

from build_docs import rewrite_report_links


def test_rewrite_report_links_converts_md_to_html():
    text = "See [the guide](./tap-sweep-cabinet-legal-exposure.md) for details."

    result = rewrite_report_links(text)

    assert result == "See [the guide](./tap-sweep-cabinet-legal-exposure.html) for details."


def test_rewrite_report_links_handles_multiple_links_in_one_line():
    text = (
        "See [Ingestion Pipeline](./tap-sweep-reporting-database-updates.md) or "
        "[Backlog Triage](./tap-sweep-reporting-backlog-triage.md)."
    )

    result = rewrite_report_links(text)

    assert "](./tap-sweep-reporting-database-updates.html)" in result
    assert "](./tap-sweep-reporting-backlog-triage.html)" in result


from build_docs import ensure_blank_line_before_lists


def test_ensure_blank_line_before_lists_inserts_missing_blank_line():
    text = "Trackers:\n- Item One\n- Item Two\n"

    result = ensure_blank_line_before_lists(text)

    assert result == "Trackers:\n\n- Item One\n- Item Two\n"


def test_ensure_blank_line_before_lists_leaves_existing_blank_line_untouched():
    text = "Trackers:\n\n- Item One\n- Item Two\n"

    result = ensure_blank_line_before_lists(text)

    assert result == text


def test_ensure_blank_line_before_lists_leaves_consecutive_items_as_is():
    text = "- Item One\n- Item Two\n- Item Three\n"

    result = ensure_blank_line_before_lists(text)

    assert result == text


def test_ensure_blank_line_before_lists_ignores_unspaced_list_inside_fence():
    text = "```\nTrackers:\n- one\n- two\n```\n"

    result = ensure_blank_line_before_lists(text)

    assert result == text


from build_docs import convert_report


def test_convert_report_rewrites_report_links():
    text = "See [the guide](./tap-sweep-cabinet-legal-exposure.md) for details."

    html = convert_report(text)

    assert '<a href="./tap-sweep-cabinet-legal-exposure.html">' in html
    assert ".md" not in html


def test_convert_report_renders_fenced_code_blocks():
    text = "```markdown\nThe sweep begins.\n```\n"

    html = convert_report(text)

    assert "<pre>" in html
    assert "<code" in html


def test_convert_report_renders_list_that_immediately_follows_prose():
    text = "Trackers:\n- Item One\n- Item Two\n"

    html = convert_report(text)

    assert "<ul>" in html
    assert "<li>Item One</li>" in html
    assert " - Item One" not in html


from build_docs import extract_title


def test_extract_title_returns_h1_text():
    text = (
        "# The Accountability Project — Overview\n\n"
        '> "While headlines flood, the record stands."\n\n'
        "## Introduction\n\n"
        "The Accountability Project began in early 2025.\n"
    )

    assert extract_title(text) == "The Accountability Project — Overview"


def test_extract_title_returns_empty_string_when_no_h1():
    text = "## Introduction\n\nNo top-level heading here.\n"

    assert extract_title(text) == ""


import pytest

from build_docs import render_page, render_index, read_homepage_banner


def test_render_page_includes_title_body_and_back_links():
    html = render_page(
        "Cabinet-Level Legal Exposure",
        "<p>Body content here.</p>",
        back_links=[("All Docs", "index.html"), ("Back to The Accountability Project", "../index.html")],
    )

    assert "<title>Cabinet-Level Legal Exposure — The Accountability Project</title>" in html
    assert "<h1>Cabinet-Level Legal Exposure</h1>" in html
    assert "<p>Body content here.</p>" in html
    assert '<a class="back-link" href="index.html">&larr; All Docs</a>' in html
    assert '<a class="back-link" href="../index.html">&larr; Back to The Accountability Project</a>' in html


def test_render_page_banner_comes_from_homepage(tmp_path):
    # The docs masthead's project name and mission line are read from the
    # homepage, so a reword there is the only edit needed (2026-10-16).
    homepage = tmp_path / "index.html"
    homepage.write_text(
        '<header class="masthead">\n  <h1>TAP</h1>\n'
        '  <p class="tagline-name">Test Project Name</p>\n'
        '  <p class="tagline">A test mission line.</p>\n</header>\n',
        encoding="utf-8",
    )
    html_out = render_page("Some Report", "<p>Body.</p>", back_links=[],
                           banner=read_homepage_banner(homepage))

    assert '<p class="tagline-name">Test Project Name</p>' in html_out
    assert '<p class="tagline">A test mission line.</p>' in html_out


def test_read_homepage_banner_fails_loudly_when_missing(tmp_path):
    homepage = tmp_path / "index.html"
    homepage.write_text("<html><body>no banner here</body></html>", encoding="utf-8")

    with pytest.raises(ValueError):
        read_homepage_banner(homepage)


def test_render_page_real_homepage_banner_is_used_by_default():
    # No banner argument: falls back to the real tap-site homepage.
    name, mission = read_homepage_banner()
    html_out = render_page("Some Report", "<p>Body.</p>", back_links=[])

    assert f'<p class="tagline-name">{name}</p>' in html_out
    assert f'<p class="tagline">{mission}</p>' in html_out


def test_render_page_wraps_tables_in_scroll_container():
    # Wide tables scroll inside their own box on a phone instead of
    # pushing the whole page sideways.
    html_out = render_page("T", "<table>\n<tr><td>x</td></tr>\n</table>", back_links=[])

    assert '<div class="table-scroll"><table>' in html_out
    assert "</table></div>" in html_out


def test_render_page_escapes_ampersand_in_title():
    html_out = render_page(
        "Footnotes & References Guide",
        "<p>Body content here.</p>",
        back_links=[],
    )

    assert "Footnotes &amp; References Guide" in html_out
    assert "Footnotes & References Guide" not in html_out


def test_render_index_escapes_ampersand_in_title():
    reports = [
        {"slug": "tap-footnotes-and-references-guide", "title": "Footnotes & References Guide"},
    ]

    html_out = render_index(reports)

    assert "Footnotes &amp; References Guide" in html_out
    assert "Footnotes & References Guide" not in html_out


def test_render_index_lists_reports_with_overview_first():
    reports = [
        {"slug": "tap-sweep-corporate-deregulation", "title": "Corporate Deregulation"},
        {"slug": "tap-project-overview", "title": "Overview"},
        {"slug": "tap-sweep-cabinet-legal-exposure", "title": "Cabinet-Level Legal Exposure"},
    ]

    html = render_index(reports)

    overview_pos = html.index("tap-project-overview.html")
    cabinet_pos = html.index("tap-sweep-cabinet-legal-exposure.html")
    dereg_pos = html.index("tap-sweep-corporate-deregulation.html")
    assert overview_pos < cabinet_pos < dereg_pos
    # Link-only index -- no narrative/summary text follows each entry.
    assert "<p>" not in html


from build_docs import build_docs


def test_build_docs_writes_one_html_file_per_report_and_an_index(tmp_path):
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    (reports_dir / "tap-project-overview.md").write_text(
        "# The Accountability Project — Overview\n\n"
        "## Introduction\n\n"
        "The Accountability Project began in early 2025.\n"
    )
    (reports_dir / "tap-sweep-cabinet-legal-exposure.md").write_text(
        "# The Accountability Project — Cabinet-Level Legal Exposure "
        "Update Sweeps\n\n"
        "## Concept & Purpose\n"
        "A Cabinet-Level Legal Exposure Update Sweep tracks statutory "
        "liability.\n"
    )

    build_docs(working, site)

    overview_html = (site / "docs" / "tap-project-overview.html").read_text()
    assert "<h1>The Accountability Project — Overview</h1>" in overview_html
    assert "The Accountability Project began in early 2025." in overview_html

    cabinet_html = (site / "docs" / "tap-sweep-cabinet-legal-exposure.html").read_text()
    assert "Cabinet-Level Legal Exposure Update Sweeps" in cabinet_html

    index_html = (site / "docs" / "index.html").read_text()
    assert "tap-project-overview.html" in index_html
    assert "tap-sweep-cabinet-legal-exposure.html" in index_html


def test_build_docs_does_not_duplicate_title_as_second_h1(tmp_path):
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    (reports_dir / "tap-project-overview.md").write_text(
        "# The Accountability Project — Overview\n\n"
        "## Introduction\n\n"
        "The Accountability Project began in early 2025.\n"
    )

    build_docs(working, site)

    overview_html = (site / "docs" / "tap-project-overview.html").read_text()
    # The masthead's <h1>{title}</h1> (from render_page) must still be
    # present exactly once -- the body must NOT re-render the source's
    # leading "# Title" line as a second <h1>.
    assert overview_html.count("<h1>The Accountability Project — Overview</h1>") == 1
    assert overview_html.count("<h1") == 1
    # The rest of the body must still render normally.
    assert "<h2" in overview_html
    assert "The Accountability Project began in early 2025." in overview_html


def test_build_docs_does_not_duplicate_title_when_h1_follows_generated_header_comment(tmp_path):
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    # Matches generate_webdocs.py's real output shape: an HTML comment
    # (AUTO_GENERATED_HEADER) and a blank line precede the report's own
    # "# Title" line, rather than the H1 being the very first line.
    (reports_dir / "tap-sweep-corporate-deregulation.md").write_text(
        "<!-- AUTO-GENERATED from docs/reports/tech-reports/"
        "tap-sweep-corporate-deregulation.md -- edit that file and rerun "
        "generate_webdocs.py, do not edit this file directly -->\n\n"
        "# Corporate Deregulation\n\n"
        "## About This Tracker\n\n"
        "Tracks federal agency rule rollbacks.\n"
    )

    build_docs(working, site)

    report_html = (site / "docs" / "tap-sweep-corporate-deregulation.html").read_text()
    assert report_html.count("<h1") == 1
    assert report_html.count("<h1>Corporate Deregulation</h1>") == 1
    assert "<h2" in report_html
    assert "Tracks federal agency rule rollbacks." in report_html


def test_build_docs_ignores_nested_subfolder(tmp_path):
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    nested_dir = reports_dir / "drafts"
    nested_dir.mkdir(parents=True)

    (reports_dir / "tap-project-overview.md").write_text(
        "# Overview\n\nReal content.\n"
    )
    (nested_dir / "tap-project-overview-v1.md").write_text(
        "# Old Draft\n\nSuperseded content.\n"
    )

    build_docs(working, site)

    assert (site / "docs" / "tap-project-overview.html").exists()
    assert not (site / "docs" / "tap-project-overview-v1.html").exists()


def test_build_docs_ignores_files_outside_webdocs_subfolder(tmp_path):
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports"
    webdocs_dir = reports_dir / "webdocs"
    webdocs_dir.mkdir(parents=True)

    (webdocs_dir / "tap-project-overview.md").write_text(
        "# Overview\n\nReal content.\n"
    )
    # A file sitting directly in docs/reports/ (not in webdocs/) should be
    # ignored entirely -- only webdocs/*.md is the source scope now.
    (reports_dir / "tap-docs-audit-and-publishing-report.md").write_text(
        "# Internal Audit and Publishing Report\n\n"
        "## Engineering Session\nPrivate project-management narrative.\n"
    )

    build_docs(working, site)

    assert (site / "docs" / "tap-project-overview.html").exists()
    assert not (site / "docs" / "tap-docs-audit-and-publishing-report.html").exists()
    index_html = (site / "docs" / "index.html").read_text()
    assert "tap-docs-audit-and-publishing-report" not in index_html


def test_build_docs_skips_unreadable_file_and_continues(tmp_path, capsys):
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    (reports_dir / "tap-project-overview.md").write_text(
        "# Overview\n\nGood content that should still convert.\n"
    )
    # Invalid UTF-8 bytes -- read_text(encoding="utf-8") will raise.
    (reports_dir / "tap-sweep-broken.md").write_bytes(b"\xff\xfe not valid utf-8")

    build_docs(working, site)

    captured = capsys.readouterr()
    assert "WARNING" in captured.out
    assert "tap-sweep-broken.md" in captured.out
    assert (site / "docs" / "tap-project-overview.html").exists()
    assert not (site / "docs" / "tap-sweep-broken.html").exists()


def test_build_docs_prunes_stale_html_when_source_md_removed(tmp_path):
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    (reports_dir / "tap-project-overview.md").write_text(
        "# Overview\n\nReal content.\n"
    )
    removed_md = reports_dir / "tap-sweep-old-report.md"
    removed_md.write_text(
        "# Old Report\n\nContent that will be deleted.\n"
    )

    build_docs(working, site)

    overview_output = site / "docs" / "tap-project-overview.html"
    removed_output = site / "docs" / "tap-sweep-old-report.html"
    assert overview_output.exists()
    assert removed_output.exists()

    # Simulate Joe deleting the report's .md source.
    removed_md.unlink()

    build_docs(working, site)

    assert not removed_output.exists()
    assert overview_output.exists()
    assert "Real content." in overview_output.read_text()

    index_html = (site / "docs" / "index.html").read_text()
    assert "tap-project-overview.html" in index_html
    assert "tap-sweep-old-report" not in index_html


def test_build_docs_does_not_prune_hand_authored_md_files(tmp_path):
    """site/docs/ can also hold hand-authored .md reference files
    (e.g. tap-about.md) alongside the generated .html pages -- the
    prune logic only ever globs and deletes *.html, never *.md."""
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    (reports_dir / "tap-project-overview.md").write_text(
        "# Overview\n\nReal content.\n"
    )

    output_dir = site / "docs"
    output_dir.mkdir(parents=True)
    hand_authored = output_dir / "tap-about.md"
    hand_authored.write_text("# About\n\nHand-authored reference content.\n")

    build_docs(working, site)

    assert hand_authored.exists()
    assert hand_authored.read_text() == "# About\n\nHand-authored reference content.\n"
    assert (site / "docs" / "tap-project-overview.html").exists()


def test_build_docs_index_is_link_only_no_narrative(tmp_path):
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    (reports_dir / "tap-project-overview.md").write_text(
        "# Overview\n\n"
        "This paragraph should never appear on the index page.\n"
    )

    build_docs(working, site)

    index_html = (site / "docs" / "index.html").read_text()
    assert 'href="tap-project-overview.html"' in index_html
    assert "This paragraph should never appear on the index page." not in index_html
    # No <p> at all inside the report-index list items -- links only.
    assert "<p>" not in index_html


def test_build_docs_warns_when_stale_output_survives_read_failure(tmp_path, capsys):
    """When a .md file fails to read, but a previous .html exists for it,
    the "was NOT pruned" warning should be printed."""
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    # Create a good report so build_docs can generate at least one output
    (reports_dir / "tap-project-overview.md").write_text(
        "# Overview\n\nGood content.\n"
    )
    # Create the broken report
    broken_md = reports_dir / "tap-sweep-broken.md"
    broken_md.write_bytes(b"\xff\xfe not valid utf-8")

    # First build: creates tap-project-overview.html, skips tap-sweep-broken.md (no html created for it)
    build_docs(working, site)
    assert (site / "docs" / "tap-project-overview.html").exists()
    assert not (site / "docs" / "tap-sweep-broken.html").exists()

    # Second run: Simulate the first run having succeeded in creating an html for tap-sweep-broken,
    # then this run the .md file becomes unreadable. We create the stale html manually.
    stale_broken_output = site / "docs" / "tap-sweep-broken.html"
    stale_broken_output.write_text("<html><body>Stale broken content</body></html>")

    # Now run build_docs again with the broken .md file
    capsys.readouterr()  # Clear previous output
    build_docs(working, site)
    captured = capsys.readouterr()

    # Both warnings should appear
    assert "WARNING: skipping tap-sweep-broken.md" in captured.out
    assert "was NOT pruned (previous output kept)" in captured.out
    assert "tap-sweep-broken.html" in captured.out
    # The stale file should still exist (not pruned)
    assert stale_broken_output.exists()


def test_build_docs_no_warning_when_no_stale_output_exists(tmp_path, capsys):
    """When a .md file fails to read, but NO previous .html exists for it,
    the "was NOT pruned" warning should NOT be printed."""
    working = tmp_path / "tap-data"
    site = tmp_path / "tap-site"
    reports_dir = working / "docs" / "reports" / "webdocs"
    reports_dir.mkdir(parents=True)

    # Create a good report so we have at least one output
    (reports_dir / "tap-project-overview.md").write_text(
        "# Overview\n\nGood content.\n"
    )
    # Create a broken report that has never been successfully built before
    (reports_dir / "tap-sweep-never-built.md").write_bytes(b"\xff\xfe not valid utf-8")

    capsys.readouterr()  # Clear previous output
    build_docs(working, site)
    captured = capsys.readouterr()

    # The skip warning should appear
    assert "WARNING: skipping tap-sweep-never-built.md" in captured.out
    # But the "was NOT pruned" warning should NOT appear (no prior .html to warn about)
    assert "was NOT pruned" not in captured.out
    # The stale file should not exist (it was never created)
    assert not (site / "docs" / "tap-sweep-never-built.html").exists()
