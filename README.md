# MEEMAR — FPL'26 FPGA Design Optimization Contest submission

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Score](https://img.shields.io/badge/final%20score-318.254-brightgreen.svg)](RESULTS.md)
[![Legality](https://img.shields.io/badge/legality-7%2F7%20clean-brightgreen.svg)](RESULTS.md)

A post-placement FPGA timing optimizer that **prices its own compute in contest points** and
stops when the next second stops paying for itself.

This is the submission that scored **318.254 across seven benchmarks with zero
disqualifications** in the [FPL'26 FPGA Design Optimization Contest](https://xilinx.github.io/fpl26_optimization_contest/),
placing in the top five. One person, no institutional compute.

---

## The result

| | |
|---|---|
| Total score | **318.254** |
| Benchmarks | 7 (four of them unseen before the final round) |
| Legality | **7/7 fully clean** — routed, DRC clean, hold, pulse width, simulation |
| Sum of f_max improvement | **332.784 MHz** |
| Total LLM spend | **$0.34** across all seven benchmarks |
| Best single design | `amd_mini-isp` 288.0 → **410.5 MHz** (+42.5 %) |

Full per-benchmark scorecard, including the α/β/γ decomposition: **[RESULTS.md](RESULTS.md)**.

## The idea

The contest does not score frequency. It scores

```
per-benchmark score = max(0, α − 0.1·α·(β + γ))
```

where α is the f_max improvement in MHz, β is dollars spent on LLM calls and γ is wall-clock
hours. Two consequences drive the entire design of this optimizer.

**A dollar costs exactly what an hour costs, and both scale with α.** Searching harder is not
free — it is charged at `0.1·α` per unit. On a design where α is 103, a 442-second run has
already burned 1.25 points before any gain is counted; on a design where α is 12, an hour costs
almost nothing. So the correct amount of search is *different on every design*, and it depends on
how well that design is already doing. This inverts the obvious intuition: a second is worth most
on the designs that are already fast and high-α, not on the slowest one.

**γ has a hard 3600-second cap, and it is a cliff rather than a slope.** A truncated run does not
merely pay the γ term; it loses every megahertz it had not yet banked. Seconds spent near the cap
can cost α outright.

This optimizer therefore computes its own break-even before spending
(`_gamma_fill_breakeven_mhz`), banks every improvement to disk the moment it is proven
(`_autosave_best`), and exits early on designs a deterministic pass has already brought close to
their ceiling. The reasoning is written up in **[docs/scoring-model.md](docs/scoring-model.md)**.

## How it works

Four layers, all inside `submission/dcp_optimizer.py`.

**1. A deterministic prepass ladder** runs before any language model is consulted, and does most
of the work. `_seed_baseline_floor` immediately banks a legal output so that no later failure can
produce a zero. Then `_deterministic_phys_opt_prepass`, `_deterministic_pblock_shrink` (a
device-centric, clock-region-aligned, roughly 50 %-density pblock derivation — the single largest
lever), `_free_replace_rescue` and `_surgical_replace` for designs whose placement is improvable,
and `_final_polish`. Same input, same host, same thread count produces a byte-identical result.

**2. A safety net** that makes an illegal or worse-than-input result structurally impossible.
`_design_is_legal` gates every candidate, `_atomic_write_output` prevents partial writes,
`_autosave_best` keeps the best proven state, `_restore_best_for_retry` rolls back, and
`_resolve_api_key_or_deterministic` degrades to the deterministic pipeline when no API key is
present rather than crashing. The output is the maximum over everything ever proven, never the
last thing tried.

**3. An LLM layer** — best-of-K first-stage sampling (`_run_stage1_best_of_k`), an optional second
stage (`_maybe_run_stage2`), and a model fallback chain (`_model_fallback_chain`) so that a single
unavailable model cannot end a run. It is deliberately the *last* layer: on three of the seven
final benchmarks it was skipped entirely, and those three scored highest.

**4. The cost model** described above, wired into runtime decisions rather than applied in
hindsight.

Detail, with the call graph: **[docs/architecture.md](docs/architecture.md)**.

## What is honest about this

`_matches_v2_fingerprint` and its three siblings are benchmark fingerprints: cheap primitive-count
and port-count checks that let a known-shaped design skip straight to the treatment that worked
for it. They look like overfitting to the public suite, and it is fair to read them that way.

The counter-evidence is on the record rather than asserted. The fingerprints are a fast path, not
the mechanism — the generic decision function (`_generic_free_replace_decision`) handles anything
unrecognised, and it is what ran on the unseen designs. **Four of the seven final benchmarks had
never been seen**, all four scored positive and clean, and three of them are in the top four by
score. Generalization was also tested before the final round on designs that are not RISC-V cores
at all — systolic matrix multiply, crossbar switch fabric, DSP/BRAM macro-heavy, LUTRAM banks —
which are published here under [`benchmarks/heldout/`](benchmarks/heldout/).

Two more things worth stating plainly. One benchmark (`fir_symmetric_systolic`) hit the 3600 s γ
cap; its timeline shows the last improvement at t = 3240 s, so the truncation cost only the γ term
itself rather than a banked gain. And the determinism claim was verified against the organizers'
own numbers: two repeated benchmarks came back byte-identical to our preview runs.

## Layout

```
submission/          the scored artifact, byte-exact
  dcp_optimizer.py     md5 64475899a43e372f4dcf441a254eec9d
  SYSTEM_PROMPT.TXT    md5 4aaf8d8dceaea50c3153b24e0336b802
  requirements.txt     md5 be4dc2a597aef77d292c7d832df87554
  upstream.patch       full diff against AMD upstream a81aad5 — exactly what is ours
docs/                architecture, scoring model, measurement notes, reproduction
tools/
  pack.py              the deterministic packager that built the scored zip
  harness_timeline.py  reads contest harness logs without being lied to by them
benchmarks/heldout/  generalization designs outside the contest suite
tests/               Vivado-free unit tests for the parsing and packaging paths
```

## Running it

The optimizer runs inside the contest harness, which supplies Vivado, RapidWright and the two MCP
servers. It is not a standalone tool.

```bash
git clone --recursive https://github.com/Xilinx/fpl26_optimization_contest.git
cd fpl26_optimization_contest
git checkout a81aad5
cp /path/to/this/repo/submission/dcp_optimizer.py .
cp /path/to/this/repo/submission/SYSTEM_PROMPT.TXT .
cp /path/to/this/repo/submission/requirements.txt .

make setup
export OPENROUTER_API_KEY=...        # optional: without it the deterministic pipeline still runs
make run_optimizer DCP=<benchmark>
```

To rebuild the submitted archive and check its md5 against the scored one, see
**[docs/reproduce.md](docs/reproduce.md)**.

The unit tests need neither Vivado nor an FPGA:

```bash
pip install -r requirements-dev.txt
pytest -q
```

## Citing

A `CITATION.cff` is included; GitHub's "Cite this repository" button will format it for you.

## License and attribution

Apache-2.0. `submission/dcp_optimizer.py` is a derivative work of a file
© 2026 Advanced Micro Devices, Inc., and retains AMD's copyright and license headers. See
[`NOTICE`](NOTICE) for the split between upstream and our modifications, and
[`submission/upstream.patch`](submission/upstream.patch) for the exact diff.

Thanks to the contest organizers at AMD — Chris Lavin and Preston Walker — for a benchmark suite
and evaluation harness that rewarded measurement over guesswork, and to Prof. Enver Çavuş for
advising the entry.
