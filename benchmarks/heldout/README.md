# Held-out benchmark harness

Builds unseen-design DCPs (contest format, `clk_fpl26contest`, xcvu3p-ffvc1517-2-e) to **measure**
generalization of the optimizer instead of guessing it. See `../HELDOUT_BENCH_2026-06-15.md` for the
first run's results (4 designs, all improved, zero regressions).

## RTL sources
- PicoRV32: `curl -sL https://raw.githubusercontent.com/YosysHQ/picorv32/main/picorv32.v`
- `corearray.v` — parameterized N× PicoRV32 array (ring + registered XOR reduction; keeps cores live)
- VexRiscv: coursier (no root) → JDK17 → `sbt "runMain vexriscv.demo.GenFull"` → `VexRiscv.v`
  ```
  curl -fLs https://github.com/coursier/coursier/releases/latest/download/cs-x86_64-pc-linux.gz | gunzip > cs && chmod +x cs
  eval "$(./cs java --jvm temurin:17 --env)"
  git clone --depth 1 https://github.com/SpinalHDL/VexRiscv.git && cd VexRiscv
  ../cs launch sbt -- "runMain vexriscv.demo.GenFull"
  ```

## Build a DCP
```
vivado -mode batch -source synth_bench.tcl -tclargs <files,csv> <top> <period_ns> <out.dcp> <clkport> [generics]
# e.g. single full core:  picorv32.v,corearray.v corearray 1.45 out.dcp clk "N=1"
# e.g. 24-core array:     picorv32.v,corearray.v corearray 4.0  out.dcp clk "N=24"
# e.g. VexRiscv:          VexRiscv/VexRiscv.v VexRiscv 1.80 out.dcp clk
```
Set the period **below** the achievable path delay to land in the negative-WNS band (matches the
responsive contest benches). Vivado meets any achievable (loose) constraint, leaving WNS≈0.

## Deterministic eval ($0)
```
cp out.dcp /home/fpl26_contest_benchmarks/<basename>.dcp
bash /home/det_eval.sh <basename>      # prints BASELINE / FINAL fmax + TOTAL_WALL_S
```
