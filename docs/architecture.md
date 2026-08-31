# Architecture

Everything ships as a single file, `submission/dcp_optimizer.py`, because the contest harness runs
exactly one entry point and a submission that depends on an importable package is a submission
that can fail to import. Line numbers below refer to that file — the frozen one with md5
`64475899a43e372f4dcf441a254eec9d`, not to any later version of it. They are checked in CI by
`tests/test_doc_anchors.py`, because a line number in prose rots silently and a reader who
lands in the wrong function has no way to tell.

The upstream reference agent is an MCP tool-use loop: it opens a design checkpoint, hands Vivado
and RapidWright tools to a language model, and lets the model drive. This submission keeps that
loop but demotes it. The model is the fourth thing that runs, not the first, and on three of the
seven scored benchmarks it never ran at all.

## Layer 1 — deterministic prepass ladder

Runs before any model call. Everything here is reproducible: the same input on the same host with
the same thread count produces a byte-identical checkpoint.

| step | function | what it does |
|---|---|---|
| floor | `_seed_baseline_floor` (1106) | Writes a legal output immediately, so the run has a non-zero result from its first minute onward |
| phys_opt | `_deterministic_phys_opt_prepass` (1139) | A fixed `phys_opt_design` chain, size-gated |
| pblock | `_deterministic_pblock_shrink` (1452) | Derives a placement constraint region from the *device*, not the design |
| free re-place | `_free_replace_prepass_skip` (1765), `_free_replace_rescue` (1841) | Full re-placement when the gate says the placement is improvable |
| surgical | `_surgical_replace` (2381) | Targeted re-placement for large designs where a full re-place is too expensive |
| retime polish | `_logicnets_retime_polish` (1372) | Narrow polish for SLICEM-heavy quantised networks |
| polish | `_final_polish` (1982) | Final pass, gated on entry WNS rather than on its own first-pass gain |

**The pblock shrink is the largest single lever.** `_deterministic_pblock_shrink` and its helpers
`_derive_pblock_range` (2477) and `_bench_literal_pblocks` (1673) build a rectangular placement
region that is device-centric, clock-region aligned, taller than it is wide, and sized to roughly
50 % utilisation density. The rule is expressed against the device geometry, so it transfers to
designs the author has never seen — which is what the held-out benchmarks under
`benchmarks/heldout/` were built to test. On the public suite it was worth +129.6, +103.4 and
+82.6 MHz on three different designs.

`_design_is_slicem_heavy` (1429) is the gate that separates designs where the LUTRAM/SRL fabric
dominates, which respond to different treatment than logic-dominated designs do.

## Layer 2 — the safety net

The contest awards zero for an illegal result, and a zero on one benchmark costs more than any
optimization gains on another. This layer exists so that a zero is structurally unreachable.

| function | guarantee |
|---|---|
| `_design_is_legal` (878) | No candidate is accepted without passing the legality gate first |
| `_atomic_write_output` (992) | The output checkpoint is never observed half-written |
| `_autosave_best` (1047) | Every proven improvement is persisted the moment it is proven |
| `_restore_best_for_retry` (1087) | A failed experiment rolls back to the last proven state |
| `_preseed_output_dcp` (4689) | The output file exists and is legal before optimization begins |
| `_resolve_api_key_or_deterministic` (4665) | A missing or empty API key degrades to the deterministic pipeline instead of crashing |

The consequence worth stating explicitly: **the emitted result is the maximum over every state
ever proven, not the last state tried.** An experiment that makes the design worse costs time and
nothing else.

`_resolve_api_key_or_deterministic` is the one that turned out to matter most in practice. An
optimizer that dies without credentials scores zero on the benchmark where the key ran out; this
one scores whatever the deterministic ladder had already banked.

## Layer 3 — the language-model stage

| function | role |
|---|---|
| `_run_stage1_best_of_k` (3327) | Samples K independent first-stage attempts and keeps the best legal one |
| `_run_llm_phase` (3428) | The bounded tool-use loop |
| `_maybe_run_stage2` (3483) | Optional second stage, with its own model |
| `_model_fallback_chain` (2832), `_is_model_unavailable_error` (2846), `_chat_completion_create` (2859) | Survives an unavailable or rate-limited model by moving down a chain rather than failing the run |
| `perform_initial_analysis` (2629), `process_response` (2525) | Design summarisation and tool dispatch |

Best-of-K matters because a single sample is high-variance: the density-box search does not
converge at K = 1, and `_autosave_best` means extra samples can only help. It is applied to the
first stage, where the variance is, rather than to the whole pipeline.

The default model is `google/gemini-3.1-flash-lite`, chosen on cost per useful decision rather
than on capability — the model's job here is narrow, and β is charged at `0.1·α` per dollar.

## Layer 4 — the cost model

The scoring formula is `max(0, α − 0.1·α·(β + γ))`, so the marginal value of another minute of
search depends on α, which depends on how well the design is already doing. This is computed at
runtime rather than assumed.

- `_gamma_fill_breakeven_mhz` (2062) answers "how many MHz would the next `n` seconds have to
  produce in order to pay for themselves?" and the caller declines to spend if the expected gain
  is below it.
- `_gamma_aware_fill` (2079) is the spend-remaining-budget path, gated on that break-even.
- The early exit (a strong-floor check after the deterministic ladder) skips the model stage
  entirely on designs the prepass has already brought near their ceiling. On the final suite it
  fired on `amd_mini-isp`, `finn_radioml` and `rosetta_3d-rendering` — the three benchmarks that
  spent $0.00 and returned three of the top four scores.
- `_remap_roundtrip_arm` (2297) is an example of a lever that was implemented, measured, and left
  off by default because it won on one benchmark and lost on five.

The reasoning behind the formula, including why a second is worth more on a fast design than on a
slow one, is in [scoring-model.md](scoring-model.md).

## Shared plumbing

`DCPOptimizerBase` (176) holds what the optimizer and the test harness share: MCP server startup
and teardown (`start_servers`, `cleanup`), clock period and WNS retrieval (`get_clock_period`,
`get_wns_for_target_clock`), and the f_max arithmetic (`calculate_fmax`). The pure parsers —
`parse_timing_summary_static` (57) and `parse_route_status_static` (111) — are module-level
functions with no I/O, which is what makes them testable without Vivado. `tests/` exercises them.

`call_tool` (723) is the single choke point through which every Vivado and RapidWright call passes,
which is where measurement instrumentation lives. Read the durations it records through
`tools/harness_timeline.py` rather than directly; [measurement-notes.md](measurement-notes.md)
explains why they are not what they appear to be.
