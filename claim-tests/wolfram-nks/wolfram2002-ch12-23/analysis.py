#!/usr/bin/env python3
"""Test of wolfram2002-ch12-23: halting-time growth census of all 4096 two-state two-colour
Turing machines under the one-sided convention of NKS p. 761 / p. 1143.
Writes derived/measurements.json and derived/machines.csv (one row per machine: number, class, supplementary class, T(3..10)).
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
S, K = 2, 2
XMAX = 1023
TMAX = 20000
LENGTHS = range(3, 11)
MIN_LENGTHS = 5
BATCH = 512
EXT_BATCH = 8
EXT_TMAX = 2 ** 17
RMS_TOL = 0.15


def rule_from_number(n, s=S, k=K):
    """NKS numbering (p. 888). Returns dict (state 1-based, colour) -> (new state, new colour, displacement)."""
    base = 2 * s * k
    digits = []
    x = n
    for _ in range(s * k):
        digits.append(x % base)
        x //= base
    digits = digits[::-1]
    rule = {}
    for i in range(s):
        for j in range(k):
            d = digits[i * k + j]
            rule[(i + 1, k - 1 - j)] = ((d // (2 * k)) % s + 1, (d // 2) % k, 2 * (d % 2) - 1)
    return rule


def number_from_rule(rule, s=S, k=K):
    n = 0
    for i in range(1, s + 1):
        for j in range(k):
            ns, nc, mv = rule[(i, k - 1 - j)]
            n = n * (2 * s * k) + 2 * k * (ns - 1) + 2 * nc + (mv + 1) // 2
    return n


def left_runaway_states(rule):
    """States from which, reading blanks forever, the head keeps moving left (i increases)
    through a cycle of states: once the head is left of every visited cell in such a state it
    never returns."""
    out = set()
    for s0 in range(1, S + 1):
        s, seen = s0, []
        ok = True
        while s not in seen:
            seen.append(s)
            ns, nc, mv = rule[(s, 0)]
            if mv != -1:  # displacement -1 means i -= (-1) -> i increases -> moves left
                ok = False
                break
            s = ns
        if ok:
            out.update(seen)
    return out


def run(rule, x, runaway, tmax=TMAX):
    """Returns (halt_step or None, output or None, reason)."""
    tape = [int(c) for c in bin(x)[2:][::-1]]  # tape[0] = cell 1 = least significant digit
    i, s = 0, 1  # i is 0-based index of cell i+1
    t = 0
    max_visited = len(tape) - 1
    # Brent cycle detection on full configurations
    power = lam = 1
    snap = None
    while t < tmax:
        if i < 0:
            return t, int("".join(str(c) for c in tape[::-1]), 2) if any(tape) else 0, "halt"
        if i >= len(tape):
            tape.extend([0] * (i - len(tape) + 1))
        if i > max_visited:
            max_visited = i
            if s in runaway:
                return None, None, "left-runaway"
        ns, nc, mv = rule[(s, tape[i])]
        tape[i] = nc
        s = ns
        i -= mv
        t += 1
        cfg = (s, i, tuple(tape))
        if snap is not None and cfg == snap:
            return None, None, "cycle"
        if power == lam:
            snap = cfg
            power *= 2
            lam = 0
        lam += 1
    return None, None, "cutoff"


def run_all(numbers, xs, tmax=TMAX, log=None):
    """Vectorised version of run() over every (machine, input) pair, same conventions and the same
    three non-halting detections (left runaway, Brent cycle detection with a global snapshot
    schedule, cutoff). Returns halts[M, X] (-1 = no halt), outputs[M, X] (python ints or None),
    and reason codes[M, X] (0 halt, 1 left-runaway, 2 cycle, 3 cutoff)."""
    M, X = len(numbers), len(xs)
    nst = np.zeros((M, (S + 1) * K), np.int8)
    ncl = np.zeros((M, (S + 1) * K), np.uint8)
    mvs = np.zeros((M, (S + 1) * K), np.int8)
    runaway = np.zeros((M, S + 1), bool)
    for mi, n in enumerate(numbers):
        rule = rule_from_number(n)
        for (st, col), (ns, nc, mv) in rule.items():
            nst[mi, st * K + col], ncl[mi, st * K + col], mvs[mi, st * K + col] = ns, nc, mv
        for st in left_runaway_states(rule):
            runaway[mi, st] = True
    R = M * X
    mach = np.repeat(np.arange(M), X)
    width = 16
    tape = np.zeros((R, width), np.uint8)
    for xi, x in enumerate(xs):
        bits = [int(c) for c in bin(x)[2:][::-1]]
        tape[xi::X, :len(bits)] = bits
    pos = np.zeros(R, np.int64)
    state = np.ones(R, np.int8)
    max_visited = np.tile(np.array([digits_len(x) - 1 for x in xs], np.int64), M)
    halts = np.full(R, -1, np.int64)
    reason = np.full(R, 3, np.int8)
    outputs = [None] * R
    active = np.arange(R)
    snap_tape, snap_pos, snap_state = None, None, None
    power = lam = 1
    t = 0
    while t < tmax and len(active) > 0:
        # halting / runaway checks on the configuration at step t
        halted = pos < 0
        if halted.any():
            idx = active[halted]
            halts[idx] = t
            reason[idx] = 0
            for r, row in zip(idx, tape[halted]):
                nz = np.flatnonzero(row)
                outputs[r] = int(sum(1 << int(j) for j in nz)) if len(nz) else 0
        new_max = pos > max_visited
        np.maximum(max_visited, pos, out=max_visited)
        ran = new_max & runaway[mach, state]
        if ran.any():
            reason[active[ran]] = 1
        keep = ~(halted | ran)
        if not keep.all():
            active, tape, pos, state, max_visited, mach = active[keep], tape[keep], pos[keep], state[keep], max_visited[keep], mach[keep]
            if snap_tape is not None:
                snap_tape, snap_pos, snap_state = snap_tape[keep], snap_pos[keep], snap_state[keep]
            if len(active) == 0:
                break
        if pos.max() >= width:
            new_w = max(width * 2, int(pos.max()) + 1)
            tape = np.pad(tape, ((0, 0), (0, new_w - width)))
            if snap_tape is not None:
                snap_tape = np.pad(snap_tape, ((0, 0), (0, new_w - width)))
            width = new_w
        rows = np.arange(len(active))
        colour = tape[rows, pos]
        key = state.astype(np.int64) * K + colour
        tape[rows, pos] = ncl[mach, key]
        pos -= mvs[mach, key]
        state = nst[mach, key]
        t += 1
        if snap_tape is not None:
            same = (state == snap_state) & (pos == snap_pos)
            if same.any():
                same_idx = np.flatnonzero(same)
                cyc = same_idx[np.all(tape[same_idx] == snap_tape[same_idx], axis=1)]
                if len(cyc):
                    reason[active[cyc]] = 2
                    keep = np.ones(len(active), bool)
                    keep[cyc] = False
                    active, tape, pos, state, max_visited, mach = active[keep], tape[keep], pos[keep], state[keep], max_visited[keep], mach[keep]
                    snap_tape, snap_pos, snap_state = snap_tape[keep], snap_pos[keep], snap_state[keep]
        if power == lam:
            snap_tape, snap_pos, snap_state = tape.copy(), pos.copy(), state.copy()
            power *= 2
            lam = 0
        lam += 1
        if log and t % 1000 == 0:
            log(f"  step {t}: {len(active)} active rows, width {width}")
    return halts.reshape(M, X), np.array(outputs, dtype=object).reshape(M, X), reason.reshape(M, X)


def supplementary_class(T):
    """Supplementary (not pre-registered) classifier: growth class of T(n) allowing a parity-dependent
    constant (odd and even n fitted separately) and an initial transient (first two lengths dropped);
    'constant' if T is eventually constant."""
    ns = sorted(int(k) for k in T if T[k] is not None)
    ts = [T[k] for k in T if T[k] is not None]
    ts = [t for _, t in sorted(zip([int(k) for k in T if T[k] is not None], ts))]
    if len(ns) < 5:
        return "insufficient"
    if len(set(ts[2:])) == 1:
        return "constant"
    for name in ("linear", "quadratic", "exponential"):
        ok = True
        for parity in (0, 1):
            sub = [(n, t) for n, t in zip(ns, ts) if n % 2 == parity and n > ns[1]]
            if len(sub) < 3:
                continue
            sn, st = np.array([n for n, _ in sub], float), np.array([t for _, t in sub], float)
            if name == "linear":
                A = np.column_stack([np.ones_like(sn), sn])
            elif name == "quadratic":
                A = np.column_stack([np.ones_like(sn), sn, sn ** 2])
            else:
                A = np.column_stack([np.ones_like(sn), 2.0 ** sn])
            coef, *_ = np.linalg.lstsq(A, st, rcond=None)
            if np.max(np.abs(A @ coef - st)) > 1e-6 or coef[-1] <= 0:
                ok = False
                break
        if ok:
            return name
    return "other"


def digits_len(x):
    return 1 if x == 0 else x.bit_length()


# ------------------------------------------------------------ growth fitting
def fit_models(ns, ts):
    ns, ts = np.asarray(ns, float), np.asarray(ts, float)
    out = {}

    def lsq(A):
        coef, *_ = np.linalg.lstsq(A, ts, rcond=None)
        pred = A @ coef
        return coef, pred

    one = np.ones_like(ns)
    c, p = lsq(np.column_stack([one]))
    out["constant"] = (c, p)
    c, p = lsq(np.column_stack([one, ns]))
    out["linear"] = (c, p)
    c, p = lsq(np.column_stack([one, ns, ns ** 2]))
    out["quadratic"] = (c, p)
    best = None
    for b in (2, 3, 4):
        c, p = lsq(np.column_stack([one, b ** ns]))
        rms = np.sqrt(np.mean(((ts - p) / ts) ** 2))
        if best is None or rms < best[0]:
            best = (rms, c, p, b)
    out["exponential"] = (best[1], best[2], best[3])
    return out


def classify(ns, ts):
    if len(ns) < MIN_LENGTHS:
        return "insufficient", None
    models = fit_models(ns, ts)
    ts_a = np.asarray(ts, float)
    # exact fits in order of complexity, with positivity of the leading coefficient
    for name, cond in (("constant", lambda c: True), ("linear", lambda c: c[1] > 0), ("quadratic", lambda c: c[2] > 0), ("exponential", lambda c: c[1] > 0)):
        c, p = models[name][0], models[name][1]
        if np.max(np.abs(p - ts_a)) < 1e-9 and cond(c):
            return name, {"fit": "exact", "coef": [round(float(v), 6) for v in c], **({"base": models[name][2]} if name == "exponential" else {})}
    for name, cond in (("linear", lambda c: c[1] > 0), ("quadratic", lambda c: c[2] > 0), ("exponential", lambda c: c[1] > 0)):
        c, p = models[name][0], models[name][1]
        rms = float(np.sqrt(np.mean(((ts_a - p) / ts_a) ** 2)))
        if rms <= RMS_TOL and cond(c):
            return name, {"fit": "approx", "rel_rms": round(rms, 4), "coef": [round(float(v), 4) for v in c], **({"base": models[name][2]} if name == "exponential" else {})}
    return "other", {"fit": "none", "T": [int(v) for v in ts]}


def main():
    t0 = time.time()
    n_machines = (2 * S * K) ** (S * K)
    machines = []
    xs = list(range(XMAX + 1))
    reason_names = {0: "halt", 1: "left-runaway", 2: "cycle", 3: "cutoff"}
    # cross-check of the vectorised runner against the scalar reference on a sample of machines
    sample = sorted(set([1447, 261, 3279, 1953, 378, 2289, 1507, 1285] + np.random.default_rng(1).integers(0, n_machines, 24).tolist()))
    Hs, Os, Rs = run_all(sample, xs[:256], tmax=5000)
    for mi, n in enumerate(sample):
        rule = rule_from_number(n)
        assert number_from_rule(rule) == n
        ra = left_runaway_states(rule)
        for xi, x in enumerate(xs[:256]):
            h, f, why = run(rule, x, ra, tmax=5000)
            assert (h, f, why) == (None if Hs[mi, xi] < 0 else int(Hs[mi, xi]), Os[mi, xi], reason_names[int(Rs[mi, xi])]), (n, x)
    print(f"  vectorised runner agrees with scalar reference on {len(sample)} machines x 256 inputs", flush=True)
    for b0 in range(0, n_machines, BATCH):
        nums = list(range(b0, min(b0 + BATCH, n_machines)))
        H, O, R = run_all(nums, xs)
        for mi, n in enumerate(nums):
            halts = [None if h < 0 else int(h) for h in H[mi]]
            outs = list(O[mi])
            reasons = {reason_names[c]: int(v) for c, v in zip(*np.unique(R[mi], return_counts=True))}
            T = {}
            for n_len in LENGTHS:
                vals = [halts[x] for x in range(XMAX + 1) if digits_len(x) == n_len and halts[x] is not None]
                if vals:
                    T[n_len] = max(vals)
            cls, info = classify(list(T.keys()), list(T.values()))
            machines.append({"number": n, "halts": halts, "outputs": outs, "reasons": reasons, "T": T, "class": cls, "fit": info})
        print(f"  {len(machines)}/{n_machines} machines ({time.time() - t0:.0f}s)", flush=True)

    # census numbers
    n_never = sum(all(h is None for h in m["halts"]) for m in machines)
    n_always = sum(all(h is not None for h in m["halts"]) for m in machines)
    n_sometimes = n_machines - n_never
    cutoff_pairs = sum(m["reasons"].get("cutoff", 0) for m in machines)
    funcs = {}
    pairs = {}
    for m in machines:
        fkey = tuple(m["outputs"])
        pkey = (fkey, tuple(m["halts"]))
        funcs.setdefault(fkey, []).append(m["number"])
        pairs.setdefault(pkey, []).append(m["number"])
    total_funcs = [f for f in funcs if all(v is not None for v in f)]
    xplus1 = tuple(x + 1 for x in range(XMAX + 1))
    xminus1 = tuple((x - 1 if x > 0 else None) for x in range(XMAX + 1))
    # growth classes over distinct (f, t) pairs
    pair_class = {}
    for pkey, nums in pairs.items():
        pair_class[pkey] = machines[nums[0]]["class"]
    class_counts = defaultdict(int)
    for pkey, c in pair_class.items():
        class_counts[c] += 1
    class_counts_total = defaultdict(int)
    for pkey, c in pair_class.items():
        if all(v is not None for v in pkey[0]):
            class_counts_total[c] += 1
    machine_class_counts = defaultdict(int)
    for m in machines:
        machine_class_counts[m["class"]] += 1

    # exponential pairs and constant-time partners
    exp_pairs = [(pkey, nums) for pkey, nums in pairs.items() if pair_class[pkey] == "exponential"]
    partners = []
    for pkey, nums in exp_pairs:
        same_f = [n for n in funcs[pkey[0]] if machines[n]["class"] == "constant"]
        all_same_f = [{"number": n, "class": machines[n]["class"], "T": machines[n]["T"]} for n in funcs[pkey[0]] if n not in nums]
        bounded = [d["number"] for d in all_same_f if d["T"] and max(d["T"].values()) <= 2 * max(min(d["T"].values()), 1) and supplementary_class(d["T"]) == "constant"]
        partners.append({"exponential_machines": nums, "T": machines[nums[0]]["T"], "fit": machines[nums[0]]["fit"],
                         "constant_time_partners": same_f[:20], "n_constant_time_partners": len(same_f),
                         "total_function": all(v is not None for v in pkey[0]),
                         "other_machines_computing_same_function": all_same_f[:10], "n_other_machines_computing_same_function": len(all_same_f),
                         "classes_of_other_machines_computing_same_function": dict(sorted(((c, sum(d["class"] == c for d in all_same_f)) for c in set(d["class"] for d in all_same_f)))),
                         "supplementary_bounded_time_partners": bounded[:20], "n_supplementary_bounded_time_partners": len(bounded)})
    # supplementary: for exponential pairs computing partial functions, partners that agree with the
    # exponential machine on every input where it halts (ignoring inputs where it does not halt)
    for p in partners:
        if p["total_function"]:
            continue
        ex = machines[p["exponential_machines"][0]]
        dom = [x for x in range(XMAX + 1) if ex["halts"][x] is not None]
        found = []
        for m in machines:
            if m["number"] in p["exponential_machines"]:
                continue
            if all(m["halts"][x] is not None and m["outputs"][x] == ex["outputs"][x] for x in dom):
                Td = {}
                for n_len in LENGTHS:
                    vals = [m["halts"][x] for x in dom if digits_len(x) == n_len]
                    if vals:
                        Td[n_len] = max(vals)
                if len(set(Td.values())) == 1:
                    found.append({"number": m["number"], "T_on_domain": sorted(set(Td.values()))[0]})
        p["undefined_inputs"] = [x for x in range(XMAX + 1) if ex["halts"][x] is None]
        p["supplementary_constant_time_partners_on_halting_domain"] = found[:20]
        p["n_supplementary_constant_time_partners_on_halting_domain"] = len(found)
    others = [{"number": m["number"], "T": m["T"], "fit": m["fit"], "supplementary_class": supplementary_class(m["T"])} for m in machines if m["class"] == "other"]
    supp_counts = defaultdict(int)
    for pkey, c in pair_class.items():
        supp_counts[c if c != "other" else "other->" + supplementary_class(dict(zip(LENGTHS, [machines[pairs[pkey][0]]["T"].get(n) for n in LENGTHS])))] += 1

    # pre-registered extended run for machines classed 'other': inputs up to 2^14 - 1
    other_numbers = [m["number"] for m in machines if m["class"] == "other"]
    extended = []
    t1 = time.time()
    xs_ext = list(range(2 ** 14))
    for b0 in range(0, len(other_numbers), EXT_BATCH):
        nums_b = other_numbers[b0:b0 + EXT_BATCH]
        H, O, R = run_all(nums_b, xs_ext, tmax=EXT_TMAX)
        for mi, n in enumerate(nums_b):
            T = {}
            for n_len in range(3, 15):
                vals = [int(H[mi, x]) for x in xs_ext if digits_len(x) == n_len and H[mi, x] >= 0]
                if vals:
                    T[n_len] = max(vals)
            cls, info = classify(list(T.keys()), list(T.values()))
            extended.append({"number": n, "T": T, "class": cls, "fit": info, "supplementary_class": supplementary_class(T),
                             "max_halting_time_seen": int(H[mi].max()), "inputs_at_cutoff": int((R[mi] == 3).sum())})
        print(f"  extended run {min(b0 + EXT_BATCH, len(other_numbers))}/{len(other_numbers)} ({time.time() - t1:.0f}s)", flush=True)
    ext_still_other = [e for e in extended if e["class"] == "other"]
    ext_resolved = {}
    for e in extended:
        ext_resolved[e["class"]] = ext_resolved.get(e["class"], 0) + 1

    book_examples = {3279: "5", 1285: "6n+3", 3333: "4n+3", 261: "2n+3", 1447: "2n^2+8n+7", 1953: "2^(n+2)-3", 1969: "2n+1", 3517: "3", 3246: "2n+1", 3374: "4n-1", 1507: "~2.5n^2"}
    examples = {}
    for num, formula in book_examples.items():
        m = machines[num]
        examples[num] = {"book_formula": formula, "T": m["T"], "class": m["class"], "fit": m["fit"]}

    results = {
        "n_machines": n_machines, "inputs": f"x = 0..{XMAX}", "tmax": TMAX, "seconds": time.time() - t0,
        "census": {"never_halt": n_never, "sometimes_halt": n_sometimes, "always_halt": n_always,
                   "book": {"never_halt": 748, "sometimes_halt": 3348, "always_halt": 1683},
                   "n_distinct_functions": len(funcs), "n_total_functions": len(total_funcs), "book_functions": [351, 149],
                   "n_distinct_f_t_pairs": len(pairs), "n_total_f_t_pairs": sum(1 for p in pairs if all(v is not None for v in p[0])), "book_pairs": [492, 230],
                   "n_machines_computing_x_plus_1": len(funcs.get(xplus1, [])), "n_machines_computing_x_minus_1": len(funcs.get(xminus1, [])), "book_x_plus_1": 17,
                   "machine_input_pairs_hitting_cutoff": cutoff_pairs},
        "growth_classes_over_pairs": dict(class_counts), "growth_classes_over_total_pairs": dict(class_counts_total),
        "book_growth_classes_over_pairs": {"constant": 164, "linear": 295, "quadratic": 27, "exponential": 6},
        "book_growth_classes_over_total_pairs": {"constant": 84, "linear": 136, "quadratic": 7, "exponential": 3},
        "growth_classes_over_machines": dict(machine_class_counts),
        "exponential_pairs": partners,
        "exponential_total_function_machines": sorted(n for p in partners if p["total_function"] for n in p["exponential_machines"]),
        "book_exponential_total_function_machines": [378, 1953, 2289],
        "other_class_machines": others[:15], "n_other_class_machines": len(others),
        "supplementary_growth_classes_over_pairs": dict(supp_counts),
        "extended_run": {"inputs": "x = 0..16383 (lengths 3..14 used)", "tmax": EXT_TMAX, "preregistered_tmax": 2 ** 20,
                         "n_machines": len(extended), "classes_after_extension": ext_resolved,
                         "max_halting_time_seen_over_all": max([e["max_halting_time_seen"] for e in extended], default=0),
                         "n_machines_still_other": len(ext_still_other), "machines_still_other_numbers": [e["number"] for e in ext_still_other],
                         "supplementary_classes_of_still_other": dict(sorted(((c, sum(e["supplementary_class"] == c for e in ext_still_other)) for c in set(e["supplementary_class"] for e in ext_still_other)))),
                         "machines_still_other_first_10": ext_still_other[:10], "seconds": time.time() - t1},
        "book_examples": examples,
    }
    crit = {
        "a_no_other_class_pairs": class_counts.get("other", 0) == 0,
        "a_extended_no_other_class_confirmed": len(ext_still_other) == 0,
        "b_every_exponential_pair_has_constant_partner": all(p["constant_time_partners"] for p in partners) and len(partners) > 0,
        "b_supplementary_every_exponential_pair_has_bounded_time_partner": all(p["supplementary_bounded_time_partners"] for p in partners) and len(partners) > 0,
        "b_supplementary_every_exponential_pair_has_constant_partner_on_halting_domain": all(p["constant_time_partners"] or p.get("n_supplementary_constant_time_partners_on_halting_domain", 0) > 0 for p in partners) and len(partners) > 0,
        "n_other_pairs": class_counts.get("other", 0), "n_exponential_pairs": len(partners),
    }
    if not crit["b_every_exponential_pair_has_constant_partner"] or not crit["a_extended_no_other_class_confirmed"]:
        verdict = "refutes"
    elif crit["a_no_other_class_pairs"]:
        verdict = "supports"
    else:
        verdict = "mixed"
    results["criteria"] = crit
    results["verdict"] = verdict
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump(results, f, indent=1)
    with open(os.path.join(HERE, "derived", "machines.csv"), "w") as f:
        f.write("number,class,supplementary_class," + ",".join(f"T{n}" for n in LENGTHS) + "\n")
        for m in machines:
            f.write(f"{m['number']},{m['class']},{supplementary_class(m['T'])}," + ",".join(str(m["T"].get(n, "")) for n in LENGTHS) + "\n")
    print(json.dumps(results, indent=1)[:6000])


if __name__ == "__main__":
    sys.exit(main())
