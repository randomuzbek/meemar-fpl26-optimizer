"""The submission is a record, and a record whose bytes drift is not a record.

RESULTS.md and docs/reproduce.md publish the md5 of each shipped file and tie them to validation
ID v_e17a8d65e4a8 and the scored archive 3c0bd8d702078d4c2158a0e6c8789868. If anything reformats,
re-encodes or line-ending-smudges these files, every one of those published claims silently
becomes false. This test is what turns that from a silent problem into a failed build.

If this test fails, do not update the expected hash. Restore the file.
"""

from __future__ import annotations

import hashlib

import pytest

EXPECTED_MD5 = {
    "dcp_optimizer.py": "64475899a43e372f4dcf441a254eec9d",
    "SYSTEM_PROMPT.TXT": "4aaf8d8dceaea50c3153b24e0336b802",
    "requirements.txt": "be4dc2a597aef77d292c7d832df87554",
}


@pytest.mark.parametrize(("name", "expected"), sorted(EXPECTED_MD5.items()))
def test_shipped_file_is_byte_identical_to_what_was_scored(repo_root, name, expected):
    path = repo_root / "submission" / name
    assert path.is_file(), f"{name} is missing from submission/"
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    assert digest == expected, (
        f"{name} no longer matches the scored submission.\n"
        f"  expected {expected}\n"
        f"  actual   {digest}\n"
        "Restore the file rather than updating this expectation; the published results in "
        "RESULTS.md refer to the original bytes."
    )


def test_submission_has_no_crlf(repo_root):
    """A CRLF smudge changes every hash above, and shipping one broke four evaluation runs.

    .gitattributes marks submission/ as -text to prevent it; this asserts the outcome.
    """
    for name in EXPECTED_MD5:
        data = (repo_root / "submission" / name).read_bytes()
        assert b"\r\n" not in data, f"{name} contains CRLF line endings"


def test_upstream_attribution_is_intact(repo_root):
    """Apache-2.0 requires the upstream notices to survive. NOTICE asserts they do."""
    head = (repo_root / "submission" / "dcp_optimizer.py").read_text(encoding="utf-8")[:600]
    assert "Advanced Micro Devices" in head
    assert "SPDX-License-Identifier" in head
