#!/usr/bin/env python3
"""Test of wolfram2002-ch11-11: remainder-selected arithmetic systems emulate
two-register machines.

Register machine (NKS ch. 3 conventions): program of L instructions, positions
1..L, executed cyclically.  ('i', r): increment register r, go to next position.
('d', r, j): if register r > 0, decrement it and jump to position j; else go to
the next position.

Encoding (NKS p. 673): n = i + L * 2^a * 3^b, with i in 1..L the program position
and a, b the two registers.  The arithmetic system computes rho = n mod 6L and
applies the branch (p, q, s): n -> (p*n + q) // s.  For L = 5 the modulus is 30.
"""
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261111


def rm_step(prog, state):
    i, regs = state
    ins = prog[i - 1]
    regs = list(regs)
    L = len(prog)
    nxt = i + 1 if i < L else 1
    if ins[0] == "i":
        regs[ins[1]] += 1
        return (nxt, tuple(regs))
    r, j = ins[1], ins[2]
    if regs[r] > 0:
        regs[r] -= 1
        return (j, tuple(regs))
    return (nxt, tuple(regs))


def compile_map(prog):
    """Return dict rho -> (p, q, s) for rho in 0..6L-1."""
    L = len(prog)
    M = 6 * L
    prime = (2, 3)
    table = {}
    for rho in range(M):
        i = rho % L
        if i == 0:
            i = L
        m_mod6 = ((rho - i) // L) % 6  # m = 2^a 3^b mod 6
        ins = prog[i - 1]
        nxt = i + 1 if i < L else 1
        if ins[0] == "i":
            pr = prime[ins[1]]
            # n = i + L m  ->  nxt + L pr m = pr*(n - i) + nxt
            table[rho] = (pr, nxt - pr * i, 1)
        else:
            r, j = ins[1], ins[2]
            pr = prime[r]
            if m_mod6 % pr == 0:
                # register nonzero: n -> j + L m / pr = (n - i)/pr + j
                table[rho] = (1, pr * j - i, pr)
            else:
                table[rho] = (1, nxt - i, 1)
    return M, table


def arith_step(M, table, n):
    p, q, s = table[n % M]
    num = p * n + q
    assert num % s == 0
    return num // s


POW3 = [1]


def encode(L, state):
    """n = i + L * 2^a * 3^b (injective, so comparing encodings compares states)."""
    i, (a, b) = state
    while len(POW3) <= b:
        POW3.append(POW3[-1] * 3)
    return i + L * (1 << a) * POW3[b]


def compare(prog, state0, steps, table_override=None):
    L = len(prog)
    M, table = compile_map(prog)
    if table_override:
        table = dict(table)
        table.update(table_override)
    n = encode(L, state0)
    st = state0
    mism = 0
    first = None
    maxn_bits = 0
    for t in range(steps):
        st = rm_step(prog, st)
        n = arith_step(M, table, n)
        maxn_bits = max(maxn_bits, n.bit_length())
        if n != encode(L, st):
            mism += 1
            if first is None:
                first = t + 1
    return mism, first, maxn_bits, st


def random_program(rng, L):
    prog = []
    for _ in range(L):
        if rng.random() < 0.5:
            prog.append(("i", int(rng.integers(0, 2))))
        else:
            prog.append(("d", int(rng.integers(0, 2)), int(rng.integers(1, L + 1))))
    return tuple(prog)


HAND = {
    # L=3: move a into b forever: a never empties because position 3 refills a.
    "L3_move": (("d", 0, 2), ("i", 1), ("i", 0)),
    # L=5: double a into b (a -> b twice), then refill: registers grow without bound.
    "L5_double": (("d", 0, 2), ("i", 1), ("i", 1), ("i", 0), ("d", 1, 1)),
    # L=7: copy-like loop with two counters.
    "L7_copy": (("i", 0), ("d", 0, 3), ("i", 1), ("i", 1), ("d", 1, 6), ("i", 0), ("d", 0, 1)),
}


def main():
    rng = np.random.default_rng(SEED)
    results = {"random_L5": [], "hand": {}, "perturbation": {}}
    total_steps = 0
    total_mism = 0
    for k in range(200):
        prog = random_program(rng, 5)
        for s0 in ((1, (0, 0)), (int(rng.integers(1, 6)), (int(rng.integers(0, 21)), int(rng.integers(0, 21))))):
            mism, first, bits, _ = compare(prog, s0, 10000)
            total_steps += 10000
            total_mism += mism
            results["random_L5"].append({"prog": prog, "start": s0, "mismatches": mism,
                                         "max_n_bits": bits})
    for name, prog in HAND.items():
        mism, first, bits, final = compare(prog, (1, (1, 0)), 20000)
        total_steps += 20000
        total_mism += mism
        results["hand"][name] = {"prog": prog, "mismatches": mism, "max_n_bits": bits,
                                 "final_state": final}
    # Perturbation check: change one branch's additive constant by 1.
    detected = False
    for name, prog in HAND.items():
        M, table = compile_map(prog)
        rho = 1 + len(prog) * 2  # the branch used by state (1, a=1, b=0)
        p, q, s = table[rho]
        try:
            mism, first, _, _ = compare(prog, (1, (1, 0)), 10000, {rho: (p, q + s, s)})
        except AssertionError:
            mism, first = 1, 1
        results["perturbation"][name] = {"mismatches": mism, "first_mismatch_step": first}
        detected = detected or mism > 0

    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "runs.json"), "w") as f:
        json.dump(results, f, indent=1)

    max_bits = max([r["max_n_bits"] for r in results["random_L5"]] +
                   [r["max_n_bits"] for r in results["hand"].values()])
    if total_mism == 0 and detected:
        verdict = "supports"
    elif total_mism > 0:
        verdict = "refutes"
    else:
        verdict = "inconclusive"
    measured = {
        "value": total_mism,
        "unit": "steps at which the arithmetic-system value differs from the encoding of the register-machine state",
        "n": total_steps,
        "uncertainty": "exact integer arithmetic; none",
        "extra": {
            "programs": {"random_L5": 200, "random_L5_runs": 400, "hand_written": list(HAND)},
            "modulus": {"L3": 18, "L5": 30, "L7": 42},
            "largest_n_bits": max_bits,
            "perturbation_detected": detected,
            "perturbation_first_mismatch_step": {k: v["first_mismatch_step"]
                                                 for k, v in results["perturbation"].items()},
            "hand_final_states": {k: v["final_state"] for k, v in results["hand"].items()},
        },
    }
    print(json.dumps({"measured": measured, "verdict": verdict}, indent=1))


if __name__ == "__main__":
    main()
