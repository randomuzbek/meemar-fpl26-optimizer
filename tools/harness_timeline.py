#!/usr/bin/env python3
"""Read a preview's harness logs honestly: where the wall went, and what is misattributed.

WHY THIS EXISTS. On 2026-08-07 I read boom's per-call durations straight out of a
harness log and concluded `report_timing_summary` cost 588 + 506 + 218 s -- 39 % of the
bench's wall. It does not. `VivadoMCP/vivado_mcp_server.py:213` gives `run_tcl` a **300 s
pexpect timeout**; when it fires the server marks `_command_pending`, raises, and returns
the timeout as an ORDINARY result, so the optimizer records the call as `OK` at exactly
300.1 s and logs no error at all. The abandoned command keeps running inside Vivado, and
the NEXT call silently blocks in `sync_after_timeout` waiting for it before doing its own
work. On boom that next call is nearly always the timing report -- so `place_design`'s and
`phys_opt_design`'s tails get billed to the report.

A real report costs 1-3 s on amd, 4-7 s on fir, 2-4 s on optical, 3-5 s on vtr and
27-51 s on boom. The inflated readings were off by ~10x, and a whole lane was very nearly
submitted on them. So: never read these durations by eye again -- read them through this.

    python3 tools/harness_timeline.py results/final/preview/attempt-6/logs.zip
    python3 tools/harness_timeline.py <dir-or-zip> --bench boom --detail

`--detail` prints the full chronological timeline (what a phase-by-phase comparison of two
runs needs). Without it you get the per-bench cost summary and the contamination warning.

Pricing uses M3 from docs/scoring-model.md: dscore = dalpha - 0.1*alpha*(dbeta + dgamma_h),
with alpha read from the sibling scorecard.json (`alpha_fmax_improvement_mhz`). Note what
that means on a cap-adjacent bench: boom's gamma term makes 150 s worth 0.05 points, but
the 2.56 MHz it fails to bank when the 3600 s cap truncates it is worth ~2.4. Seconds
there matter through what they let the run FINISH, not through the gamma term.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import zipfile
from pathlib import Path

# A run_tcl whose client-observed duration lands in this window did not take that long --
# it hit the server's 300 s pexpect timeout and was abandoned mid-flight.
TIMEOUT_LO, TIMEOUT_HI = 299.5, 301.0

LINE = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d,\d+) - (\w+) - (.*)$")
CALL = re.compile(r"^Calling (\S+) with args: (.*)$")


def _load(source: Path) -> dict[str, str]:
    """bench name -> harness log text, from a logs.zip or an unpacked directory."""
    logs: dict[str, str] = {}
    if source.is_dir():
        for p in sorted(source.glob("*.harness.log")):
            logs[p.name.split(".harness")[0]] = p.read_text("utf-8", "replace")
        zips = sorted(source.glob("logs.zip"))
        if not logs and zips:
            return _load(zips[0])
    else:
        with zipfile.ZipFile(source) as z:
            for n in sorted(z.namelist()):
                if n.endswith("harness.log"):
                    logs[n.split(".harness")[0]] = z.read(n).decode("utf-8", "replace")
    return logs


def _alpha(source: Path) -> dict[str, float]:
    base = source if source.is_dir() else source.parent
    sc = base / "scorecard.json"
    if not sc.exists():
        return {}
    try:
        data = json.loads(sc.read_text("utf-8"))
    except Exception:
        return {}
    return {
        b["name"]: float(b.get("alpha_fmax_improvement_mhz") or 0.0)
        for b in data.get("benchmarks", [])
        if b.get("name")
    }


class Call:
    __slots__ = ("after_timeout", "args", "elapsed", "idx", "notes", "secs", "tool")

    def __init__(self, idx, tool, args, secs, elapsed):
        self.idx, self.tool, self.args = idx, tool, args
        self.secs, self.elapsed = secs, elapsed
        self.after_timeout = False
        self.notes: list[str] = []

    @property
    def timed_out(self) -> bool:
        return TIMEOUT_LO < self.secs < TIMEOUT_HI

    @property
    def label(self) -> str:
        t = self.tool.replace("vivado_", "v.").replace("rapidwright_", "rw.")
        cmd = ""
        m = re.search(r'"command":\s*"(.*?)"', self.args)
        if m:
            cmd = m.group(1)
        elif '"dcp_path"' in self.args:
            m2 = re.search(r'"dcp_path":\s*"([^"]*)"', self.args)
            cmd = Path(m2.group(1)).name if m2 else ""
        return f"{t} {cmd}"[:78]


def parse(text: str) -> tuple[list[Call], list[str], float | None]:
    events: list[tuple[dt.datetime, str]] = []
    for line in text.splitlines():
        m = LINE.match(line)
        if m:
            ts = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S,%f")
            events.append((ts, m.group(3)))
    wall = None
    for line in text.splitlines():
        if line.startswith("WALL_SECONDS"):
            try:
                wall = float(line.split("=", 1)[1])
            except ValueError:
                pass

    calls: list[Call] = []
    banked: list[str] = []
    t0 = events[0][0] if events else None
    for i, (ts, msg) in enumerate(events):
        nxt = events[i + 1][0] if i + 1 < len(events) else ts
        if "New best WNS" in msg or "[autosave]" in msg:
            banked.append(f"t={int((ts - t0).total_seconds()):5d}  {msg[:96]}")
        m = CALL.match(msg)
        if m:
            calls.append(
                Call(
                    len(calls) + 1,
                    m.group(1),
                    m.group(2),
                    (nxt - ts).total_seconds(),
                    (ts - t0).total_seconds(),
                )
            )
    # Contamination propagates, and NOT just to the next call. `route_design` after a
    # timed-out `place_design` sync-waits for it and then hits its own 300 s timeout -- so
    # it shows neither 300.1 s nor its true cost, and it leaves a command pending for the
    # call after it. Boom #6: place_design 300.1 -> route_design 847 -> report 557, all
    # three unreadable, and only then does a 0.5 s WNS query appear.
    #
    # What CAN be trusted is drainage: `sync_after_timeout` waits for Vivado's prompt, so a
    # call that returned quickly proves nothing was outstanding when it ran. So a timeout
    # taints every following call until a short one proves the queue empty again.
    DRAINED_UNDER = 30.0
    pending = False
    for c in calls:
        if pending:
            if c.secs < DRAINED_UNDER:
                pending = False  # this call proves Vivado was idle; it is clean
            else:
                c.after_timeout = True
                c.notes.append("includes an abandoned command's tail")
        if c.timed_out:
            pending = True
    return calls, banked, wall


def report(
    bench: str,
    calls: list[Call],
    banked: list[str],
    wall: float | None,
    alpha: float | None,
    detail: bool,
) -> None:
    print(f"\n=== {bench} " + "=" * max(0, 60 - len(bench)))
    tos = [c for c in calls if c.timed_out]
    print(
        f"wall {wall if wall is not None else '?'}s over {len(calls)} tool calls"
        + (f"   alpha {alpha:.3f} MHz" if alpha else "")
    )

    if tos:
        print(
            f"\n  !! {len(tos)} call(s) hit the 300 s MCP timeout -- durations after each are "
            f"NOT that call's own cost:"
        )
        for c in tos:
            print(f"     #{c.idx} t={c.elapsed:.0f}s  {c.label}")
        print(
            "     (the abandoned command kept running in Vivado; the next call waited for it "
            "in\n      sync_after_timeout and then DISCARDED its output)"
        )
    else:
        print("\n  no 300 s timeouts -- per-call durations on this bench can be read directly.")

    trust = [c for c in calls if not c.after_timeout and not c.timed_out]
    print("\n  costliest calls whose duration is its OWN work:")
    for c in sorted(trust, key=lambda c: -c.secs)[:8]:
        print(f"    {c.secs:8.1f}s  #{c.idx:<3} {c.label}")

    contaminated = [c for c in calls if c.after_timeout]
    if contaminated:
        print("\n  calls billed for someone else's work (do NOT price these):")
        for c in sorted(contaminated, key=lambda c: -c.secs)[:6]:
            print(f"    {c.secs:8.1f}s  #{c.idx:<3} {c.label}")

    # The specific question this file was written to answer honestly.
    rts = [c for c in calls if c.tool == "vivado_report_timing_summary"]
    clean = [c for c in rts if not c.after_timeout]
    if rts:
        tot = sum(c.secs for c in clean)
        print(
            f"\n  report_timing_summary: {len(rts)} calls, {len(clean)} priceable, "
            f"{tot:.1f}s total" + (f", {[f'{c.secs:.0f}' for c in clean]}" if clean else "")
        )
        if alpha and tot:
            print(
                f"    skipping all of them is worth 0.1*{alpha:.2f}*{tot:.0f}/3600 = "
                f"{0.1 * alpha * tot / 3600:.3f} points of gamma"
                + (
                    "  (plus cap headroom, which is what actually matters here)"
                    if wall and wall > 3000
                    else ""
                )
            )

    if banked:
        print("\n  what was banked:")
        for b in banked[-6:]:
            print(f"    {b}")

    if detail:
        print("\n  --- full timeline ---")
        for c in calls:
            mark = " !TIMEOUT" if c.timed_out else (" ~sync" if c.after_timeout else "")
            print(f"    t={c.elapsed:6.0f} +{c.secs:7.1f}  #{c.idx:<3} {c.label}{mark}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("source", type=Path, help="logs.zip, or a directory holding one")
    ap.add_argument("--bench", default="", help="only benches whose name contains this")
    ap.add_argument("--detail", action="store_true", help="print the full chronological timeline")
    a = ap.parse_args()

    if not a.source.exists():
        print(f"not found: {a.source}", file=sys.stderr)
        return 2
    logs = _load(a.source)
    if not logs:
        print(f"no *.harness.log in {a.source}", file=sys.stderr)
        return 2
    alphas = _alpha(a.source)

    for bench, text in logs.items():
        if a.bench and a.bench not in bench:
            continue
        calls, banked, wall = parse(text)
        if not calls:
            continue
        report(bench, calls, banked, wall, alphas.get(bench), a.detail)

    print(
        "\nM3: dscore = dalpha - 0.1*alpha*(dbeta + dgamma_h). On a cap-adjacent bench the "
        "gamma\nterm understates the stakes -- boom's 150 s is 0.05 points, but the 2.56 MHz "
        "it fails\nto bank when the 3600 s cap truncates it is ~2.4."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
