# Reproducing the scored submission

The scored artifact is fixed and identified by hash. This page shows how to check that what is in
this repository is what was evaluated, and how to rebuild the archive from scratch.

## What was scored

| item | value |
|---|---|
| submission archive md5 | `3c0bd8d702078d4c2158a0e6c8789868` |
| validation ID | `v_e17a8d65e4a8` |
| `dcp_optimizer.py` md5 | `64475899a43e372f4dcf441a254eec9d` |
| `SYSTEM_PROMPT.TXT` md5 | `4aaf8d8dceaea50c3153b24e0336b802` |
| `requirements.txt` md5 | `be4dc2a597aef77d292c7d832df87554` |
| upstream base commit | `a81aad5` (AMD, 2026-07-29) |
| benchmark archive | v1.3.0 |

## Step 1 — verify the files in this repository

```bash
md5sum submission/dcp_optimizer.py submission/SYSTEM_PROMPT.TXT submission/requirements.txt
```

All three must match the table above. `tests/test_submission_identity.py` asserts exactly this and
runs in CI, so a change to any of the three fails the build rather than silently redefining what
"the submission" means.

## Step 2 — verify what is ours versus what is AMD's

```bash
git clone https://github.com/Xilinx/fpl26_optimization_contest.git upstream
cd upstream
git checkout a81aad5

git -c core.autocrlf=false -c core.eol=lf apply /path/to/this/repo/submission/upstream.patch
md5sum dcp_optimizer.py requirements.txt
```

Applying `submission/upstream.patch` to upstream `a81aad5` reproduces
`submission/dcp_optimizer.py` (`64475899…`) and `submission/requirements.txt` (`be4dc2a5…`)
byte for byte. The patch is 2 873 lines and is the authoritative statement of this project's
contribution: 2 696 lines added, 105 removed, across two files.

The `core.autocrlf=false -c core.eol=lf` overrides are not optional on Windows. Without them git
smudges the result to CRLF and every hash changes — the same class of failure described under
"Why the packager works the way it does" below. `git apply` also prints
`warning: dcp_optimizer.py has type 100644, expected 100755` on some checkouts; that is a file-mode
note about the upstream blob and does not affect content.

## Step 3 — rebuild the archive

```bash
export FPL26_CONTEST_DIR=/path/to/fpl26_optimization_contest   # with the submission files in place
python3 tools/pack.py --round final --out ./build
```

`tools/pack.py` prints the resulting md5. It is the packager that produced the scored archive, and
it is deterministic by construction: content comes from the git index rather than the working
tree, file modes come from the git index, and entry timestamps are pinned to the HEAD commit time.

Reproducing `3c0bd8d702078d4c2158a0e6c8789868` byte for byte additionally requires the same
nested submodule commits (`RapidWright`, `VivadoMCP`, `RapidWrightMCP`) that were checked out at
build time, since the archive contains all of them.

### Why the packager works the way it does

Each of these is a rule paid for with a failed evaluation run, and the reasoning is preserved in
the comments inside `tools/pack.py`:

- **Content comes from the git index, not the working tree.** A Windows checkout smudges line
  endings to CRLF. Shipping worktree bytes sent a `gradlew` whose shebang read `#!/usr/bin/env sh\r`,
  which the evaluation kernel cannot execute.
- **File modes come from the git index.** Windows carries no Unix executable bit, so a naively
  built archive stores every entry non-executable and `make setup` dies at
  `./gradlew: Permission denied`.
- **The archive has exactly one top-level directory.** The validator unpacks the archive and
  changes into its sole top-level entry before running `make setup`. A second root-level entry
  breaks that detection, `make setup` runs in the wrong directory, and every benchmark reports a
  setup failure.
- **Entry timestamps are pinned to the HEAD commit time.** Zip stores naive local time; building
  in a timezone ahead of the validator produces `modification time in the future` warnings from
  `make`.
- **Only tracked files are shipped.** The working tree also contains scratch scripts and result
  dumps. Restricting to the tracked set is the equivalent of `git archive` and drops only scratch.

## Step 4 — run it

```bash
cd /path/to/fpl26_optimization_contest
make setup
export OPENROUTER_API_KEY=...      # optional
make run_optimizer DCP=<benchmark>
```

The evaluation invokes exactly `make setup` followed by `make run_optimizer DCP=<benchmark>`, with
no flags, and takes the newest `<stem>_optimized*.dcp` as the result. Vivado 2025.1 is expected at
`/tools/Xilinx/2025.1/`.

Without `OPENROUTER_API_KEY` the run does not fail: `_resolve_api_key_or_deterministic` falls
through to the deterministic pipeline, which is where most of the gain comes from anyway.

## On determinism

The deterministic pipeline is genuinely deterministic — the same input, host and thread count
produce a byte-identical checkpoint, and this reproduced the organizers' numbers to 0.01 MHz.

It was confirmed once more in the final results: two benchmarks that also appeared in the public
suite came back at α = 18.900 and α = 3.067, identical to the values measured weeks earlier on
different hardware. That is why the submission was frozen rather than resampled — repeated runs
buy nothing, so the budget went to validation instead.

Thread count is part of that contract, and the submission enforces it itself rather than relying
on the host: immediately after opening the checkpoint it issues
`set_param general.maxThreads 8`. That parameter is application-global and the MCP server holds a
single persistent Vivado process, so the one call governs every later `place_design`,
`route_design` and `phys_opt_design` in the session. `place_design` has roughly 4 MHz of
cross-thread variance, so an evaluation machine with a different native core count would otherwise
place differently and could erase a thin gain entirely. Override with `DCP_MAX_THREADS`, or
disable the pin with `DCP_PIN_THREADS=0`, if you are deliberately measuring that variance.
