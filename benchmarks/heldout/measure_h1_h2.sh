#!/usr/bin/env bash
# heldout/measure_h1_h2.sh — turnkey Task-6 measurement for the beta endgame
# harden+ratchet guards (plan docs/superpowers/plans/2026-07-03-beta-endgame-hardening.md).
# Run ON the contest instance (Vivado 2025.1) in ONE batched session to minimise the
# 55h/$ budget. Everything is $0/deterministic (DCP_SKIP_LLM=1) except the optional P3.
#
# Assumes the fleet conventions from HELDOUT_BENCH_2026-06-15.md:
#   - synth driver : heldout/synth_bench.tcl
#   - eval driver  : /home/det_eval.sh <basename>   (runs `python3 dcp_optimizer.py`)
#   - bench dir    : /home/fpl26_contest_benchmarks/<basename>.dcp
#   - persisted DCPs from prior held-out runs: /home/heldout/*.dcp
# det_eval.sh prints BASELINE/FINAL fmax + TOTAL_WALL_S; the pipeline's own
# [pblock]/[cellcount]/[legality] lines go to its log — we tee everything per run.
#
# Usage:
#   bash heldout/measure_h1_h2.sh build   [NB] [PERIOD_NS]   # P1: build lutram DCP, report cells
#   bash heldout/measure_h1_h2.sh h1      [NB] [PERIOD_NS]   # P2: H1 A/B (SLICEM_SKIP 0 vs 1)
#   bash heldout/measure_h1_h2.sh h2                          # P3: H2 cell-count across corpus
#   bash heldout/measure_h1_h2.sh all     [NB] [PERIOD_NS]   # build -> h1 -> h2
set -uo pipefail

NB="${2:-600}"           # ~600 banks ≈ 40k cells (SLICEM ratio ~0.5); sweep to land 30-80k
PERIOD="${3:-1.20}"      # below achievable delay -> mild-negative WNS (responsive band)
BENCHDIR=/home/fpl26_contest_benchmarks
OUTDIR=/home/heldout
LOGDIR="${OUTDIR}/logs_h1h2"
DETEVAL=/home/det_eval.sh
mkdir -p "$OUTDIR" "$LOGDIR"

# Locate the repo root (this script lives in heldout/) so synth_bench.tcl is found.
HERE="$(cd "$(dirname "$0")" && pwd)"

cells_of () {  # extract the synthesized primitive cell count from a build log
  grep -Eo 'RESULT_CELLS[[:space:]]+[0-9]+' "$1" 2>/dev/null | awk '{print $2}' | tail -1
}

build_lutram () {
  local nb="$1" period="$2" log="${LOGDIR}/build_lutram_NB${1}.log"
  echo "== P1 BUILD lutram_bank NB=$nb period=${period}ns =="
  # synth_bench.tcl already runs synth->opt->place->phys_opt->route->write_checkpoint and
  # prints RESULT_WNS/FMAX. We add a cell count so NB can be tuned to the 30-80k target.
  vivado -mode batch -source "${HERE}/synth_bench.tcl" -tclargs \
      "${HERE}/lutram_bank.v" lutram_bank "$period" "${OUTDIR}/lutram.dcp" clk "NB=${nb}" \
      2>&1 | tee "$log"
  local nc; nc="$(cells_of "$log")"
  echo "-- RESULT_CELLS=${nc:-?}  (target 30000-80000 so the derived-box + Explore path fires) --"
  grep -iE 'RESULT_WNS|RESULT_CELLS|FMAX' "$log" | tail -4
  if [ -n "${nc:-}" ] && { [ "$nc" -lt 30000 ] || [ "$nc" -gt 80000 ]; }; then
    local guess=$(( nb * 55000 / (nc>0?nc:1) ))     # linear interp to the 55k midpoint
    echo ">> TUNE: cells ${nc} outside [30k,80k]; retry NB≈${guess}: bash $0 build ${guess} ${period}"
  else
    cp -f "${OUTDIR}/lutram.dcp" "${BENCHDIR}/lutram.dcp" && echo "staged ${BENCHDIR}/lutram.dcp (in range)"
  fi
}

eval_capture () {  # $1=basename $2=extra-env-prefix $3=tag
  local base="$1" envp="$2" tag="$3" log="${LOGDIR}/eval_${base}_${tag}.log"
  echo "== EVAL ${base} [${tag}] : ${envp} =="
  # shellcheck disable=SC2086
  env DCP_SKIP_LLM=1 ${envp} bash "$DETEVAL" "$base" 2>&1 | tee "$log"
  echo "-- guard/route lines [${tag}] --"
  grep -nE '\[pblock\]|\[cellcount\]|\[legality\]|BASELINE|FINAL|TOTAL_WALL_S|routable|fully routed|error' "$log" | tail -30
  echo
}

case "${1:-all}" in
  build) build_lutram "$NB" "$PERIOD" ;;
  h1)
    echo "### P2 — H1 A/B: does the SLICEM-blind derived box throw, and does the skip help?"
    eval_capture lutram "DCP_PBLOCK_SLICEM_SKIP=0" guardoff   # OLD: derived box may place-throw
    eval_capture lutram "DCP_PBLOCK_SLICEM_SKIP=1" guardon    # NEW: skip -> free-replace
    echo ">> DECISION: guardon FINAL fmax must be >= guardoff (defers to free-replace, so >=)."
    echo ">>           and final output legal+routed on BOTH (1.1 autosave floor)."
    ;;
  h2)
    echo "### P3 — H2 inertness: no held-out design may net-decrease cells (guard must stay inert)"
    for b in corearray systolic_mm switchfab dsp_macc lutram; do
      [ -f "${BENCHDIR}/${b}.dcp" ] || { echo "skip ${b} (no DCP at ${BENCHDIR})"; continue; }
      eval_capture "$b" "" cellcount
    done
    echo ">> DECISION: confirm NO design triggers the [legality] cell-count block (guard inert);"
    echo ">>           any legitimate 0-3% drop that still routes must NOT be blocked."
    ;;
  all)
    build_lutram "$NB" "$PERIOD"
    "$0" h1 "$NB" "$PERIOD"
    "$0" h2
    ;;
  *) echo "usage: bash $0 {build|h1|h2|all} [NB] [PERIOD_NS]"; exit 2 ;;
esac
