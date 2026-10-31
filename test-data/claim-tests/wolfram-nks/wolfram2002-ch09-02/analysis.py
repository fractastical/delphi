#!/usr/bin/env python3
"""wolfram2002-ch09-02: numbers of reversible nearest-neighbour cellular automata.

Compiles revca.c (exhaustive pruned search with the exact pair-graph injectivity test), runs it
for (k, r) = (2, 1), (2, 2) [method check: 62] and (3, 1), and independently checks the rules
found with Wolfram's periodic-configuration test (ReversibleQ, NKS p. 1017) implemented here in
Python, plus random balanced rules that were not found.  Prints JSON to stdout.
"""
import itertools
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PERIOD_MAX = {2: 4, 3: 9}   # NKS note: sufficient block lengths for k=2,r=1 and k=3,r=1
N_RANDOM = 10000


def compile_c():
    exe = os.path.join("/tmp", "revca_bin")
    subprocess.run(["gcc", "-O2", "-o", exe, os.path.join(HERE, "revca.c")], check=True)
    return exe


def run_enum(exe, k, r, outfile):
    t0 = time.time()
    res = subprocess.run([exe, str(k), str(r), outfile], capture_output=True, text=True, check=True)
    count, nodes = map(int, res.stdout.split())
    rules = [line.strip() for line in open(outfile) if line.strip()]
    return {"k": k, "r": r, "count": count, "search_nodes": nodes, "seconds": round(time.time() - t0, 2), "rules": rules}


def rule_table(digits, k):
    """digits: most significant neighbourhood first (Wolfram order); returns array indexed by l*k^2+c*k+r."""
    n = len(digits)
    return np.array([int(digits[n - 1 - i]) for i in range(n)], dtype=np.int64)


def ca_step_cyclic(x, tab, k):
    idx = np.roll(x, 1) * k * k + x * k + np.roll(x, -1)
    return tab[idx]


_CONFS = {}


def all_confs(k, m):
    if (k, m) not in _CONFS:
        _CONFS[(k, m)] = np.array(list(itertools.product(range(k), repeat=m)), dtype=np.int64).reshape(k ** m, m)
    return _CONFS[(k, m)]


def reversible_q(tab, k, nmax):
    """Wolfram's ReversibleQ: for every m <= nmax, the k^m cyclic configurations of length m have distinct successors."""
    for m in range(1, nmax + 1):
        X = all_confs(k, m)
        idx = np.roll(X, 1, axis=1) * k * k + X * k + np.roll(X, -1, axis=1)
        Y = tab[idx]
        codes = Y @ (k ** np.arange(m, dtype=np.int64))
        if np.unique(codes).size != codes.size:
            return False
    return True


def main():
    exe = compile_c()
    out = {"enumeration": {}}
    for k, r in ((2, 1), (2, 2), (3, 1)):
        res = run_enum(exe, k, r, "/tmp/revca_%d_%d.txt" % (k, r))
        key = "k%d_r%d" % (k, r)
        out["enumeration"][key] = {a: b for a, b in res.items() if a != "rules"}
        if (k, r) == (2, 1):
            out["enumeration"][key]["rule_numbers"] = sorted(int(d, 2) for d in res["rules"])
        if (k, r) == (3, 1):
            rules3 = res["rules"]
        if (k, r) == (2, 1):
            rules2 = res["rules"]
        print(key, res["count"], res["search_nodes"], res["seconds"], file=sys.stderr)
    # independent check with the periodic-configuration test
    checks = {}
    for k, rules in ((2, rules2), (3, rules3)):
        passed = sum(reversible_q(rule_table(d, k), k, PERIOD_MAX[k]) for d in rules)
        rng = np.random.default_rng(0)
        n_ent = k ** 3
        found = set(rules)
        sampled_fail = 0
        sampled = 0
        for _ in range(N_RANDOM if k == 3 else 0):
            digs = np.repeat(np.arange(k), k * k)
            rng.shuffle(digs)
            s = "".join(map(str, digs))
            if s in found:
                continue
            sampled += 1
            sampled_fail += int(not reversible_q(rule_table(s, k), k, PERIOD_MAX[k]))
        if k == 2:
            # all 256 rules: periodic test must agree exactly with the enumeration
            agree = 0
            for num in range(256):
                s = format(num, "08b")
                agree += int(reversible_q(rule_table(s, 2), 2, 4) == (s in found))
            checks["k2"] = {"found_rules_passing_periodic_test": passed, "found": len(rules), "all_256_agree_with_periodic_test": agree}
        else:
            checks["k3"] = {"found_rules_passing_periodic_test": passed, "found": len(rules),
                            "random_balanced_rules_not_found_sampled": sampled, "of_which_fail_periodic_test": sampled_fail}
    out["checks"] = checks
    # symmetry families for k=3 (colour permutations x reflection)
    fams = set()
    for d in rules3:
        tab = rule_table(d, 3)
        variants = []
        for perm in itertools.permutations(range(3)):
            p = np.array(perm)
            for refl in (False, True):
                t2 = np.empty(27, dtype=np.int64)
                for l in range(3):
                    for c in range(3):
                        for rr in range(3):
                            src = (rr * 9 + c * 3 + l) if refl else (l * 9 + c * 3 + rr)
                            t2[p[l] * 9 + p[c] * 3 + p[rr]] = p[tab[src]]
                variants.append("".join(str(int(v)) for v in t2[::-1]))
        fams.add(min(variants))
    out["k3_symmetry_families"] = len(fams)
    c21 = out["enumeration"]["k2_r1"]["count"]
    c22 = out["enumeration"]["k2_r2"]["count"]
    c31 = out["enumeration"]["k3_r1"]["count"]
    ok = (c21 == 6 and out["enumeration"]["k2_r1"]["rule_numbers"] == [15, 51, 85, 170, 204, 240] and c22 == 62 and c31 == 1800
          and checks["k2"]["all_256_agree_with_periodic_test"] == 256 and checks["k3"]["found_rules_passing_periodic_test"] == c31
          and checks["k3"]["of_which_fail_periodic_test"] == checks["k3"]["random_balanced_rules_not_found_sampled"])
    out["verdict"] = "supports" if ok else ("refutes" if (c22 == 62 and (c21 != 6 or c31 != 1800)) else "mixed")
    json.dump(out, sys.stdout, indent=1)
    print()
    with open(os.path.join(HERE, "derived", "reversible_k3_r1.txt"), "w") as f:
        f.write("\n".join(rules3) + "\n")


if __name__ == "__main__":
    main()
