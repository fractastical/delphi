#!/usr/bin/env python3
"""Test of wolfram2002-ch11-32: S/K combinators - exponential growth, size-8 census, rule-110 emulation.

Evaluation step = one Mathematica-style ReplaceAll pass of
    crules = {s[x_][y_][z_] -> x[z][y[z]], k[x_][y_] -> x}
(whole expression tried first; if no rule matches, head and argument are visited; replaced
parts are not re-scanned).  Full normalisation (//.) = iterate passes to a fixed point.

Terms are hash-consed DAG nodes, so identical subterms are shared and each pass is memoised
per node; LeafCount is the size of the unfolded tree.

Run: python3 analysis.py   (writes derived/census.json, prints measured block)
"""
import itertools
import json
import os
import sys
import time

import numpy as np

sys.setrecursionlimit(1_000_000)
HERE = os.path.dirname(os.path.abspath(__file__))

# ----------------------------------------------------------------------------- terms
_intern = {}


class Node:
    __slots__ = ("sym", "f", "a", "size", "depth")

    def __init__(self, sym, f, a):
        self.sym, self.f, self.a = sym, f, a
        if sym is not None:
            self.size, self.depth = 1, 0
        else:
            self.size = f.size + a.size
            self.depth = 1 + max(f.depth, a.depth)

    def __repr__(self):
        return to_str(self)


def leaf(sym):
    key = ("L", sym)
    n = _intern.get(key)
    if n is None:
        n = _intern[key] = Node(sym, None, None)
    return n


def app(f, a):
    key = (id(f), id(a))
    n = _intern.get(key)
    if n is None:
        n = _intern[key] = Node(None, f, a)
    return n


def apply_all(f, *args):
    for a in args:
        f = app(f, a)
    return f


S, K = leaf("s"), leaf("k")


def to_str(e):
    if e.sym is not None:
        return e.sym
    # print curried applications as h[a][b]...
    args = []
    while e.sym is None:
        args.append(e.a)
        e = e.f
    return e.sym + "".join("[" + to_str(a) + "]" for a in reversed(args))


def free_in(e, v, memo=None):
    if memo is None:
        memo = {}
    r = memo.get(e)
    if r is not None:
        return r
    if e.sym is not None:
        r = e is v
    else:
        r = free_in(e.f, v, memo) or free_in(e.a, v, memo)
    memo[e] = r
    return r


# ----------------------------------------------------------------------------- rewriting
def try_rules(e):
    if e.sym is not None:
        return None
    # k[x][y] -> x
    if e.f.sym is None and e.f.f is K:
        return e.f.a
    # s[x][y][z] -> x[z][y[z]]
    if e.f.sym is None and e.f.f.sym is None and e.f.f.f is S:
        x, y, z = e.f.f.a, e.f.a, e.a
        return app(app(x, z), app(y, z))
    return None


def replace_all(e, memo):
    r = memo.get(e)
    if r is not None:
        return r
    r = try_rules(e)
    if r is None:
        if e.sym is None:
            r = app(replace_all(e.f, memo), replace_all(e.a, memo))
        else:
            r = e
    memo[e] = r
    return r


def step(e):
    return replace_all(e, {})


def normalize(e, max_passes=200_000):
    for i in range(max_passes):
        n = step(e)
        if n is e:
            return e, i
        e = n
    raise RuntimeError("normalisation did not terminate within max_passes")


# ----------------------------------------------------------------------------- bracket abstraction (ToC)
ID = app(app(S, K), K)


def rm(e, v):
    if e is v:
        return ID
    if e.sym is None and e.a is v and not free_in(e.f, v):
        return e.f
    if not free_in(e, v):
        return app(K, e)
    return app(app(S, rm(e.f, v)), rm(e.a, v))


def ToC(e, vars_):
    for v in reversed(vars_):
        e = rm(e, v)
    return e


def cr(e, vars_):
    return ToC(normalize(e)[0], vars_)


# ----------------------------------------------------------------------------- Mathematica-syntax mini-parser
def parse(text, env):
    """Parse expressions like  s[s[s]][s][s][s][s]  or  cr[p[...][...], {x}]  into Nodes.
    env maps symbol names to Nodes; special heads: cr (abstraction), num (Church numeral)."""
    pos = 0
    text = text.replace(" ", "").replace("\n", "")

    def peek():
        return text[pos] if pos < len(text) else ""

    def parse_primary():
        nonlocal pos
        start = pos
        while pos < len(text) and (text[pos].isalnum() or text[pos] == "_"):
            pos += 1
        name = text[start:pos]
        if not name:
            raise ValueError(f"parse error at {pos}: {text[pos:pos+20]}")
        head = None
        args_special = None
        if name in ("cr", "num"):
            # special forms: cr[expr, {vars}] / num[n]
            assert peek() == "["
            pos += 1
            if name == "num":
                nstart = pos
                while text[pos].isdigit():
                    pos += 1
                n = int(text[nstart:pos])
                assert text[pos] == "]"
                pos += 1
                head = env["num"](n)
            else:
                body = parse_expr()
                assert text[pos] == ","
                pos += 1
                assert text[pos] == "{"
                pos += 1
                vs = []
                while True:
                    vstart = pos
                    while text[pos].isalnum():
                        pos += 1
                    vs.append(env[text[vstart:pos]])
                    if text[pos] == ",":
                        pos += 1
                        continue
                    assert text[pos] == "}"
                    pos += 1
                    break
                assert text[pos] == "]"
                pos += 1
                head = cr(body, vs)
        else:
            head = env[name]
        # applications
        while peek() == "[":
            pos += 1
            arg = parse_expr()
            assert text[pos] == "]", f"expected ] at {pos}"
            pos += 1
            head = app(head, arg)
        return head

    def parse_expr():
        return parse_primary()

    result = parse_expr()
    assert pos == len(text), f"trailing input at {pos}: {text[pos:]}"
    return result


# ----------------------------------------------------------------------------- constructions from NKS p. 1121-1123
X, Y, Z = leaf("x"), leaf("y"), leaf("z")
BASE_ENV = {"s": S, "k": K, "x": X, "y": Y, "z": Z}

P = normalize(ToC(parse("z[y][x]", BASE_ENV), [X, Y, Z]))[0]          # pairing: p[x][y][z] -> z[y][x]
INC = parse("s[s[k[s]][k]]", BASE_ENV)                                  # Church successor
ZERO = parse("s[k]", BASE_ENV)


def num(n):
    e = ZERO
    for _ in range(n):
        e = app(INC, e)
    return e


ENV = dict(BASE_ENV, p=P, inc=INC, num=num)


def make_f(rule):
    digits = [(rule >> (7 - i)) & 1 for i in range(8)]  # IntegerDigits[rule, 2, 8]
    d = [ZERO if b else K for b in digits]               # 1 -> s[k], 0 -> k
    e = apply_all(P, apply_all(P, apply_all(P, d[0], d[1]), apply_all(P, d[2], d[3])),
                  apply_all(P, apply_all(P, d[4], d[5]), apply_all(P, d[6], d[7])))
    return normalize(e)[0]


W_TEXT = ("cr[p[inc[inc[x[s[k]]]]][inc[x[s[k]]][cr[p[y[s[k]][k]][p[y[s[k]][s[k]]][y[k]]],{y}]]"
          "[p[x[s[k]][cr[p[p[f[y[k][k][k][s[k]]][y[k][k][s[k]]][y[k][s[k]]]][y[s[k]]]][y[k][k]],{y}]]"
          "[p[p[k][k]][p[k][x[k]]]][s[k]]][p[k][p[k][k]]]][k]],{x}]")


def encode(cells):
    data = apply_all(P, K, K)
    for c in cells:
        data = apply_all(P, ZERO if c else K, data)
    return normalize(apply_all(P, num(len(cells)), data))[0]


PKK = normalize(apply_all(P, K, K))[0]


def decode(state, expected_len):
    length_term = normalize(app(state, ZERO))[0]
    data = normalize(app(state, K))[0]
    cells = []
    while data is not PKK and len(cells) <= expected_len + 2:
        head = normalize(app(data, ZERO))[0]
        if head is ZERO:
            cells.append(1)
        elif head is K:
            cells.append(0)
        else:
            return None, length_term
        data = normalize(app(data, K))[0]
    return list(reversed(cells)), length_term


def eca_step(cells, rule, pad=1):
    padded = [0] * pad + list(cells) + [0] * pad
    out = []
    for i in range(len(padded)):
        l = padded[i - 1] if i > 0 else 0
        c = padded[i]
        r = padded[i + 1] if i + 1 < len(padded) else 0
        out.append((rule >> ((l << 2) | (c << 1) | r)) & 1)
    return out


def eca_step_n(cells, rule, t):
    for _ in range(t):
        cells = eca_step(cells, rule)
    return cells


# ----------------------------------------------------------------------------- census helpers
def trees(n):
    """All binary application trees with n leaves (leaves unlabeled -> yield shape builders)."""
    if n == 1:
        yield "L"
        return
    for i in range(1, n):
        for l in trees(i):
            for r in trees(n - i):
                yield (l, r)


def build(shape, labels, it=None):
    if it is None:
        it = iter(labels)
    if shape == "L":
        return S if next(it) else K
    return app(build(shape[0], None, it), build(shape[1], None, it))


def main():
    t0 = time.time()
    out = {}

    # (A) growth of s[s[s]][s][s][s][s]
    e = parse("s[s[s]][s][s][s][s]", BASE_ENV)
    sizes = [e.size]
    fixed = None
    for t in range(1, 41):
        n = step(e)
        if n is e:
            fixed = t
            break
        e = n
        sizes.append(e.size)
    ts = np.arange(10, 41)
    slope, intercept = np.polyfit(ts, np.log2(np.array(sizes[10:41], dtype=float)), 1)
    pred = intercept + slope * ts
    ss_res = float(np.sum((np.log2(np.array(sizes[10:41], dtype=float)) - pred) ** 2))
    ss_tot = float(np.sum((np.log2(np.array(sizes[10:41], dtype=float)) - np.mean(np.log2(np.array(sizes[10:41], dtype=float)))) ** 2))
    r2 = 1 - ss_res / ss_tot
    out["A"] = {"sizes": sizes, "fixed_point_step": fixed, "slope_log2_per_step": round(float(slope), 4),
                "r2": round(float(r2), 5), "size_at_40": sizes[40] if len(sizes) > 40 else None,
                "pass": fixed is None and 0.45 <= slope <= 0.55 and r2 >= 0.99}
    print(f"A: fixed={fixed} slope={slope:.4f} r2={r2:.5f} size40={out['A']['size_at_40']}", file=sys.stderr)

    # (C) rule 110 emulation
    f110 = make_f(110)
    env = dict(ENV, f=f110)
    w = parse(W_TEXT, env)
    out["C"] = {"w_size": w.size, "f_size": f110.size, "p_size": P.size, "cases": 0, "mismatches": [], "passes_per_step": {}}
    n_cases = 0
    n_ok = 0
    per_t = {1: [0, 0], 2: [0, 0], 3: [0, 0]}
    for n in (3, 4, 5):
        for cells in itertools.product((0, 1), repeat=n):
            cells = list(cells)
            state = encode(cells)
            expected = cells
            for t in (1, 2, 3):
                state = normalize(app(w, state))[0]
                expected = eca_step(expected, 110)
                decoded, length_term = decode(state, len(expected))
                ok = decoded == expected and length_term is normalize(num(len(expected)))[0]
                n_cases += 1
                per_t[t][1] += 1
                if ok:
                    n_ok += 1
                    per_t[t][0] += 1
                elif len(out["C"]["mismatches"]) < 10:
                    out["C"]["mismatches"].append({"init": cells, "t": t, "expected": expected, "decoded": decoded})
        print(f"C: n={n} done, ok {n_ok}/{n_cases} ({time.time()-t0:.0f}s)", file=sys.stderr)
    out["C"]["cases"] = n_cases
    out["C"]["ok"] = n_ok
    out["C"]["passes_per_step"] = {str(t): f"{a}/{b}" for t, (a, b) in per_t.items()}
    out["C"]["pass"] = n_ok == n_cases
    # Post-hoc diagnosis (not part of the pre-registered decision): does w implement
    # 'evolve the n cells with zero boundaries, then pad a 0 on each side'?  That differs from
    # evolving the zero-padded list only in the leftmost cell, and only when the list starts with 1.
    alt_ok = 0
    lead0_ok = lead0_cases = 0
    for n in (3, 4, 5):
        for cells in itertools.product((0, 1), repeat=n):
            cells = list(cells)
            state = encode(cells)
            alt = cells
            for t in (1, 2, 3):
                state = normalize(app(w, state))[0]
                alt = [0] + eca_step(alt, 110, pad=0) + [0]
                decoded, _ = decode(state, len(alt))
                alt_ok += decoded == alt
                if cells[0] == 0:
                    lead0_cases += 1
                    lead0_ok += decoded == eca_step_n(cells, 110, t)
    out["C"]["alt_convention_evolve_then_pad_ok"] = f"{alt_ok}/{n_cases}"
    out["C"]["leading_zero_lists_exact"] = f"{lead0_ok}/{lead0_cases}"

    # Validation of the rewrite semantics against the book's published size-7 counts
    # (note 'Combinator properties': all but 2 of 16,896 size-7 expressions reach fixed points
    # in at most 12 steps; the largest fixed point has size 41).
    v = {"fixed_point": 0, "not_fixed_60": 0, "max_steps_to_fixed": 0, "largest_fixed_point": 0, "total": 0}
    for shape in trees(7):
        for labels in itertools.product((0, 1), repeat=7):
            e = build(shape, labels)
            v["total"] += 1
            for t in range(1, 61):
                n = step(e)
                if n is e:
                    v["fixed_point"] += 1
                    v["max_steps_to_fixed"] = max(v["max_steps_to_fixed"], t - 1)
                    v["largest_fixed_point"] = max(v["largest_fixed_point"], e.size)
                    break
                e = n
            else:
                v["not_fixed_60"] += 1
    out["size7_validation"] = v
    print(f"size-7 validation: {v}", file=sys.stderr)

    # (B) census of size-8 expressions
    shapes = list(trees(8))
    assert len(shapes) == 429
    census = {"fixed_point": 0, "exceeded_20000": 0, "other": 0, "max_steps_to_fixed": 0,
              "exceeded_examples": [], "other_examples": [], "largest_fixed_point": 0}
    for shape in shapes:
        for labels in itertools.product((0, 1), repeat=8):
            e = build(shape, labels)
            cls = "other"
            for t in range(1, 61):
                n = step(e)
                if n is e:
                    cls = "fixed_point"
                    census["max_steps_to_fixed"] = max(census["max_steps_to_fixed"], t - 1)
                    census["largest_fixed_point"] = max(census["largest_fixed_point"], e.size)
                    break
                e = n
                if e.size > 20000:
                    cls = "exceeded_20000"
                    break
            census[cls] += 1
            if cls == "exceeded_20000" and len(census["exceeded_examples"]) < 60:
                census["exceeded_examples"].append(to_str(build(shape, labels)))
            if cls == "other" and len(census["other_examples"]) < 5:
                census["other_examples"].append((to_str(build(shape, labels)), e.size))
    census["total"] = sum(census[k] for k in ("fixed_point", "exceeded_20000", "other"))
    out["B"] = census
    print(f"B: {census['fixed_point']} fixed, {census['exceeded_20000']} exceeded, {census['other']} other "
          f"({time.time()-t0:.0f}s)", file=sys.stderr)

    out["runtime_s"] = round(time.time() - t0, 1)
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "census.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    measured = {
        "value": {"A_pass": out["A"]["pass"], "C_pass": out["C"]["pass"]},
        "unit": "pre-registered components A (exponential growth) and C (rule 110 emulation)",
        "n": {"A_steps": 40, "C_cases": n_cases, "B_expressions": census["total"]},
        "uncertainty": None,
        "extra": {
            "A": {k: v for k, v in out["A"].items() if k != "sizes"},
            "A_sizes_first_12": sizes[:12],
            "C": {k: v for k, v in out["C"].items() if k not in ("mismatches",)},
            "C_mismatches": out["C"]["mismatches"],
            "B": {k: v for k, v in census.items() if k not in ("exceeded_examples", "other_examples")},
            "B_exceeded_examples": census["exceeded_examples"],
            "size7_validation": out["size7_validation"],
            "runtime_s": out["runtime_s"],
        },
    }
    print(json.dumps(measured, indent=2))


if __name__ == "__main__":
    main()
