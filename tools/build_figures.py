#!/usr/bin/env python3
"""Draw the README's scorecard figure from RESULTS.md, so the two cannot disagree.

A figure with numbers typed into it is a second copy of the data, and the copy is the one that
goes stale — silently, because a picture does not fail a test. This script reads the scorecard
table out of RESULTS.md and emits the SVG from it; `tests/test_figures.py` regenerates and
compares, so editing the table without redrawing fails the build.

    python3 tools/build_figures.py            # write docs/img/scorecard-{light,dark}.svg
    python3 tools/build_figures.py --check    # exit 1 if the committed SVGs are stale

Two files rather than one CSS-switched file: GitHub serves README images through an image proxy,
where a media query inside the SVG never sees the reader's theme. The README picks between them
with <picture>, which GitHub does honour.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS = REPO_ROOT / "RESULTS.md"
OUT_DIR = REPO_ROOT / "docs" / "img"

# Slots 1 and 2 of the validated categorical palette, stepped for each surface. Blue carries the
# points that survived, orange the points the search spent to get them.
THEMES = {
    "light": {
        "surface": "#ffffff",
        "panel": "#f6f8fa",
        "line": "#d0d7de",
        "text": "#1f2328",
        "muted": "#59636e",
        "kept": "#2a78d6",
        "spent": "#eb6834",
    },
    "dark": {
        "surface": "#0d1117",
        "panel": "#161b22",
        "line": "#30363d",
        "text": "#e6edf3",
        "muted": "#9198a1",
        "kept": "#3987e5",
        "spent": "#d95926",
    },
}

SANS = "ui-sans-serif,-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif"
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,monospace"

ROW = 34  # band per benchmark
BAR = 16  # mark thickness, capped well under the 24px maximum
GAP = 2  # the surface gap between the two segments of a stack
LABEL_W = 232  # benchmark names, right-aligned against the plot
PLOT_W = 560
VALUE_W = 92
PAD = 20
TOP = 74  # title, subtitle and legend


def read_scorecard(path: Path = RESULTS):
    """(benchmark, alpha, score) per row, in the order RESULTS.md lists them."""
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 8 or not cells[0].startswith("`"):
            continue
        name = cells[0].strip("`")
        alpha = float(cells[3])
        score = float(cells[6].strip("*"))
        rows.append((name, alpha, score))
    if not rows:
        raise SystemExit(f"no scorecard rows found in {path}")
    return rows


def _short(name: str) -> str:
    """`amd_mini-isp_2025.1_v2` -> `amd_mini-isp`. The tool version is noise in a figure."""
    return re.sub(r"_(routed_)?2025\.1(_v\d)?$", "", name)


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(rows, theme: str) -> str:
    c = THEMES[theme]
    width = PAD * 2 + LABEL_W + PLOT_W + VALUE_W
    height = TOP + ROW * len(rows) + 34
    scale = PLOT_W / max(alpha for _, alpha, _ in rows)
    x0 = PAD + LABEL_W + 16

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" '
        f"aria-label=\"Per-benchmark score, FPL'26 final round: 318.254 points total, "
        f'of which 14.53 points were spent on compute">',
        f'<rect width="{width}" height="{height}" fill="{c["surface"]}"/>',
        f'<text x="{PAD}" y="30" font-family="{SANS}" font-size="16" font-weight="600" '
        f'fill="{c["text"]}">Per-benchmark score — FPL\'26 final round</text>',
        f'<text x="{PAD}" y="50" font-family="{SANS}" font-size="12.5" fill="{c["muted"]}">'
        f"Each bar is the f_max gain in MHz. The score is what survived the compute charge.</text>",
    ]

    # Legend: identity never rests on colour alone, so it is present even at two series.
    legend_x = PAD
    for label, colour in (("score kept", c["kept"]), ("paid to compute (β + γ)", c["spent"])):
        out.append(f'<rect x="{legend_x}" y="60" width="9" height="9" rx="2" fill="{colour}"/>')
        out.append(
            f'<text x="{legend_x + 15}" y="68.5" font-family="{SANS}" font-size="12" '
            f'fill="{c["muted"]}">{_escape(label)}</text>'
        )
        legend_x += 26 + len(label) * 6.4

    for index, (name, alpha, score) in enumerate(rows):
        y = TOP + index * ROW
        bar_y = y + (ROW - BAR) / 2
        kept_w = score * scale
        spent_w = max(alpha * scale - kept_w - GAP, 1.5)

        out.append(
            f'<text x="{PAD + LABEL_W}" y="{bar_y + BAR - 3.5}" text-anchor="end" '
            f'font-family="{MONO}" font-size="12" fill="{c["muted"]}">{_escape(_short(name))}</text>'
        )
        # Square at the baseline, 4px rounded at the data end: the rounded rect is clipped back
        # to the baseline by a square one, rather than rounding both ends of the segment.
        out.append(
            f'<rect x="{x0}" y="{bar_y}" width="{kept_w:.1f}" height="{BAR}" fill="{c["kept"]}"/>'
        )
        out.append(
            f'<rect x="{x0 + kept_w + GAP:.1f}" y="{bar_y}" width="{spent_w:.1f}" '
            f'height="{BAR}" rx="4" fill="{c["spent"]}"/>'
        )
        out.append(
            f'<rect x="{x0 + kept_w + GAP:.1f}" y="{bar_y}" '
            f'width="{min(spent_w, 4):.1f}" height="{BAR}" fill="{c["spent"]}"/>'
        )
        out.append(
            f'<text x="{x0 + alpha * scale + 12:.1f}" y="{bar_y + BAR - 3.5}" '
            f'font-family="{MONO}" font-size="12" fill="{c["text"]}">{score:,.1f}</text>'
        )

    total_alpha = sum(alpha for _, alpha, _ in rows)
    total_score = sum(score for _, _, score in rows)
    out.append(
        f'<text x="{PAD}" y="{height - 12}" font-family="{SANS}" font-size="12.5" '
        f'fill="{c["muted"]}">{total_score:,.3f} points from {total_alpha:,.3f} MHz — the whole '
        f"search cost {total_alpha - total_score:,.2f} points, 4.4 % of the gain.</text>"
    )
    out.append("</svg>\n")
    return "\n".join(out)


def _box(c, x, y, w, h, title, lines, accent=None):
    out = [
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{c["panel"]}" '
        f'stroke="{c["line"]}"/>'
    ]
    if accent:
        out.append(f'<rect x="{x}" y="{y}" width="3.5" height="{h}" rx="1.75" fill="{accent}"/>')
    out.append(
        f'<text x="{x + 14}" y="{y + 22}" font-family="{SANS}" font-size="13" font-weight="600" '
        f'fill="{c["text"]}">{_escape(title)}</text>'
    )
    for index, line in enumerate(lines):
        out.append(
            f'<text x="{x + 14}" y="{y + 40 + index * 15}" font-family="{MONO}" font-size="11" '
            f'fill="{c["muted"]}">{_escape(line)}</text>'
        )
    return out


def _arrow(c, x1, y1, x2, y2, label=None, label_dy=-8):
    out = [
        f'<path d="M {x1} {y1} L {x2} {y2}" stroke="{c["line"]}" stroke-width="2" '
        f'fill="none" marker-end="url(#head)"/>'
    ]
    if label:
        out.append(
            f'<text x="{(x1 + x2) / 2}" y="{(y1 + y2) / 2 + label_dy}" text-anchor="middle" '
            f'font-family="{SANS}" font-size="11" fill="{c["muted"]}">{_escape(label)}</text>'
        )
    return out


def render_pipeline(theme: str) -> str:
    """The four layers as they actually run: the model is the last thing tried, not the first."""
    c = THEMES[theme]
    width, height = 880, 366
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="Pipeline: a checkpoint enters a '
        f"deterministic ladder, a cost model decides whether more search pays for itself, the "
        f'language-model stage runs only if it does, and a safety net gates every candidate">',
        f'<defs><marker id="head" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
        f'markerHeight="6" orient="auto-start-reverse">'
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{c["line"]}"/></marker></defs>',
        f'<rect width="{width}" height="{height}" fill="{c["surface"]}"/>',
        f'<text x="20" y="28" font-family="{SANS}" font-size="16" font-weight="600" '
        f'fill="{c["text"]}">How a run spends its hour</text>',
    ]

    out += _box(c, 20, 74, 116, 62, "input .dcp", ["placed,", "unrouted"])
    out += _box(
        c,
        178,
        56,
        258,
        98,
        "1 — Deterministic ladder",
        [
            "floor · phys_opt · pblock shrink",
            "free-replace · final polish",
            "byte-identical on a repeat run",
        ],
        c["kept"],
    )
    out += _box(
        c,
        478,
        56,
        212,
        98,
        "4 — Cost model",
        [
            "Δscore = Δα − 0.1·α·(Δβ + Δγ)",
            "γ caps hard at 3600 s",
            "does the next second pay?",
        ],
        c["spent"],
    )
    out += _box(c, 748, 74, 112, 62, "output .dcp", ["best proven", "state"])
    out += _box(
        c,
        478,
        208,
        212,
        76,
        "3 — LLM stage",
        [
            "best-of-K, model fallback",
            "skipped on 3 of 7 benchmarks",
        ],
        c["kept"],
    )

    out += _arrow(c, 136, 105, 174, 105)
    out += _arrow(c, 436, 105, 474, 105)
    out += _arrow(c, 690, 105, 744, 105, "no", -9)
    out += _arrow(c, 584, 154, 584, 204, "yes")
    out += [
        f'<path d="M 690 246 L 804 246 L 804 140" stroke="{c["line"]}" stroke-width="2" '
        f'fill="none" marker-end="url(#head)"/>'
    ]

    out += _box(
        c,
        20,
        298,
        840,
        54,
        "2 — Safety net, underneath all of it",
        [
            "legality gate · atomic write · autosave · rollback",
            "the output is the maximum over every state ever proven, never the last one tried",
        ],
    )
    out.append("</svg>\n")
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the committed SVGs are stale")
    args = parser.parse_args()

    rows = read_scorecard()
    figures = {}
    for theme in THEMES:
        figures[OUT_DIR / f"scorecard-{theme}.svg"] = render(rows, theme)
        figures[OUT_DIR / f"pipeline-{theme}.svg"] = render_pipeline(theme)

    stale = []
    for path, content in figures.items():
        if args.check:
            if not path.is_file() or path.read_text(encoding="utf-8") != content:
                stale.append(path.relative_to(REPO_ROOT))
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(REPO_ROOT)}")

    if stale:
        print("stale figures (run tools/build_figures.py): " + ", ".join(map(str, stale)))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
