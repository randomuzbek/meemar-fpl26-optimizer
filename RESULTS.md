# Official results — FPL'26 FPGA Design Optimization Contest, final round

These are the organizers' published numbers, not ours. They were released on 2026-08-13 against
benchmark archive **v1.3.0**, with every benchmark evaluated on its own instance.

| | |
|---|---|
| Validation ID | `v_e17a8d65e4a8` |
| Submission archive md5 | `3c0bd8d702078d4c2158a0e6c8789868` |
| `dcp_optimizer.py` md5 | `64475899a43e372f4dcf441a254eec9d` |
| **Total score** | **318.254** |
| Failures / disqualifications | **0** |

## Per-benchmark scorecard

α is the f_max improvement in MHz, β the LLM spend in US dollars, γ the wall-clock hours.
Score is `max(0, α − 0.1·α·(β + γ))`.

| benchmark | f_max in | f_max out | α (MHz) | β ($) | γ (h) | score | legality |
|---|---|---|---|---|---|---|---|
| `amd_mini-isp_2025.1_v2` | 288.0 | 410.5 | 122.491 | 0.0000 | 0.0882 | **121.411** | all pass |
| `finn_radioml_2025.1` | 284.9 | 349.9 | 64.995 | 0.0000 | 0.5517 | **61.409** | all pass |
| `rosetta_digit-recognition_2025.1` | 367.0 | 428.8 | 61.844 | 0.0629 | 0.6574 | **57.389** | all pass |
| `rosetta_3d-rendering_2025.1_v2` | 236.7 | 289.6 | 52.917 | 0.0000 | 0.4151 | **50.720** | all pass |
| `fir_systolic_transposed_routed_2025.1` | 355.5 | 374.4 | 18.900 | 0.2341 | 0.8582 | **16.836** | all pass |
| `fir_symmetric_systolic_routed_2025.1` | 405.7 | 414.2 | 8.570 | 0.0128 | 1.0000 | **7.702** | all pass, γ-capped |
| `vtr_mcml_2025.1_v2` | 69.3 | 72.4 | 3.067 | 0.0384 | 0.8739 | **2.787** | all pass |
| **total** | | | **332.784** | **0.3482** | **4.4445** | **318.254** | **7/7** |

β and γ are quoted to four decimals because two and three do not add up: rounded, the β column
sums to $0.34 against a measured $0.3482, and the γ column to 4.444 h against 4.4445 h. The gaps
are rounding, not missing charges — but $0.34 is what the earlier version of this table published,
while the slide and video submitted to the organizers say $0.35. `tests/test_scorecard_table.py`
now sums each column against the totals row so a table cannot disagree with itself again.

Legality means all five organizer checks passed on every benchmark: `par_routed`,
`par_drc_clean`, `hold_passed`, `pulse_width_passed`, `sim_passed`.

## What the numbers say

**β + γ cost 14.53 points against 332.784 MHz of gain.** That is the entire budget the scoring
formula charges for compute, and it is why the optimizer treats runtime as a priced resource
rather than a free one. See [docs/scoring-model.md](docs/scoring-model.md).

**LLM spend was $0.35 in total ($0.3482), and three benchmarks spent nothing at all.** The
deterministic
prepass ladder brought `amd_mini-isp`, `finn_radioml` and `rosetta_3d-rendering` to a floor high
enough that the early-exit fired and the language model was never consulted. Those three are
three of the top four scores. The largest single result in the suite — +122.491 MHz on
`amd_mini-isp`, a 42.5 % frequency improvement — was produced with **zero** LLM calls and in
5.3 minutes of wall clock.

**Four of the seven benchmarks were unseen.** `finn_radioml`, `fir_symmetric_systolic`,
`rosetta_3d-rendering` and `rosetta_digit-recognition` did not appear in any public round. All
four scored positive and legal; three are in the top four by score.

**Determinism reproduced exactly.** `fir_systolic_transposed` returned α = 18.900 and `vtr_mcml_v2`
returned α = 3.067 — identical to the values measured in our own preview runs on the public suite,
on the organizers' hardware, weeks apart. The pipeline is deterministic by construction, which is
why the submission was frozen rather than resampled.

**One γ cap, and it was cheap.** `fir_symmetric_systolic` ran the full 3600 s. Its timeline shows
the last autosave at t = 3240 s at 414.25 MHz with no further improvement in the remaining
360 s, so the truncation cost only the 0.868 points of the γ term rather than cutting off a gain
in progress. Four MCP 300-second timeouts fired during that run — the pattern documented in
[docs/measurement-notes.md](docs/measurement-notes.md).
