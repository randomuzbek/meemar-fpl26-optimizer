"""The figures in the README are drawn from RESULTS.md, and this is what keeps them that way.

A picture with numbers baked into it is a second copy of the data that no test reads. Change the
scorecard, forget the figure, and the README shows last month's result with no warning anywhere.
`tools/build_figures.py` derives the SVGs from the table; this regenerates them and compares.

If it fails: run `python3 tools/build_figures.py` and commit the result.
"""

from __future__ import annotations

import subprocess
import sys


def test_committed_figures_match_the_scorecard(repo_root):
    result = subprocess.run(
        [sys.executable, "tools/build_figures.py", "--check"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_figure_reads_the_published_totals(repo_root):
    """The caption states the totals; they must be the ones RESULTS.md publishes."""
    svg = (repo_root / "docs" / "img" / "scorecard-light.svg").read_text(encoding="utf-8")
    assert "318.254 points from 332.784 MHz" in svg
    assert "14.53 points" in svg
