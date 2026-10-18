"""about.html's tracker counts must match its tracker table (TFS Phase B
cutover review, 2026-10-17: the page still counted Trump Family as hidden)."""
import re
from pathlib import Path

ABOUT = (Path(__file__).parent / "about.html").read_text(encoding="utf-8")
WORDS = {"three": 3, "four": 4, "five": 5, "six": 6, "seven": 7}


def _table_rows():
    return re.findall(r"<tr><td>([^<]+)</td>", ABOUT)


def test_total_tracker_count_matches_table():
    m = re.search(r"<p>(\w+) trackers, organized by kind of action", ABOUT)
    assert WORDS[m.group(1).lower()] == len(_table_rows())


def test_curated_tracker_count_matches_table():
    # Every row except Reporting is a curated tracker.
    curated = len([r for r in _table_rows() if r != "Reporting"])
    counts = re.findall(r"\b(" + "|".join(WORDS) + r")\s+curated\s+trackers", ABOUT, re.I)
    assert counts, "no 'N curated trackers' phrase found"
    for word in counts:
        assert WORDS[word.lower()] == curated, word
