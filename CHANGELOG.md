# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] — 2026-08-31

Documentation corrections. `submission/` is untouched: every hash in RESULTS.md and
docs/reproduce.md is the same as it was, and the artifact this repository exists to publish has
not moved.

### Fixed

- **Every line number in `docs/architecture.md` was wrong.** They were taken from a later working
  copy of `dcp_optimizer.py`, not from the frozen submission, and were off by 50-105 lines. The
  names were right, so a reader following one landed in a different function with nothing to warn
  them. All 24 recomputed against the shipped file.
- **`docs/architecture.md` documented `_polish_state_fp`, which is not in the submission.** It was
  added to the optimizer after the freeze. The row is removed rather than the function published:
  what ships here is what was scored.
- **`docs/reproduce.md` mis-stated the size of `upstream.patch`** as 2 696 lines added and 105
  removed. `git apply --stat` reports 2 579 and 93.
- **`NOTICE` described `SYSTEM_PROMPT.TXT` as modified from upstream.** It is byte-identical to
  AMD's file at `a81aad5` — no part of it is this project's work — and it is therefore absent from
  `upstream.patch`. Corrected, because attribution that overstates authorship is the wrong error to
  make in a NOTICE file.
- **`README.md` reproduction steps skipped `git submodule update` after `git checkout a81aad5`**,
  which leaves the harness submodules on the wrong commits.

### Added

- `tests/test_doc_anchors.py` — resolves every `` `name` (line) `` anchor in the documentation
  against the frozen submission, so a stale line number fails CI instead of misleading a reader.
- `tests/test_upstream_patch.py` — reads the patch statistics back out of `docs/reproduce.md` and
  measures the patch. The prose and the file can no longer drift apart silently.
- CI, OpenSSF Scorecard, view-count and star badges in the README.

### Changed

- GitHub Actions are pinned by commit SHA with the version in a trailing comment. A tag is
  mutable; a SHA is not, and Dependabot updates both together.

## [1.0.0] — 2026-08-20

First public release: the FPL'26 FPGA Design Optimization Contest submission as it was scored,
plus the documentation and tooling needed to verify and rebuild it.

### Added

- `submission/` — the scored artifact, byte-exact. `dcp_optimizer.py`
  (md5 `64475899a43e372f4dcf441a254eec9d`), `SYSTEM_PROMPT.TXT`, `requirements.txt`, and
  `upstream.patch` giving the complete diff against AMD upstream `a81aad5`.
- `RESULTS.md` — the organizers' official per-benchmark scorecard: 318.254 total, 7/7 legal,
  zero disqualifications, validation ID `v_e17a8d65e4a8`.
- `docs/architecture.md` — the four layers of the optimizer, mapped to function names.
- `docs/scoring-model.md` — why a dollar costs what an hour costs, why a second is worth most on
  fast high-α designs, and why the 3600-second γ cap is a cliff rather than a slope.
- `docs/measurement-notes.md` — the 300-second MCP timeout recorded as a success, page-cache and
  machine-speed confounders, and measuring in the shipped configuration.
- `docs/reproduce.md` — verify the hashes, reproduce the patch, rebuild the archive.
- `tools/pack.py` — the deterministic packager that produced the scored archive
  (`3c0bd8d702078d4c2158a0e6c8789868`), with the packaging rules that each cost a failed
  evaluation run preserved in its comments.
- `tools/harness_timeline.py` — reads contest harness logs, flags timed-out calls, and separates
  a call's own work from inherited wait.
- `benchmarks/heldout/` — generalization designs outside the contest suite: systolic matrix
  multiply, crossbar switch fabric, DSP/BRAM macro-heavy, LUTRAM banks, plus synthesis and probe
  scripts.
- `tests/` — Vivado-free unit tests covering the pure timing and route-status parsers, the f_max
  arithmetic, the packager's exclusion rules, and the identity of the shipped artifact.

### Notes

The submission itself is frozen. `submission/` records what was evaluated on 2026-08-13 and will
not change; anything that would alter those hashes belongs in a new major version with the reason
stated here.

[1.0.1]: https://github.com/randomuzbek/meemar-fpl26-optimizer/releases/tag/v1.0.1
[1.0.0]: https://github.com/randomuzbek/meemar-fpl26-optimizer/releases/tag/v1.0.0
