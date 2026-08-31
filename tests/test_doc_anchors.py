"""Every line number printed in the docs must point at the function it names.

`docs/architecture.md` walks the reader through the submission by name and line —
```_autosave_best` (1047)`` — which is only useful while the numbers are true. They were
written once against a working copy of `dcp_optimizer.py` that had moved on from the frozen one,
and every one of them was wrong by 50-100 lines: the names were right, so nothing looked broken,
and a reader following them landed inside a different function with no way to tell.

Prose rots quietly. This test makes it fail loudly instead. It resolves each anchor against
`submission/dcp_optimizer.py`, which is frozen, so the numbers can only break if the docs change.
"""

from __future__ import annotations

import re

import pytest

ANCHOR = re.compile(r"`([A-Za-z_][A-Za-z0-9_]*)` \((\d+)\)")
DEFINITION = re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+([A-Za-z_][A-Za-z0-9_]*)\s*[(:]")

DOCS = (
    "README.md",
    "RESULTS.md",
    "docs/architecture.md",
    "docs/measurement-notes.md",
    "docs/reproduce.md",
    "docs/scoring-model.md",
)


def _definitions(repo_root):
    """First definition line of every function and class in the frozen submission."""
    found: dict[str, int] = {}
    text = (repo_root / "submission" / "dcp_optimizer.py").read_text(encoding="utf-8")
    for number, line in enumerate(text.splitlines(), start=1):
        match = DEFINITION.match(line)
        if match:
            found.setdefault(match.group(1), number)
    return found


def _anchors(repo_root):
    for doc in DOCS:
        path = repo_root / doc
        if not path.is_file():
            continue
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for name, claimed in ANCHOR.findall(line):
                yield doc, number, name, int(claimed)


def test_documentation_anchors_resolve(repo_root):
    definitions = _definitions(repo_root)
    anchors = list(_anchors(repo_root))
    assert anchors, "no `name` (line) anchors found — has the pattern in the docs changed?"

    wrong = []
    for doc, doc_line, name, claimed in anchors:
        actual = definitions.get(name)
        if actual is None:
            wrong.append(f"{doc}:{doc_line}: {name} is not defined in the frozen submission")
        elif actual != claimed:
            wrong.append(f"{doc}:{doc_line}: {name} is at line {actual}, the docs say {claimed}")

    assert not wrong, "documentation points at the wrong lines:\n  " + "\n  ".join(wrong)


@pytest.mark.parametrize(
    "name", ["parse_timing_summary_static", "parse_route_status_static", "calculate_fmax"]
)
def test_parsers_the_tests_rely_on_still_exist(repo_root, name):
    """The Vivado-free test suite is only possible because these are pure and module-level."""
    assert name in _definitions(repo_root)
