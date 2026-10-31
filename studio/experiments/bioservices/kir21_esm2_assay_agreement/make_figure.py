"""Render predictions against measurements as a standalone SVG.

Two panels, one per assay, sharing the x axis so the two agreements are read on
the same prediction scale. Small multiples rather than an overlay: the question
is whether the model tracks one assay better than the other, and two clouds on
one pair of axes would answer it worse.

Each panel carries one series, so its title names the series and no legend box
is needed. Colours are the validated categorical slots 1 and 2, stepped for each
mode; every number and label wears a text token, never the series colour.

No dependency beyond the standard library -- the SVG is written directly, so the
figure can be regenerated anywhere the repository is checked out.
"""

from __future__ import annotations

import argparse
import csv
import json
import math

# Validated categorical slots 1 (blue) and 2 (orange), light and dark steps.
LIGHT = {"surface": "#2a78d6", "function": "#eb6834", "bg": "#fcfcfb",
         "ink": "#0b0b0b", "ink2": "#52514e", "grid": "#e2e1dd"}
DARK = {"surface": "#3987e5", "function": "#d95926", "bg": "#1a1a19",
        "ink": "#f0efec", "ink2": "#c3c2b7", "grid": "#343431"}

W, H = 940, 716
PANEL_W, PANEL_H = 370, 290
PAD_L, PAD_T, GAP = 68, 118, 56
# Roughly how many characters of 11.5px system-ui fit across the plotting width.
WRAP_COLS = 122


def _wrap(text: str, cols: int = WRAP_COLS) -> list[str]:
    """Greedy word wrap. The figure is standalone SVG, which has no text flow,
    so every caption line is placed by hand and must be wrapped before placing."""
    words, lines, cur = text.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if len(trial) > cols and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def _nice_ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    if not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo:
        return [lo, hi]
    raw = (hi - lo) / target
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10)), key=lambda s: abs(s - raw))
    first = math.ceil(lo / step) * step
    out, v = [], first
    while v <= hi + step * 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def _esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _panel(rows, xkey, ykey, x0, y0, title, role, xlim, ylim, annotation) -> str:
    xlo, xhi = xlim
    ylo, yhi = ylim
    sx = lambda v: x0 + (v - xlo) / (xhi - xlo) * PANEL_W
    sy = lambda v: y0 + PANEL_H - (v - ylo) / (yhi - ylo) * PANEL_H
    parts = ['<g class="panel">']
    parts.append(f'<text x="{x0}" y="{y0 - 14}" class="panel-title">{_esc(title)}</text>')

    for t in _nice_ticks(ylo, yhi):
        y = sy(t)
        if not (y0 - 1 <= y <= y0 + PANEL_H + 1):
            continue
        parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{x0 + PANEL_W}" y2="{y:.1f}" class="grid"/>')
        parts.append(f'<text x="{x0 - 10}" y="{y + 4:.1f}" class="tick tick-y">{t:g}</text>')
    for t in _nice_ticks(xlo, xhi):
        x = sx(t)
        if not (x0 - 1 <= x <= x0 + PANEL_W + 1):
            continue
        parts.append(f'<line x1="{x:.1f}" y1="{y0}" x2="{x:.1f}" y2="{y0 + PANEL_H}" class="grid"/>')
        parts.append(f'<text x="{x:.1f}" y="{y0 + PANEL_H + 20}" class="tick tick-x">{t:g}</text>')

    parts.append(f'<line x1="{x0}" y1="{y0 + PANEL_H}" x2="{x0 + PANEL_W}" y2="{y0 + PANEL_H}" class="axis"/>')
    parts.append(f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y0 + PANEL_H}" class="axis"/>')

    for r in rows:
        x, y = sx(float(r[xkey])), sy(float(r[ykey]))
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" class="pt pt-{role}">'
                     f'<title>{_esc(r["mutant"])}: ESM-2 {float(r[xkey]):.2f}, '
                     f'measured {float(r[ykey]):.2f}</title></circle>')

    # A backing plate, so the statistics stay readable where points are dense.
    plate_h = 12 + len(annotation) * 17
    parts.append(f'<rect x="{x0 + 2}" y="{y0 + 4}" width="186" height="{plate_h}" rx="3" class="plate"/>')
    for i, line in enumerate(annotation):
        cls = "annot-strong" if i == 0 else "annot"
        parts.append(f'<text x="{x0 + 10}" y="{y0 + 21 + i * 17}" class="{cls}">{_esc(line)}</text>')
    parts.append("</g>")
    return "".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description="Render the Kir2.1 evaluation figure")
    ap.add_argument("--csv", required=True)
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rows = list(csv.DictReader(open(args.csv)))
    an = json.load(open(args.analysis))
    esm = an["results"]["esm2_masked_marginal"]

    xs = [float(r["esm2_masked_marginal"]) for r in rows]
    xlim = (min(xs), max(xs))
    pad = (xlim[1] - xlim[0]) * 0.04
    xlim = (xlim[0] - pad, xlim[1] + pad)

    def ylim_for(key):
        v = [float(r[key]) for r in rows]
        lo, hi = min(v), max(v)
        p = (hi - lo) * 0.05 or 1.0
        return (lo - p, hi + p)

    def annot(side):
        r = esm[f"rho_{side}"]
        return [f"Spearman ρ = {r['point']:+.3f}",
                f"95% CI [{r['ci_low']:+.3f}, {r['ci_high']:+.3f}]",
                f"permutation p = {esm['permutation_p_' + side]:.3g}"]

    d = esm["delta_rho_surface_minus_function"]
    cb = esm["cluster_bootstrap_by_position"]
    w = esm["williams_test"]
    cov = an["coverage"]

    body = [
        _panel(rows, "esm2_masked_marginal", "surface_dms_score", PAD_L, PAD_T,
               "Surface expression", "surface", xlim, ylim_for("surface_dms_score"), annot("surface")),
        _panel(rows, "esm2_masked_marginal", "function_dms_score", PAD_L + PANEL_W + GAP, PAD_T,
               "Channel function", "function", xlim, ylim_for("function_dms_score"), annot("function")),
    ]

    strip_y = PAD_T + PANEL_H + 92
    covered = {int(r["position"]) for r in rows}
    total_w = PANEL_W * 2 + GAP
    body.append(f'<text x="{PAD_L}" y="{strip_y - 10}" class="strip-label">'
                f'Positions scored: {len(covered)} distinct of {cov["matched_distinct_positions"]} '
                f'in the matched set (residues 1–428)</text>')
    body.append(f'<rect x="{PAD_L}" y="{strip_y}" width="{total_w}" height="12" class="strip-bg"/>')
    for p in sorted(covered):
        x = PAD_L + (p - 1) / 428 * total_w
        body.append(f'<rect x="{x:.2f}" y="{strip_y}" width="1.6" height="12" class="strip-tick"/>')

    verdict = esm["verdict_on_H1"]
    caption = [
        f"n = {an['n_usable']} matched variants, hashed subset of {an['n_matched']}; "
        f"checkpoint {an['checkpoint_used']}; masked marginals, zero-shot.",
        f"Δρ (surface − function) = {d['point']:+.3f}, 95% CI "
        f"[{d['ci_low']:+.3f}, {d['ci_high']:+.3f}] by variant; "
        f"[{cb['delta_ci_low']:+.3f}, {cb['delta_ci_high']:+.3f}] clustered by position; "
        f"paired permutation p = {esm['paired_permutation_delta']['p_two_sided']:.3g}"
        + (f"; Williams p = {w['p_two_sided']:.3g}" if w.get("applicable") else ""),
        f"H1 (better agreement with surface expression): {verdict.upper()} — the interval spans zero, "
        f"which is not support. This subset resolves |Δρ| of about {1.96 * d['bootstrap_sd']:.2f}; the "
        f"external reference implies about 0.03, so the design is underpowered for the question by "
        f"roughly fivefold.",
        f"Assay-to-assay ρ = {w.get('rho_between_assays', float('nan')):+.3f}: the model tracks each assay "
        f"about as closely as the two assays track each other. Function is measured downstream of surface "
        f"expression, so they are not independent readouts — though this ρ is lower than that alone implies.",
    ]
    y = strip_y + 44
    for i, line in enumerate(caption):
        cls = "caption-strong" if i >= 2 else "caption"
        for part in _wrap(line):
            body.append(f'<text x="{PAD_L}" y="{y}" class="{cls}">{_esc(part)}</text>')
            y += 17
        y += 3

    css = """
    .bg{fill:var(--bg)}
    .title{fill:var(--ink);font:600 17px system-ui,-apple-system,"Segoe UI",sans-serif}
    .subtitle{fill:var(--ink2);font:400 12.5px system-ui,-apple-system,"Segoe UI",sans-serif}
    .panel-title{fill:var(--ink);font:600 13.5px system-ui,-apple-system,"Segoe UI",sans-serif}
    .tick{fill:var(--ink2);font:400 11px system-ui,-apple-system,"Segoe UI",sans-serif}
    .tick-y{text-anchor:end} .tick-x{text-anchor:middle}
    .grid{stroke:var(--grid);stroke-width:1}
    .axis{stroke:var(--ink2);stroke-width:1;opacity:.55}
    .pt{fill-opacity:.62;stroke:var(--bg);stroke-width:1}
    .pt-surface{fill:var(--c-surface)} .pt-function{fill:var(--c-function)}
    .annot{fill:var(--ink2);font:400 11.5px system-ui,-apple-system,"Segoe UI",sans-serif}
    .annot-strong{fill:var(--ink);font:600 12.5px system-ui,-apple-system,"Segoe UI",sans-serif}
    .axis-label{fill:var(--ink2);font:400 12px system-ui,-apple-system,"Segoe UI",sans-serif;text-anchor:middle}
    .strip-label{fill:var(--ink2);font:400 11.5px system-ui,-apple-system,"Segoe UI",sans-serif}
    .plate{fill:var(--bg);fill-opacity:.82}
    .strip-bg{fill:var(--grid)} .strip-tick{fill:var(--ink2);opacity:.85}
    .caption{fill:var(--ink2);font:400 11.5px system-ui,-apple-system,"Segoe UI",sans-serif}
    .caption-strong{fill:var(--ink);font:600 11.5px system-ui,-apple-system,"Segoe UI",sans-serif}
    """
    light_vars = (f"--bg:{LIGHT['bg']};--ink:{LIGHT['ink']};--ink2:{LIGHT['ink2']};"
                  f"--grid:{LIGHT['grid']};--c-surface:{LIGHT['surface']};--c-function:{LIGHT['function']}")
    dark_vars = (f"--bg:{DARK['bg']};--ink:{DARK['ink']};--ink2:{DARK['ink2']};"
                 f"--grid:{DARK['grid']};--c-surface:{DARK['surface']};--c-function:{DARK['function']}")

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img"
     aria-label="ESM-2 masked-marginal scores against Kir2.1 surface expression and channel function">
<style>
svg{{{light_vars}}}
@media (prefers-color-scheme: dark){{svg{{{dark_vars}}}}}
{css}
</style>
<rect width="{W}" height="{H}" class="bg"/>
<text x="{PAD_L}" y="36" class="title">ESM-2 masked marginals against two Kir2.1 assays, on identical variants</text>
<text x="{PAD_L}" y="58" class="subtitle">Zero-shot prediction (x) versus measured outcome (y). ProteinGym v1.3, KCNJ2_MOUSE, Coyote-Maestas 2022.</text>
<text x="{PAD_L}" y="76" class="subtitle">A computational replication on public data. A prediction remains a prediction.</text>
{''.join(body)}
<text x="{PAD_L + (PANEL_W * 2 + GAP) / 2}" y="{PAD_T + PANEL_H + 48}" class="axis-label">ESM-2 masked-marginal score  (log p(mut) − log p(wt), higher = more tolerated)</text>
</svg>
"""
    with open(args.out, "w") as fh:
        fh.write(svg)
    print(f"wrote {args.out} ({len(svg)} bytes, {len(rows)} points)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
