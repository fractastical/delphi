#!/usr/bin/env python3
"""Test of wolfram2002-ch05-20: 56 allowed 3x3 templates (NKS p. 221) forcing a shifted rule-30 pattern.

Run: python3 analysis.py   (downloads fig-c.png to data/, writes derived/*.json|csv, prints measured block; ~1-2 min)
Needs numpy, scipy, requests and pillow (image reading).
"""
import csv
import datetime as dt
import hashlib
import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
FIG_URL = "https://www.wolframscience.com/nks/pages/p221--systems-based-on-constraints/fig-c.png"
W_MAX = 9          # pre-registered
W_SUPP = 11        # supplementary periods 10..11, reported only
WINDOW = 300


def fetch_figure():
    import requests
    os.makedirs(os.path.join(HERE, "data"), exist_ok=True)
    path = os.path.join(HERE, "data", "p221_fig-c.png")
    if not os.path.exists(path):
        r = requests.get(FIG_URL, headers={"User-Agent": "Mozilla/5.0 (delphi-claim-tests)"}, timeout=60)
        r.raise_for_status()
        with open(path, "wb") as f:
            f.write(r.content)
    data = open(path, "rb").read()
    return path, {"download_url": FIG_URL, "retrieved_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                  "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def extract_templates(path):
    """14 x 4 grid of template boxes; box borders at the pixel columns/rows found from the dark-pixel profile
    (vertical lines at x = 2, 58, 115, ... spaced 56.5 px; horizontal at y = 0, 56, 111, 167); each 3x3 cell is 14 px."""
    from PIL import Image
    im = np.array(Image.open(path).convert("L"))
    xs = [2, 58, 115, 171, 227, 283.5, 340, 396, 453, 509, 566, 622, 678, 735]
    ys = [0, 56, 111, 167]
    temps, ambiguous = [], 0
    for y0 in ys:
        for x0 in xs:
            t = np.zeros((3, 3), dtype=np.int64)
            for i in range(3):
                for j in range(3):
                    cy, cx = int(y0 + 15 + 14 * i), int(x0 + 15 + 14 * j)
                    frac = float((im[cy - 4:cy + 5, cx - 4:cx + 5] < 128).mean())
                    t[i, j] = 1 if frac > 0.5 else 0
                    if 0.15 < frac < 0.85:
                        ambiguous += 1
            temps.append(t)
    codes = [int("".join(str(v) for v in t.flatten()), 2) for t in temps]
    return temps, codes, ambiguous


def rule30(a, b, c):
    return (30 >> ((a << 2) | (b << 1) | c)) & 1


def candidate_pattern(n_rows=WINDOW, n_cols=WINDOW, margin=3):
    """Rows 0,1: band black for columns <= C+1; columns C, C+1 black for rows >= 0; interior shifted rule 30."""
    C = n_cols
    H = n_rows + margin
    Wd = n_cols + 2 + margin
    g = np.zeros((H, Wd), dtype=np.int64)
    r0 = margin  # row index of pattern row 0
    g[r0:r0 + 2, :C + 2] = 1
    g[r0:, C:C + 2] = 1
    for t in range(r0 + 2, H):
        prev = g[t - 1]
        # a(t, x) = rule30(prev[x], prev[x+1], prev[x+2]) for x <= C-1
        a, b, c = prev[0:C], prev[1:C + 1], prev[2:C + 2]
        g[t, :C] = (30 >> ((a << 2) | (b << 1) | c)) & 1
    return g, r0, C


def blocks_of(g):
    H, Wd = g.shape
    codes = np.zeros((H - 2, Wd - 2), dtype=np.int64)
    for i in range(3):
        for j in range(3):
            codes = codes * 2 + g[i:H - 2 + i, j:Wd - 2 + j]
    return codes


def periodic_search(allowed_codes, template1, w):
    """Transfer graph on pairs of rows of a width-w cylinder. Returns dict with cycle info."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    allowed = np.zeros(512, dtype=bool)
    allowed[list(allowed_codes)] = True
    n = 1 << w
    rows = np.arange(n)
    bits = ((rows[:, None] >> (w - 1 - np.arange(w))[None, :]) & 1)  # (n, w) bit j of each row, left to right
    # cyclic 3-windows for each row: code3[r, j] = 4*b[j-1] + 2*b[j] + b[j+1]
    code3 = 4 * np.roll(bits, 1, axis=1) + 2 * bits + np.roll(bits, -1, axis=1)  # (n, w)
    src, dst, has_t1 = [], [], []
    for r0 in range(n):
        for r1 in range(n):
            # candidate r2: all n; block codes (n, w)
            blk = (code3[r0][None, :] << 6) | (code3[r1][None, :] << 3) | code3
            ok = allowed[blk].all(axis=1)
            r2s = np.flatnonzero(ok)
            if r2s.size:
                src.append(np.full(r2s.size, r0 * n + r1))
                dst.append(r1 * n + r2s)
                has_t1.append((blk[r2s] == template1).any(axis=1))
    if not src:
        return {"w": w, "edges": 0, "cyclic_edges": 0, "cyclic_edges_with_template1": 0, "cyclic_components": 0}
    src = np.concatenate(src)
    dst = np.concatenate(dst)
    has_t1 = np.concatenate(has_t1)
    N = n * n
    A = coo_matrix((np.ones(src.size, dtype=np.int8), (src, dst)), shape=(N, N)).tocsr()
    ncomp, labels = connected_components(A, directed=True, connection="strong")
    comp_size = np.bincount(labels, minlength=ncomp)
    self_loop = src == dst
    in_cycle_edge = (labels[src] == labels[dst]) & ((comp_size[labels[src]] > 1) | self_loop)
    cyc_edges = int(in_cycle_edge.sum())
    cyc_t1 = int((in_cycle_edge & has_t1).sum())
    # describe cyclic patterns: the set of templates used on cyclic edges
    used = set()
    if cyc_edges:
        for s, d in zip(src[in_cycle_edge][:2000], dst[in_cycle_edge][:2000]):
            r0, r1, r2 = s // n, s % n, d % n
            blk = (code3[r0] << 6) | (code3[r1] << 3) | code3[r2]
            used |= set(int(x) for x in blk)
    comps_cyc = int((comp_size > 1).sum() + len(set(labels[src[self_loop]].tolist()) - set(np.flatnonzero(comp_size > 1).tolist())))
    return {"w": w, "edges": int(src.size), "cyclic_edges": cyc_edges, "cyclic_edges_with_template1": cyc_t1,
            "cyclic_components": comps_cyc, "templates_used_on_cycles": sorted(used)}


def main():
    t0 = time.time()
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    path, fig = fetch_figure()
    temps, codes, ambiguous = extract_templates(path)
    distinct = len(set(codes)) == 56
    decreasing = all(codes[i] > codes[i + 1] for i in range(len(codes) - 1))
    T_ok = distinct and decreasing
    allowed = set(codes)
    template1 = codes[0]
    with open(os.path.join(HERE, "derived", "templates.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["index", "code", "top", "middle", "bottom"])
        for i, (t, c) in enumerate(zip(temps, codes)):
            w.writerow([i + 1, c] + ["".join(str(v) for v in row) for row in t])

    # (A) candidate pattern
    g, r0, C = candidate_pattern()
    blk = blocks_of(g)
    occurring = set(int(x) for x in np.unique(blk))
    disallowed = sorted(occurring - allowed)
    missing = sorted(allowed - occurring)
    # locate disallowed blocks (if any) and classify as interior or boundary
    disallowed_detail = []
    for code in disallowed[:20]:
        ii, jj = np.argwhere(blk == code)[0]
        disallowed_detail.append({"code": code, "bits": format(code, "09b"), "row": int(ii - r0), "col_from_C": int(jj - C),
                                  "interior": bool(ii - r0 >= 2 and jj + 2 <= C - 1)})

    # (R) rule identification
    rule_ok, rule_fail = [], []
    for i, t in enumerate(temps):
        a = t[1][0] == rule30(*t[0]) and t[2][0] == rule30(*t[1])
        (rule_ok if a else rule_fail).append(i + 1)

    # (U) periodic search
    per = []
    for w in range(1, W_SUPP + 1):
        res = periodic_search(allowed, template1, w)
        res["preregistered"] = w <= W_MAX
        per.append(res)
        print(f"  w={w}: edges {res['edges']}, cyclic edges {res['cyclic_edges']}, with template 1: {res['cyclic_edges_with_template1']} ({time.time()-t0:.0f}s)", file=sys.stderr)
    with open(os.path.join(HERE, "derived", "periodic_search.json"), "w") as f:
        json.dump(per, f, indent=1)

    total_t1 = sum(r["cyclic_edges_with_template1"] for r in per if r["preregistered"])
    supp_t1 = sum(r["cyclic_edges_with_template1"] for r in per if not r["preregistered"])
    A_subset = len(disallowed) == 0
    A_all = len(missing) == 0
    passes = T_ok and A_subset and A_all and total_t1 == 0
    measured = {
        "value": total_t1,
        "unit": "number of cycle edges (doubly periodic valid patterns, periods 1-9) containing template 1; 0 = no periodic competitor",
        "n": sum(r["edges"] for r in per if r["preregistered"]),
        "uncertainty": None,
        "extra": {
            "T_templates_distinct": distinct, "T_templates_strictly_decreasing": decreasing, "T_ambiguous_cells": ambiguous,
            "template1_bits": format(template1, "09b"),
            "A_blocks_occurring_in_candidate": len(occurring), "A_disallowed_blocks": disallowed_detail, "A_missing_templates": missing,
            "A_subset_ok": A_subset, "A_all_templates_used": A_all,
            "R_templates_satisfying_shifted_rule30": len(rule_ok), "R_templates_not_satisfying": rule_fail,
            "U_per_period": [{k: v for k, v in r.items() if k != "templates_used_on_cycles"} for r in per],
            "U_templates_used_on_cycles_union": sorted(set().union(*[set(r.get("templates_used_on_cycles", [])) for r in per])),
            "passes_preregistered_criterion": passes,
            "U_supplementary_periods_10_11_cyclic_edges_with_template1": supp_t1,
            "figure_file": fig,
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    print(json.dumps(measured, indent=2, default=str))


if __name__ == "__main__":
    main()
