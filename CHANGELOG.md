# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.0]: https://github.com/randomuzbek/meemar-fpl26-optimizer/releases/tag/v1.0.0
