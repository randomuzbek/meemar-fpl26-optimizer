"""`submission/upstream.patch` is the boundary between AMD's work and this project's.

`docs/reproduce.md` tells a reader what that patch contains — how many lines it adds, how many it
removes, and which files it touches — and invites them to check. The first published version of
those counts came from an earlier patch and was wrong by a hundred lines in each direction, which
is the worst kind of error in a document whose entire purpose is verifiability.

So the numbers are no longer typed into prose independently of the file: this test reads them back
out of the document and measures the patch itself. Changing either one alone fails the build.
"""

from __future__ import annotations

import re

PATCH = "submission/upstream.patch"
TOUCHED = {"dcp_optimizer.py", "requirements.txt"}


def _patch_lines(repo_root):
    return (repo_root / PATCH).read_text(encoding="utf-8").splitlines()


def _counts(lines):
    """Added and removed content lines, excluding the `+++`/`---` file headers."""
    added = sum(1 for line in lines if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in lines if line.startswith("-") and not line.startswith("---"))
    return added, removed


def _claimed(repo_root):
    """The three numbers docs/reproduce.md prints, read back out of the prose it prints them in.

    The document groups digits with a narrow no-break space ("2 873"), so the digits are pulled
    out of each captured group rather than matched exactly.
    """
    text = (repo_root / "docs" / "reproduce.md").read_text(encoding="utf-8")
    claim = re.search(
        r"The patch is (\d[\d\s]*?) lines .*?"
        r"contribution: (\d[\d\s]*?) lines added, (\d[\d\s]*?) removed, "
        r"across two files",
        text,
        re.S,
    )
    assert claim, "docs/reproduce.md no longer states the patch size in the expected wording"
    return tuple(int(re.sub(r"\D", "", group)) for group in claim.groups())


def test_patch_matches_what_the_docs_claim(repo_root):
    lines = _patch_lines(repo_root)
    claimed_total, claimed_added, claimed_removed = _claimed(repo_root)
    added, removed = _counts(lines)

    assert len(lines) == claimed_total, f"patch is {len(lines)} lines, docs say {claimed_total}"
    assert added == claimed_added, f"patch adds {added} lines, docs say {claimed_added}"
    assert removed == claimed_removed, f"patch removes {removed} lines, docs say {claimed_removed}"


def test_patch_touches_exactly_the_two_modified_files(repo_root):
    """NOTICE says SYSTEM_PROMPT.TXT is upstream's, unmodified. The patch is where that shows."""
    headers = [line for line in _patch_lines(repo_root) if line.startswith("diff --git ")]
    files = {header.split(" b/")[-1] for header in headers}
    assert files == TOUCHED, f"upstream.patch touches {sorted(files)}, expected {sorted(TOUCHED)}"
