"""The totals row of RESULTS.md must be the sum of the rows above it.

It was not. β was printed to two decimals, the column summed to $0.34, and $0.34 went into the
README, the CITATION abstract and every retelling — while the measured spend is $0.3482, which is
$0.35, and $0.35 is what the slide and the video submitted to the organizers say. A published
total that disagrees with the deck by a cent is small; a published total that nothing checks is
the reason it survived.

This sums the columns and compares them to the totals row, at the precision the row is printed to.
"""

from __future__ import annotations

import pytest

COLUMNS = {"alpha": 3, "beta": 4, "gamma": 5, "score": 6}


def _rows(repo_root):
    """(cells) for every benchmark row of the scorecard, plus the totals row."""
    benchmarks, totals = [], None
    for line in (repo_root / "RESULTS.md").read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [cell.strip().strip("*") for cell in line.strip().strip("|").split("|")]
        if len(cells) != 8:
            continue
        if cells[0].startswith("`"):
            benchmarks.append(cells)
        elif cells[0] == "total":
            totals = cells
    assert len(benchmarks) == 7, f"expected 7 benchmarks, parsed {len(benchmarks)}"
    assert totals is not None, "no totals row found in RESULTS.md"
    return benchmarks, totals


@pytest.mark.parametrize("column", sorted(COLUMNS))
def test_totals_row_is_the_sum_of_the_column(repo_root, column):
    benchmarks, totals = _rows(repo_root)
    index = COLUMNS[column]
    printed = totals[index]
    decimals = len(printed.partition(".")[2])
    summed = round(sum(float(row[index]) for row in benchmarks), decimals)
    assert f"{summed:.{decimals}f}" == printed, (
        f"the {column} column sums to {summed:.{decimals}f}, the totals row says {printed}"
    )


def test_the_beta_total_is_quoted_the_way_the_submitted_deck_quotes_it(repo_root):
    """$0.3482 rounds to $0.35. The slide and video say $0.35; so must everything else."""
    _, totals = _rows(repo_root)
    assert round(float(totals[COLUMNS["beta"]]), 2) == 0.35
    # RESULTS.md is allowed to name the old figure: it explains the rounding. The places that
    # merely quote a total are not.
    for name in ("README.md", "CITATION.cff"):
        text = (repo_root / name).read_text(encoding="utf-8")
        assert "0.34" not in text.replace("0.3482", ""), f"{name} still quotes the old total"
