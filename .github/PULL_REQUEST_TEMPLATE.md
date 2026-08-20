<!--
Before opening: submission/ is frozen. Pull requests that change it will be declined,
including ones that fix real bugs. See CONTRIBUTING.md for why.
-->

## What this changes

<!-- One or two sentences. The diff already says what; say why. -->

## Why

<!-- What was wrong, or what this makes possible. -->

## If this is justified by a measurement

<!-- Delete this section if it does not apply. Otherwise, per docs/measurement-notes.md: -->

- How it was measured:
- What the control was:
- Which confounder you ruled out, and how (page cache? arm order? machine speed?):

## Checklist

- [ ] `pytest -q` passes
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `scripts/scrub_check.sh` passes
- [ ] Nothing under `submission/` is modified
- [ ] Documentation updated if this changes behaviour a reader would rely on
