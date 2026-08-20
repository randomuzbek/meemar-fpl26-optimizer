# Measurement notes

Three traps that each cost real time, written down because they are properties of the contest
harness and the toolchain rather than of this submission — a future entrant will meet all three.

## 1. The 300-second MCP timeout is recorded as a success

`VivadoMCP/vivado_mcp_server.py:213` gives `run_tcl` a 300-second `pexpect` timeout. When it
fires, the server marks `_command_pending`, raises, and **returns the timeout as an ordinary
result**. The optimizer therefore records the call as `OK` at exactly 300.1 seconds, and nothing
is logged as an error anywhere.

The abandoned Tcl command keeps running inside Vivado. The next call blocks in
`sync_after_timeout` — for up to an hour — waiting for it, and then discards its output. So the
abandoned command's tail is billed to whatever call syncs next, and contamination propagates until
some call returns in under about 30 seconds and proves Vivado idle again.

What this does to a naive reading: on one benchmark, `report_timing_summary` appeared to cost 588,
506 and 218 seconds — 39 % of the benchmark's wall clock. It actually costs about 5 seconds
post-route, and 27–51 seconds on a freshly opened design where the timing graph is still cold. The
readings were off by an order of magnitude, and an optimization lane was very nearly submitted on
them.

**Never read these durations by eye.** `tools/harness_timeline.py` flags the 300.1-second calls,
marks the contaminated window, and separates a call's own work from the wait it inherited:

```bash
python3 tools/harness_timeline.py path/to/logs.zip
python3 tools/harness_timeline.py path/to/logs.zip --bench <name> --detail
```

## 2. Your own A/B tests need the same confounder discipline as the evaluation

**Page cache.** An A/B with a fixed arm order makes the first arm pay every cold read. Measured
directly: run first, immediately after `make setup` had extracted a 707 MB benchmark tarball, a
`open_checkpoint` took **352.7 seconds**; warm, the same call took **47.9 seconds**. That 305
seconds masqueraded as a 239-second win plus +0.33 MHz, and nearly shipped a change actually worth
about 6 seconds.

Either warm the input before timing it —

```bash
cat "$dcp" > /dev/null
```

— or alternate the arm order between runs. And always check a phase the change *cannot* touch
before attributing anything to the change; that check is what caught this one.

**Evaluation-machine speed.** The same discipline applies to the organizers' runs. Machine speed
varies between evaluations, and it is a confounder in every preview comparison. Check
`wall_time_seconds` on a benchmark your change cannot affect before believing a difference.

## 3. Measure in the configuration you will ship

Two versions of the same mistake, made twice.

**Skipping the LLM stage while measuring a change that interacts with it.** A gamma-fill candidate
measured **+3.55 MHz** with the model stage disabled and produced **zero** α in the organizers'
evaluation. The reason is structural: in the real run, the draw is judged against the floor the
model stage has already lifted, so a candidate that improves a lower floor improves nothing at
all. Anything downstream of the model must be measured with the model on.

**N = 1 with validation skipped is not a measurement.** Every candidate that beats the control
needs full validation, not just the argmax of a sweep. A sweep that finds a winner without
validating it has found a hypothesis.

## Two habits worth stealing

**Read the data you already have before spending compute on new data.** Every evaluation run in
this contest ships a per-benchmark harness log, and those logs sat unread while three separate
lanes and two compute campaigns circled a question the logs answered directly — in forty-five
minutes, at zero cost. The recurring failure was never weak measurement; it was not reading what
was already on disk.

**Verify claims against the code, not against notes.** A stale note about the behaviour of one
Vivado directive survived two months and misled an entire working session. The code said
otherwise, in one line, the whole time.
