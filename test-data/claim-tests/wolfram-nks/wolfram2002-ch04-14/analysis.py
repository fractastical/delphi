#!/usr/bin/env python3
"""Test of wolfram2002-ch04-14: rationals have eventually periodic digit expansions
(period <= q - 1) and are the only numbers that do.

(1) Long division for 1/q (q <= 20000) and p/q (q <= 300, all p) in bases 2, 3, 10:
    preperiod and period from the remainder cycle; check period <= q-1 and
    preperiod + period <= q; compare base-10 periods of 1/q with OEIS A007732.
(2) 20000 random eventually periodic digit patterns: reconstruct the rational exactly
    and re-expand it; the digits must match.
(3) Sanity check on OEIS digits of sqrt(2), e, pi: no period p <= N/3 for which the last
    2p digits already repeat.

Run: python3 analysis.py   (needs numpy, requests)
"""
import datetime
import hashlib
import json
import os
from fractions import Fraction

import numpy as np
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261031
QMAX = 20000
QMAX_ALL_P = 300
BASES = (2, 3, 10)
N_PATTERNS = 20000
OEIS = {
    "A007732": "https://oeis.org/A007732/b007732.txt",
    "A002193": "https://oeis.org/A002193/b002193.txt",
    "A001113": "https://oeis.org/A001113/b001113.txt",
    "A000796": "https://oeis.org/A000796/b000796.txt",
}


def preperiod_period(p, q, b):
    """Preperiod and period of the base-b expansion of p/q (0 < p < q)."""
    seen = {}
    r = p % q
    i = 0
    while r not in seen:
        seen[r] = i
        r = (b * r) % q
        i += 1
    start = seen[r]
    return start, i - start


def expand(p, q, b, ndigits):
    digits = []
    r = p % q
    for _ in range(ndigits):
        r *= b
        digits.append(r // q)
        r %= q
    return digits


def fetch(url):
    t = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = requests.get(url, timeout=120, headers={"User-Agent": "delphisci-claim-test/1.0"})
    resp.raise_for_status()
    data = resp.content
    meta = {"download_url": url, "retrieved_at": t, "byte_size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}
    vals = {}
    for line in data.decode("ascii", "replace").splitlines():
        parts = line.split()
        if len(parts) >= 2 and not parts[0].startswith("#"):
            try:
                vals[int(parts[0])] = int(parts[1])
            except ValueError:
                pass
    return meta, vals


def part1():
    res = {}
    viol = []
    periods10 = {}
    for b in BASES:
        n = 0
        maxratio = 0.0
        for q in range(1, QMAX + 1):
            s, per = preperiod_period(1, q, b)
            n += 1
            if per > q - 1 and q > 1 or s + per > q:
                viol.append({"base": b, "p": 1, "q": q, "preperiod": s, "period": per})
            if q > 1:
                maxratio = max(maxratio, per / (q - 1))
            if b == 10:
                periods10[q] = per
        for q in range(2, QMAX_ALL_P + 1):
            for p in range(1, q):
                s, per = preperiod_period(p, q, b)
                n += 1
                if per > q - 1 or s + per > q:
                    viol.append({"base": b, "p": p, "q": q, "preperiod": s, "period": per})
        res[b] = {"expansions": n, "max_period_over_q_minus_1": round(maxratio, 6)}
    return res, viol, periods10


def part2(rng):
    bad = 0
    n = 0
    examples = []
    for _ in range(N_PATTERNS):
        b = int(rng.choice(BASES))
        s = int(rng.integers(0, 21))
        p = int(rng.integers(1, 31))
        pre = [int(x) for x in rng.integers(0, b, size=s)]
        while True:
            blk = [int(x) for x in rng.integers(0, b, size=p)]
            if any(d != b - 1 for d in blk):
                break
        A = 0
        for d in pre:
            A = A * b + d
        B = 0
        for d in blk:
            B = B * b + d
        x = Fraction(A * (b ** p - 1) + B, b ** s * (b ** p - 1))
        q = x.denominator
        want = pre + blk * ((s + 3 * p) // p + 2)
        got = expand(x.numerator, q, b, len(want))
        n += 1
        if got != want:
            bad += 1
            if len(examples) < 3:
                examples.append({"base": b, "pre": pre, "block": blk, "fraction": str(x)})
        else:
            # the minimal period of the reconstructed rational must also respect the bound
            _, per = preperiod_period(x.numerator % q, q, b) if q > 1 else (0, 1)
            if per > max(q - 1, 1):
                bad += 1
    return {"patterns": n, "patterns_not_reproduced": bad, "examples": examples}


def part3(digits, n_use=10000):
    d = np.array(digits[:n_use], dtype=np.int8)
    N = len(d)
    hits = []
    best = 0.0
    for p in range(1, N // 3 + 1):
        eq = d[p:] == d[:-p]
        mism = np.nonzero(~eq)[0]
        s_min = int(mism.max()) + 1 if len(mism) else 0  # agreement holds for all j >= s_min
        agreeing_periods = (N - s_min) / p
        best = max(best, agreeing_periods)
        if s_min <= N - 2 * p:
            hits.append(p)
    return {"digits_used": N, "periods_with_two_full_agreeing_repeats": hits[:10],
            "max_agreeing_periods_over_p": round(best, 3)}


def main():
    rng = np.random.default_rng(SEED)
    out = {}
    res1, viol, periods10 = part1()
    out["part1_rationals"] = {"per_base": res1, "violations": len(viol), "violation_examples": viol[:5]}
    out["part2_reconstruction"] = part2(rng)
    files = {}
    try:
        meta, a007732 = fetch(OEIS["A007732"])
        files["A007732"] = meta
        common = [n for n in a007732 if n in periods10]
        mism = [n for n in common if a007732[n] != periods10[n]]
        out["part1_oeis_a007732"] = {"terms_in_bfile": len(a007732), "compared": len(common),
                                     "mismatches": len(mism), "first_mismatches": mism[:5]}
    except Exception as e:
        out["part1_oeis_a007732"] = {"error": repr(e)}
    out["part3_irrationals"] = {}
    for name in ("A002193", "A001113", "A000796"):
        try:
            meta, vals = fetch(OEIS[name])
            files[name] = meta
            digits = [vals[k] for k in sorted(vals)]
            out["part3_irrationals"][name] = part3(digits)
        except Exception as e:
            out["part3_irrationals"][name] = {"error": repr(e)}
    out["files"] = files
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
