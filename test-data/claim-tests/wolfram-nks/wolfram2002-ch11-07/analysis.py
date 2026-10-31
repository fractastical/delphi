#!/usr/bin/env python3
"""Test of wolfram2002-ch11-07: cellular automata emulating mobile automata, Turing machines,
substitution systems, register machines and logic circuits, using the constructions published in
the NKS notes to 'Emulating Other Systems with Cellular Automata' (pp. 1111-1112).

Run: python3 analysis.py   (writes derived/*.csv|json, prints measured block; about 2-3 minutes)
"""
import csv
import itertools
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261034
ANY = "_"


# ----------------------------------------------------------------------------- Mathematica-style ordered pattern rules
# A pattern element is: an int (literal), a frozenset of ints (alternatives), ANY, or a str variable name.
# The RHS is an int or a function of the variable bindings. The first matching rule wins (as for a
# Mathematica rule list applied with Replace / in CellularAutomaton).
def compile_table(rules, k, r):
    """Return a lookup table of shape (k,)*(2r+1) giving the new colour for every neighbourhood."""
    width = 2 * r + 1
    table = np.full((k,) * width, -1, dtype=np.int64)
    for nb in itertools.product(range(k), repeat=width):
        for pat, rhs in rules:
            env = {}
            ok = True
            for p, v in zip(pat, nb):
                if p == ANY:
                    continue
                if isinstance(p, frozenset):
                    if v not in p:
                        ok = False
                        break
                elif isinstance(p, str):
                    if p in env and env[p] != v:
                        ok = False
                        break
                    env[p] = v
                elif p != v:
                    ok = False
                    break
            if ok:
                table[nb] = rhs(env) if callable(rhs) else rhs
                break
        if table[nb] < 0:
            raise ValueError(f"no rule matches {nb}")
    return table


def alt(*xs):
    return frozenset(xs)


def flat_index(cells, k, r):
    """cells: (..., W) int array; returns neighbourhood codes for interior cells, (..., W-2r)."""
    width = 2 * r + 1
    W = cells.shape[-1]
    idx = np.zeros(cells.shape[:-1] + (W - 2 * r,), dtype=np.int64)
    for j in range(width):
        idx = idx * k + cells[..., j:W - 2 * r + j]
    return idx


def ca_step(cells, flat_table, k, r):
    """Fixed boundary (outside cells are 0). cells: (..., W)."""
    out = np.zeros_like(cells)
    out[..., r:-r] = flat_table[flat_index(cells, k, r)]
    # boundary cells: pad with zeros and evaluate
    pad = np.zeros(cells.shape[:-1] + (r,), dtype=cells.dtype)
    ext = np.concatenate([pad, cells, pad], axis=-1)
    full = flat_table[flat_index(ext, k, r)]
    return full


def ca_step_multi(cells, flat_tables, k, r):
    """Many systems at once: cells (R, W), flat_tables (R, k**(2r+1))."""
    pad = np.zeros((cells.shape[0], r), dtype=cells.dtype)
    ext = np.concatenate([pad, cells, pad], axis=1)
    idx = flat_index(ext, k, r)
    return np.take_along_axis(flat_tables, idx, axis=1)


# ----------------------------------------------------------------------------- (1) mobile automata, MAToCA (NKS p. 1111)
TRIPLES = [(1, 1, 1), (1, 1, 0), (1, 0, 1), (1, 0, 0), (0, 1, 1), (0, 1, 0), (0, 0, 1), (0, 0, 0)]


def ma_rule(colour_num, disp_num):
    """NKS labelling {colours, displacements}: bit j of each number is the entry for TRIPLES[j]
    (most significant first); displacement bit 1 means -1 (left), 0 means +1 (right)."""
    cbits = [(colour_num >> (7 - j)) & 1 for j in range(8)]
    dbits = [(disp_num >> (7 - j)) & 1 for j in range(8)]
    return {t: (cbits[j], -1 if dbits[j] else 1) for j, t in enumerate(TRIPLES)}


def ma_to_ca(rule):
    rules = []
    for (a, b, c), (d, e) in rule.items():
        rules.append(((ANY, a, b + 2, c, ANY), d))
        if e == 1:
            rules.append(((a, b + 2, c, ANY, ANY), c + 2))
        else:
            rules.append(((ANY, ANY, a, b + 2, c), a + 2))
    rules.append(((ANY, ANY, "x", ANY, ANY), lambda env: env["x"]))
    return compile_table(rules, 4, 2)


def ma_tables_all():
    """Lookup tables for all 65536 mobile automata, vectorised: shape (65536, 1024)."""
    # neighbourhood (p, q, c, s, t) code = ((((p*4+q)*4+c)*4+s)*4+t
    nb = np.array(list(itertools.product(range(4), repeat=5)), dtype=np.int64)  # (1024, 5)
    p, q, c, s, t = nb.T
    cn = np.arange(256)
    cbits = (cn[:, None] >> (7 - np.arange(8))[None, :]) & 1  # (256, 8)
    tri_of = np.zeros((2, 2, 2), dtype=np.int64)
    for j, (a, b, c_) in enumerate(TRIPLES):
        tri_of[a, b, c_] = j
    tables = np.zeros((256, 256, 1024), dtype=np.int64)
    # default: keep centre colour
    tables[:, :, :] = c[None, None, :]
    # active cell at centre: (ANY, a, b+2, c, ANY) -> d  (a = q, c = s)
    centre_active = (c >= 2) & (q < 2) & (s < 2)
    j_centre = tri_of[np.clip(q, 0, 1), np.clip(c - 2, 0, 1), np.clip(s, 0, 1)]
    # right of active moving right: (a, b+2, c, _, _) -> c+2 where (a,b,c) = (p, q-2, c), c < 2
    right_active = (q >= 2) & (p < 2) & (c < 2)
    j_right = tri_of[np.clip(p, 0, 1), np.clip(q - 2, 0, 1), np.clip(c, 0, 1)]
    # left of active moving left: (_, _, a, b+2, c) -> a+2 where (a,b,c) = (c, s-2, t), c < 2
    left_active = (s >= 2) & (c < 2) & (t < 2)
    j_left = tri_of[np.clip(c, 0, 1), np.clip(s - 2, 0, 1), np.clip(t, 0, 1)]
    for dn in range(256):
        dbits = [(dn >> (7 - j)) & 1 for j in range(8)]
        move_right = np.array([0 if b else 1 for b in dbits], dtype=bool)  # per triple
        # Rules are ordered per triple (centre rule, then move rule); conflicts between different cells
        # cannot occur with a single active cell, so order between triples does not matter. Among the
        # three cases for one neighbourhood, the centre-active case is listed before move cases for the
        # same triple only; a neighbourhood with both centre and neighbour active never occurs in valid
        # configurations, but the table must still be total: apply in the order centre, right, left.
        for cn_ in range(256):
            row = tables[cn_, dn]
            row[:] = c
            m = left_active & (~move_right[j_left])
            row[m] = c[m] + 2
            m2 = right_active & move_right[j_right]
            row[m2] = c[m2] + 2
            row[centre_active] = cbits[cn_][j_centre[centre_active]]
    return tables.reshape(65536, 1024)


def ma_run_direct_all(rules_c, rules_d, init, pos, steps):
    """Vectorised direct mobile-automaton evolution for R rules. init (R, W), pos (R,)."""
    R, W = init.shape
    cells = init.copy()
    pos = pos.copy()
    hist = np.empty((steps + 1, R, W), dtype=np.int64)
    hist_pos = np.empty((steps + 1, R), dtype=np.int64)
    hist[0] = cells
    hist_pos[0] = pos
    tri_of = np.zeros((2, 2, 2), dtype=np.int64)
    for j, (a, b, c_) in enumerate(TRIPLES):
        tri_of[a, b, c_] = j
    cbits = (rules_c[:, None] >> (7 - np.arange(8))[None, :]) & 1  # (R, 8)
    dbits = (rules_d[:, None] >> (7 - np.arange(8))[None, :]) & 1
    rows = np.arange(R)
    for t in range(1, steps + 1):
        a = cells[rows, pos - 1]
        b = cells[rows, pos]
        c_ = cells[rows, pos + 1]
        j = tri_of[a, b, c_]
        cells[rows, pos] = cbits[rows, j]
        pos = pos + np.where(dbits[rows, j] == 1, -1, 1)
        hist[t] = cells
        hist_pos[t] = pos
    return hist, hist_pos


def test_mobile_automata(rng, steps=60, n_random_ic=1):
    t0 = time.time()
    tables = ma_tables_all()  # (65536, 1024)
    R = 65536
    W = 2 * steps + 9
    mid = W // 2
    rules_c = np.repeat(np.arange(256), 256)
    rules_d = np.tile(np.arange(256), 256)
    results = {}
    for ic_kind in ["blank"] + [f"random{i}" for i in range(n_random_ic)]:
        if ic_kind == "blank":
            init = np.zeros((R, W), dtype=np.int64)
        else:
            init = rng.integers(0, 2, (R, W)).astype(np.int64)
        pos = np.full(R, mid)
        hist, hist_pos = ma_run_direct_all(rules_c, rules_d, init, pos, steps)
        ca = init.copy()
        ca[np.arange(R), pos] += 2
        ok = np.ones(R, dtype=bool)
        for t in range(1, steps + 1):
            ca = ca_step_multi(ca, tables, 4, 2)
            # decode: colours mod 2 are the cells; the unique cell >= 2 is the active cell
            dec = ca % 2
            act = ca >= 2
            ok &= np.all(dec == hist[t], axis=1)
            ok &= act.sum(axis=1) == 1
            ok &= act[np.arange(R), hist_pos[t]]
        results[ic_kind] = {"n_rules": R, "n_exact": int(ok.sum()), "failures": [int(i) for i in np.flatnonzero(~ok)[:20]]}
        print(f"  MA {ic_kind}: {int(ok.sum())}/{R} exact ({time.time()-t0:.0f}s)", file=sys.stderr)
    results["steps"] = steps
    results["book_example_35_57_index"] = 35 * 256 + 57
    return results


# ----------------------------------------------------------------------------- (2) Turing machines, TMToCA (NKS p. 1111)
def tm_tables(s, k, rules_arr):
    """rules_arr: (R, s, k, 3) with entries (sp in 1..s, ap in 0..k-1, d in {-1,+1}). CA colours K = k(s+1), r = 1.
    Rule g: if d == 1: {k s + a, x_, _} -> k sp + x ; else {_, x_, k s + a} -> k sp + x ; and {_, k s + a, _} -> ap.
    Default {_, x_, _} -> x. Order: for each (s, a) the two rules, then default; conflicts between a cell being
    both 'under the head' and 'next to the head' cannot occur with one head."""
    K = k * (s + 1)
    nb = np.array(list(itertools.product(range(K), repeat=3)), dtype=np.int64)
    l, c, rr = nb.T
    R = rules_arr.shape[0]
    tables = np.tile(c, (R, 1))
    # cell left of head (head moving left onto it): {_, x_, k s + a} -> k sp + x
    for st in range(1, s + 1):
        for a in range(k):
            code = k * st + a
            sp, ap, d = rules_arr[:, st - 1, a, 0], rules_arr[:, st - 1, a, 1], rules_arr[:, st - 1, a, 2]
            m_left = (rr == code) & (c < k)
            m_right = (l == code) & (c < k)
            m_centre = (c == code)
            left_vals = (k * sp[:, None] + c[None, :])
            tables[:, m_left] = np.where((d == -1)[:, None], left_vals[:, m_left], tables[:, m_left])
            tables[:, m_right] = np.where((d == 1)[:, None], left_vals[:, m_right], tables[:, m_right])
            tables[:, m_centre] = ap[:, None]
    return tables, K


def tm_run_direct(s, k, rules_arr, init, pos, steps):
    R, W = init.shape
    cells = init.copy()
    pos = pos.copy()
    state = np.ones(R, dtype=np.int64)
    rows = np.arange(R)
    hist = np.empty((steps + 1, R, W), dtype=np.int64)
    hist_pos = np.empty((steps + 1, R), dtype=np.int64)
    hist_state = np.empty((steps + 1, R), dtype=np.int64)
    hist[0], hist_pos[0], hist_state[0] = cells, pos, state
    for t in range(1, steps + 1):
        a = cells[rows, pos]
        sp = rules_arr[rows, state - 1, a, 0]
        ap = rules_arr[rows, state - 1, a, 1]
        d = rules_arr[rows, state - 1, a, 2]
        cells[rows, pos] = ap
        pos = pos + d
        state = sp
        hist[t], hist_pos[t], hist_state[t] = cells, pos, state
    return hist, hist_pos, hist_state


def all_tm_rules(s, k):
    opts = [(sp, ap, d) for sp in range(1, s + 1) for ap in range(k) for d in (-1, 1)]
    combos = itertools.product(range(len(opts)), repeat=s * k)
    arr = np.array([[opts[i] for i in combo] for combo in combos], dtype=np.int64)
    return arr.reshape(-1, s, k, 3)


def random_tm_rules(s, k, n, rng):
    arr = np.empty((n, s, k, 3), dtype=np.int64)
    arr[..., 0] = rng.integers(1, s + 1, (n, s, k))
    arr[..., 1] = rng.integers(0, k, (n, s, k))
    arr[..., 2] = rng.choice([-1, 1], (n, s, k))
    return arr


def test_turing_machines(rng, steps=60):
    t0 = time.time()
    out = {}
    W = 2 * steps + 9
    mid = W // 2
    for (s, k, how) in [(2, 2, "all"), (3, 2, "sample4096"), (2, 3, "sample4096"), (4, 2, "sample4096"), (3, 3, "sample4096")]:
        rules_arr = all_tm_rules(s, k) if how == "all" else random_tm_rules(s, k, 4096, rng)
        R = rules_arr.shape[0]
        tables, K = tm_tables(s, k, rules_arr)
        res = {}
        for ic_kind in ["blank", "random"]:
            init = np.zeros((R, W), dtype=np.int64) if ic_kind == "blank" else rng.integers(0, k, (R, W)).astype(np.int64)
            pos = np.full(R, mid)
            hist, hist_pos, hist_state = tm_run_direct(s, k, rules_arr, init, pos, steps)
            ca = init.copy()
            ca[np.arange(R), pos] += k * 1  # state 1
            ok = np.ones(R, dtype=bool)
            for t in range(1, steps + 1):
                ca = ca_step_multi(ca, tables, K, 1)
                dec = ca % k
                head = ca >= k
                ok &= np.all(dec == hist[t], axis=1)
                ok &= head.sum(axis=1) == 1
                ok &= head[np.arange(R), hist_pos[t]]
                ok &= (ca[np.arange(R), hist_pos[t]] // k) == hist_state[t]
            res[ic_kind] = {"n_rules": R, "n_exact": int(ok.sum()), "failures": int((~ok).sum())}
        res["colours"] = K
        out[f"s{s}k{k}_{how}"] = res
        print(f"  TM s={s} k={k} {how}: {res['blank']['n_exact']}/{R} blank, {res['random']['n_exact']}/{R} random ({time.time()-t0:.0f}s)", file=sys.stderr)
    out["steps"] = steps
    return out


# ----------------------------------------------------------------------------- (3) substitution systems, SSToCA (NKS p. 1111)
SS_CODES = {"b": 0, ("s", 0): 1, ("m", 0): 2, ("p", 0, 0): 3, ("r", 0): 4, ("p", 0, 1): 5, ("p", 1, 0): 6, ("r", 1): 7,
            ("p", 1, 1): 8, ("m", 1): 9, ("m", "b"): 10, ("s", 1): 11}
SS_BLOCKS = [(0,), (1,), (0, 0), (0, 1), (1, 0), (1, 1)]


def ss_to_ca(rule):
    """rule: dict {0: block, 1: block} with blocks of length 1 or 2."""
    C = SS_CODES
    S = lambda v: C[("s", v)]
    M = lambda v: C[("m", v)]
    P = lambda x, y: C[("p", x, y)]
    Rr = lambda v: C[("r", v)]
    b = C["b"]
    s_any = alt(S(0), S(1))
    m_any = alt(M(0), M(1), C[("m", "b")])
    p_any = alt(P(0, 0), P(0, 1), P(1, 0), P(1, 1))
    r_any = alt(Rr(0), Rr(1))
    p_first = {P(x, y): x for x in (0, 1) for y in (0, 1)}
    p_second = {P(x, y): y for x in (0, 1) for y in (0, 1)}
    s_val = {S(0): 0, S(1): 1}
    m_val = {M(0): 0, M(1): 1}
    r_val = {Rr(0): 0, Rr(1): 1}

    def replace(v):
        blk = rule[v]
        return S(blk[0]) if len(blk) == 1 else P(blk[0], blk[1])

    rules = []
    # {b, b, p[x_, _]} -> s[x]
    for pc in p_any:
        rules.append(((b, b, pc), S(p_first[pc])))
    # {_, s[v], p[x_, _]} -> p[v, x]
    for sc in s_any:
        for pc in p_any:
            rules.append(((ANY, sc, pc), P(s_val[sc], p_first[pc])))
    # {_, p[_, y_], _} -> s[y]
    for pc in p_any:
        rules.append(((ANY, pc, ANY), S(p_second[pc])))
    # {_, s[v], _m} -> m[v]
    for sc in s_any:
        rules.append(((ANY, sc, m_any), M(s_val[sc])))
    # {s[0|1], m[v], _} -> s[v]
    for mc in (M(0), M(1)):
        rules.append(((s_any, mc, ANY), S(m_val[mc])))
    # {b, m[v], _} -> r[v]
    for mc in (M(0), M(1)):
        rules.append(((b, mc, ANY), Rr(m_val[mc])))
    # {_, r[v], _} -> replacement
    for rc in r_any:
        rules.append(((ANY, rc, ANY), replace(r_val[rc])))
    # {_r, s[v], _} -> r[v]
    for sc in s_any:
        rules.append(((r_any, sc, ANY), Rr(s_val[sc])))
    # {_r, b, _} -> m[b]
    rules.append(((r_any, b, ANY), C[("m", "b")]))
    # {s[0|1], m[b], _} -> b
    rules.append(((s_any, C[("m", "b")], ANY), b))
    # {_, v_, _} -> v
    rules.append(((ANY, "v", ANY), lambda e: e["v"]))
    return compile_table(rules, 12, 1)


def ss_decode_snapshot(cells, sweep_start_only=True):
    """Decode the string at the start of a replacement sweep. Pre-registered operationalisation: exactly one r cell and
    no p or m[0|1] cells. That also matches mid-sweep configurations (the r cell moves right one cell per step and
    leaves s cells behind it), so the corrected version additionally requires the r cell to be the leftmost
    non-background cell; see result.json. Returns the decoded list of 0/1 or None."""
    C = SS_CODES
    nz = cells[cells != 0]
    r_cells = np.isin(nz, [C[("r", 0)], C[("r", 1)]])
    if r_cells.sum() != 1:
        return None
    if np.isin(nz, [C[("p", 0, 0)], C[("p", 0, 1)], C[("p", 1, 0)], C[("p", 1, 1)], C[("m", 0)], C[("m", 1)]]).any():
        return None
    if sweep_start_only and not r_cells[0]:
        return None
    val = {C[("s", 0)]: 0, C[("s", 1)]: 1, C[("r", 0)]: 0, C[("r", 1)]: 1}
    out = []
    for x in nz:
        if int(x) == C[("m", "b")]:
            continue
        out.append(val[int(x)])
    return out


def ss_direct(rule, init, t):
    seq = [list(init)]
    for _ in range(t):
        seq.append([y for x in seq[-1] for y in rule[x]])
    return seq


def test_substitution_systems(t_ss=7, max_ca_steps=3000):
    """Returns rows, n_exact (corrected decoder), n_exact_preregistered_decoder."""
    t0 = time.time()
    rows = []
    n_ok = n_ok_pre = 0
    for b0 in SS_BLOCKS:
        for b1 in SS_BLOCKS:
            rule = {0: b0, 1: b1}
            table = ss_to_ca(rule).reshape(-1)
            for init in (0, 1):
                target = ss_direct(rule, [init], t_ss)
                res = {}
                for variant in ("preregistered", "corrected"):
                    W = 2 * len(target[-1]) + 20
                    cells = np.zeros(W, dtype=np.int64)
                    cells[W - 10] = SS_CODES[("m", init)]
                    snaps = []
                    last = None
                    for step in range(max_ca_steps):
                        cells = ca_step_multi(cells[None, :], table[None, :], 12, 1)[0]
                        if cells[0] != 0 or cells[-1] != 0:
                            break
                        if variant == "preregistered":
                            d = ss_decode_snapshot(cells, sweep_start_only=False)
                            if d is not None and d != last:  # the pre-registered run also dropped repeated strings
                                snaps.append(d)
                                last = d
                        else:
                            d = ss_decode_snapshot(cells, sweep_start_only=True)
                            if d is not None:
                                snaps.append(d)
                        if len(snaps) == t_ss + 1:
                            break
                    res[variant] = (snaps == target, step + 1, len(snaps))
                ok = res["corrected"][0]
                n_ok += ok
                n_ok_pre += res["preregistered"][0]
                rows.append({"rule": f"0->{list(b0)} 1->{list(b1)}", "init": init, "final_length": len(target[-1]),
                             "ca_steps": res["corrected"][1], "n_snapshots": res["corrected"][2], "exact": ok,
                             "exact_preregistered_decoder": res["preregistered"][0]})
    print(f"  SS: corrected decoder {n_ok}/{len(rows)}, pre-registered decoder {n_ok_pre}/{len(rows)} exact ({time.time()-t0:.0f}s)", file=sys.stderr)
    return rows, n_ok, n_ok_pre


# ----------------------------------------------------------------------------- (4) register machines, RMToCA (NKS p. 1112)
def rm_to_ca(prog, repaired=False):
    """RMToCA from NKS p. 1112. With repaired=True, an increment that fires while the adjacent register cell is a
    decrement signal at the end of the register (register value 0 with the deletion still pending) writes a plain
    register cell instead of an increment signal; see result.json for the trace that motivated this."""
    m = len(prog)
    K = m + 7
    rules = []
    for idx, ins in enumerate(prog):
        p = idx + 1
        if ins == ("i", 1):
            rules += [((ANY, p, ANY), p + 1), ((ANY, 0, p), m + 2)]
            if repaired:
                rules += [((0, m + 1, p), m + 2)]
            rules += [((ANY, ANY, p), m + 3)]
        elif ins == ("i", 2):
            rules += [((ANY, p, ANY), p + 1), ((p, 0, ANY), m + 5)]
            if repaired:
                rules += [((p, m + 4, 0), m + 5)]
            rules += [((p, ANY, ANY), m + 6)]
        elif ins[0] == "d" and ins[1] == 1:
            q = ins[2]
            rules += [((alt(m + 2, m + 3), p, ANY), q), ((m + 1, p, ANY), p), ((0, p, ANY), p + 1), ((ANY, alt(m + 2, m + 3), p), m + 1)]
        else:
            q = ins[2]
            rules += [((ANY, p, alt(m + 5, m + 6)), q), ((ANY, p, m + 4), p), ((ANY, p, 0), p + 1), ((p, alt(m + 5, m + 6), ANY), m + 4)]
    rules += [((0, alt(0, m + 1), m + 3), m + 2), ((0, m + 1, ANY), 0), ((0, 0, m + 1), 0)]
    # {_, _, x:(m+1|m+3)} -> x
    rules.append(((ANY, ANY, m + 1), m + 1))
    rules.append(((ANY, ANY, m + 3), m + 3))
    rules.append(((ANY, alt(m + 1, m + 3), ANY), m + 2))
    rules.append(((m + 6, alt(0, m + 4), 0), m + 5))
    rules.append(((ANY, m + 4, 0), 0))
    rules.append(((m + 4, 0, 0), 0))
    rules.append(((m + 4, ANY, ANY), m + 4))
    rules.append(((m + 6, ANY, ANY), m + 6))
    rules.append(((ANY, alt(m + 4, m + 6), ANY), m + 5))
    rules.append(((ANY, "x", ANY), lambda e: e["x"]))
    return compile_table(rules, K, 1), K


def rm_direct(prog, a, b, steps):
    m = len(prog)
    n, regs = 1, [a, b]
    traj = [(n, regs[0], regs[1])]
    for _ in range(steps):
        if n > m:
            break
        ins = prog[n - 1]
        if ins[0] == "i":
            regs[ins[1] - 1] += 1
            n += 1
        else:
            r, q = ins[1], ins[2]
            if regs[r - 1] > 0:
                regs[r - 1] -= 1
                n = q
            else:
                n += 1
        traj.append((n, regs[0], regs[1]))
    return traj


def rm_decode(cells, m):
    pc = cells[(cells >= 1) & (cells <= m)]
    if pc.size != 1:
        return None
    r1 = int((cells == m + 2).sum() + 2 * (cells == m + 3).sum())
    r2 = int((cells == m + 5).sum() + 2 * (cells == m + 6).sum())
    return (int(pc[0]), r1, r2)


def random_program(m, rng):
    prog = []
    for _ in range(m):
        kind = rng.integers(0, 2)
        reg = int(rng.integers(1, 3))
        if kind == 0:
            prog.append(("i", reg))
        else:
            prog.append(("d", reg, int(rng.integers(1, m + 1))))
    return prog


def test_register_machines(rng, n_programs=300, rm_steps=40):
    t0 = time.time()
    rows = []
    n_ok = n_tested = 0
    n_ok_rep = 0
    attempts = 0
    while n_tested < n_programs and attempts < 20 * n_programs:
        attempts += 1
        m = int(rng.integers(2, 7))
        prog = random_program(m, rng)
        a, b = int(rng.integers(0, 4)), int(rng.integers(0, 4))
        traj = rm_direct(prog, a, b, rm_steps)
        if traj[-1][0] > m:  # halts (pc past the end) within the horizon: the CA has no colour for pc = m + 1
            traj = traj[:-1]
        if len(traj) < 20:
            continue
        res = {}
        for variant in ("published", "repaired"):
            table, K = rm_to_ca(prog, repaired=(variant == "repaired"))
            flat = table.reshape(-1)
            rmax = max(max(s[1], s[2]) for s in traj) + 4
            W = 2 * rmax + 2 * len(traj) + 10
            cells = np.zeros(W, dtype=np.int64)
            mid = W // 2
            cells[mid - a:mid] = m + 2
            cells[mid] = 1
            cells[mid + 1:mid + 1 + b] = m + 5
            decoded = [rm_decode(cells, m)]
            ca_steps = 0
            bad = False
            for step in range(6 * len(traj) * (rmax + 2)):
                cells = ca_step_multi(cells[None, :], flat[None, :], K, 1)[0]
                ca_steps += 1
                d = rm_decode(cells, m)
                if d is None:
                    bad = True
                    break
                if d != decoded[-1]:
                    decoded.append(d)
                    if len(decoded) >= len(traj):
                        break
            ok = (not bad) and decoded[:len(traj)] == traj
            res[variant] = (ok, ca_steps, next((i for i, (x, y) in enumerate(zip(decoded, traj)) if x != y), None) if not ok else None)
        n_ok += res["published"][0]
        n_ok_rep += res["repaired"][0]
        n_tested += 1
        rows.append({"program": " ".join("i%d" % i[1] if i[0] == "i" else "d%d,%d" % (i[1], i[2]) for i in prog), "a": a, "b": b,
                     "rm_steps_compared": len(traj) - 1, "ca_steps_published": res["published"][1],
                     "exact_published": res["published"][0], "first_mismatch_published": res["published"][2],
                     "ca_steps_repaired": res["repaired"][1], "exact_repaired": res["repaired"][0],
                     "first_mismatch_repaired": res["repaired"][2]})
    print(f"  RM: published {n_ok}/{n_tested}, repaired {n_ok_rep}/{n_tested} exact ({time.time()-t0:.0f}s)", file=sys.stderr)
    return rows, n_ok, n_ok_rep, n_tested


# ----------------------------------------------------------------------------- (5) logic circuits (NKS p. 1112)
LOGIC_RULES = [
    ((0, 1, alt(1, 3)), 1), ((0, 3, 3), 3), ((1, 0, alt(0, 1, 3)), 1), ((1, 1, 3), 4), ((1, 3, 0), 3), ((1, 3, 3), 2),
    ((2, 1, 3), 3), ((2, 3, 0), 2), ((2, 0, ANY), 4), ((3, 3, 0), 3), ((4, 0, alt(0, 1, 2, 4)), 2), ((4, 3, 3), 3),
    ((4, 1, 3), 1), ((4, 3, 0), 4), ((ANY, ANY, ANY), 0),
]


def logic_encode(expr):
    """expr: nested tuples ('and', x, y, ...), ('or', ...), ('not', x), or 0/1. Returns the NKS initial list."""
    if expr in (0, 1):
        return [0, 2 * (expr + 1)]
    op = expr[0]
    inner = [v for sub in expr[1:] for v in logic_encode(sub)]
    if op == "not":
        return [0] + inner + [0]
    if op == "and":
        return [0, 0, 1, 0] + inner + [1, 3, 0, 0]
    if op == "or":
        return [0, 0, 1, 0] + inner + [0, 1, 3, 0]
    raise ValueError(op)


def logic_eval(expr):
    if expr in (0, 1):
        return expr
    op = expr[0]
    vals = [logic_eval(s) for s in expr[1:]]
    if op == "not":
        return 1 - vals[0]
    if op == "and":
        return int(all(vals))
    return int(any(vals))


def random_expr(rng, depth):
    if depth == 0 or rng.random() < 0.25:
        return int(rng.integers(0, 2))
    op = ["and", "or", "not"][int(rng.integers(0, 3))]
    if op == "not":
        return ("not", random_expr(rng, depth - 1))
    n = int(rng.integers(2, 4))
    return (op,) + tuple(random_expr(rng, depth - 1) for _ in range(n))


def logic_run(expr, table):
    lst = logic_encode(expr)
    stripped = lst[:]
    while stripped and stripped[0] == 0:
        stripped.pop(0)
    steps = len(stripped) - 1
    W = len(lst) + 2 * steps + 4
    cells = np.zeros(W, dtype=np.int64)
    off = steps + 2
    cells[off:off + len(lst)] = lst
    flat = table.reshape(-1)
    for _ in range(steps):
        cells = ca_step_multi(cells[None, :], flat[None, :], 5, 1)[0]
    return cells, steps


def test_logic_circuits(rng, n_expr=400, depth=4):
    t0 = time.time()
    table = compile_table(LOGIC_RULES, 5, 1)
    rows = []
    n_ok = 0
    for i in range(n_expr):
        expr = random_expr(rng, depth)
        if expr in (0, 1):
            expr = ("not", expr)
        truth = logic_eval(expr)
        cells, steps = logic_run(expr, table)
        nz = cells[cells != 0]
        ok = nz.size == 1 and int(nz[0]) == 2 * (truth + 1)
        n_ok += ok
        rows.append({"expr": repr(expr), "truth": truth, "steps": steps, "final_nonzero": " ".join(str(int(x)) for x in nz), "exact": bool(ok)})
    print(f"  Logic: {n_ok}/{n_expr} exact ({time.time()-t0:.0f}s)", file=sys.stderr)
    return rows, n_ok


# ----------------------------------------------------------------------------- main
def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)

    ma = test_mobile_automata(rng)
    tm = test_turing_machines(rng)
    ss_rows, ss_ok, ss_ok_pre = test_substitution_systems()
    rm_rows, rm_ok, rm_ok_rep, rm_n = test_register_machines(rng)
    lg_rows, lg_ok = test_logic_circuits(rng)

    for name, rows in [("substitution_systems", ss_rows), ("register_machines", rm_rows), ("logic_circuits", lg_rows)]:
        with open(os.path.join(HERE, "derived", f"{name}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)

    families = {
        "mobile_automata": {"n": ma["blank"]["n_rules"] * 2, "exact": ma["blank"]["n_exact"] + ma["random0"]["n_exact"]},
        "turing_machines": {"n": sum(v["blank"]["n_rules"] * 2 for k_, v in tm.items() if k_ != "steps"),
                            "exact": sum(v["blank"]["n_exact"] + v["random"]["n_exact"] for k_, v in tm.items() if k_ != "steps")},
        "substitution_systems": {"n": len(ss_rows), "exact": int(ss_ok), "exact_preregistered_decoder": int(ss_ok_pre)},
        "register_machines": {"n": rm_n, "exact": int(rm_ok_rep), "exact_published_construction": int(rm_ok),
                              "exact_repaired_construction": int(rm_ok_rep)},
        "logic_circuits": {"n": len(lg_rows), "exact": int(lg_ok)},
    }
    for v in families.values():
        v["fraction"] = round(v["exact"] / v["n"], 5) if v["n"] else None
    n_families_perfect = sum(1 for v in families.values() if v["n"] and v["exact"] == v["n"])
    measured = {
        "value": n_families_perfect,
        "unit": "number of the 5 tested system types for which every tested instance is emulated exactly (published construction; repaired RM construction; corrected SS decoder)",
        "n": sum(v["n"] for v in families.values()),
        "uncertainty": None,
        "extra": {
            "families": families,
            "mobile_automata_detail": ma,
            "turing_machines_detail": tm,
            "runtime_s": round(time.time() - t0, 1),
        },
    }
    with open(os.path.join(HERE, "derived", "summary.json"), "w") as f:
        json.dump(measured, f, indent=1, default=str)
    print(json.dumps(measured, indent=2, default=str))


if __name__ == "__main__":
    main()
