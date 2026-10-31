#!/usr/bin/env python3
"""Test of wolfram2002-ch04-19: the shift map x -> 2x mod 1 only transcribes the
binary digits of its seed (its itinerary is a suffix of the seed's digit sequence),
so it creates no randomness of its own.

Run: python3 analysis.py   (needs numpy, scipy, requests)
"""
import datetime
import hashlib
import json
import lzma
import math
import os
from fractions import Fraction

import numpy as np
import requests
from scipy.stats import chi2 as chi2_dist

HERE = os.path.dirname(os.path.abspath(__file__))
SEED = 20261031
N_FRACTIONS = 2000
STEPS = 2000
N_DIGITS = 10000
Q_MAX_PERIOD = 2000
K_MAX_DYADIC = 60
N_RANDOM_REF = 200
OEIS = {
    "A004539": "https://oeis.org/A004539/b004539.txt",
    "A010060": "https://oeis.org/A010060/b010060.txt",
    "A030190": "https://oeis.org/A030190/b030190.txt",
}
HALF = Fraction(1, 2)


def fetch_bfile(url):
    t = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    raw = r.content
    vals = {}
    for line in raw.decode().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        n, v = line.split()[:2]
        vals[int(n)] = int(v)
    return vals, {"download_url": url, "retrieved_at": t, "byte_size": len(raw),
                  "sha256": hashlib.sha256(raw).hexdigest()}


def itinerary(x, steps, mult=2):
    """Exact orbit of x under x -> mult*x mod 1; bit_t = 1 if x_t >= 1/2."""
    out = np.zeros(steps, dtype=np.uint8)
    for t in range(steps):
        out[t] = 1 if x >= HALF else 0
        x = x * mult
        x -= math.floor(x)
    return out


def long_division_bits(p, q, steps):
    out = np.zeros(steps, dtype=np.uint8)
    r = p % q
    for t in range(steps):
        r *= 2
        out[t] = r // q
        r %= q
    return out


def digits_to_fraction(bits):
    m = 0
    for b in bits:
        m = (m << 1) | int(b)
    return Fraction(m, 1 << len(bits))


def mult_order_2(q):
    k, r = 1, 2 % q
    while r != 1:
        r = (2 * r) % q
        k += 1
    return k


def orbit_period(x):
    """Minimal period of the purely periodic exact orbit of x under 2x mod 1."""
    seen = {x: 0}
    t = 0
    while True:
        x = 2 * x
        x -= math.floor(x)
        t += 1
        if x in seen:
            return t - seen[x], seen[x]
        seen[x] = t


def lzma_ratio(bits):
    s = "".join("1" if b else "0" for b in bits).encode()
    return len(lzma.compress(s, preset=9 | lzma.PRESET_EXTREME)) / len(s)


def serial_test_p(bits, m=8):
    """NIST serial test: nabla psi^2_m against chi-square with 2^(m-1) dof."""
    bits = np.asarray(bits, dtype=np.int64)
    n = len(bits)

    def psi2(mm):
        if mm == 0:
            return 0.0
        ext = np.concatenate([bits, bits[:mm - 1]])
        idx = np.zeros(n, dtype=np.int64)
        for j in range(mm):
            idx = (idx << 1) | ext[j:j + n]
        c = np.bincount(idx, minlength=1 << mm)
        return (1 << mm) / n * float((c.astype(float) ** 2).sum()) - n

    stat = psi2(m) - psi2(m - 1)
    return float(chi2_dist.sf(stat, 1 << (m - 1))), stat


def main():
    rng = np.random.default_rng(SEED)
    res = {}

    # (1a) random rationals: exact orbit itinerary vs long-division digits
    mism = 0
    total = 0
    for _ in range(N_FRACTIONS):
        while True:
            q = int(rng.integers(3, 100001))
            if q % 2 == 1:
                break
        p = int(rng.integers(1, q))
        g = math.gcd(p, q)
        p, q = p // g, q // g
        a = itinerary(Fraction(p, q), STEPS)
        b = long_division_bits(p, q, STEPS)
        mism += int((a != b).sum())
        total += STEPS
    res["rational_seeds"] = {"n_seeds": N_FRACTIONS, "steps": STEPS, "bits_compared": total,
                             "mismatches": mism}
    print("rational seeds:", res["rational_seeds"])

    # (1b) seeds whose digits come from OEIS b-files
    datasets = {}
    seeds = {}
    for name, url in OEIS.items():
        vals, meta = fetch_bfile(url)
        datasets[name] = meta
        if name == "A004539":
            # offset 1; a(1) = 1 is the integer part of sqrt(2); fractional digits follow.
            # The b-file has only 1000 terms, so all 999 fractional digits are used.
            nd = min(N_DIGITS, max(vals) - 1)
            d = [vals[k] for k in range(2, 2 + nd)]
            # independent digits of sqrt(2) - 1 by integer square root
            s = math.isqrt(2 << (2 * nd))  # floor(sqrt(2) * 2^nd)
            frac = s - (1 << nd)
            ind = [(frac >> (nd - 1 - i)) & 1 for i in range(nd)]
            res["sqrt2_isqrt_vs_oeis_mismatches"] = int(sum(1 for x, y in zip(d, ind) if x != y))
            print("sqrt2 isqrt vs OEIS mismatches:", res["sqrt2_isqrt_vs_oeis_mismatches"])
            s = math.isqrt(2 << (2 * N_DIGITS)) - (1 << N_DIGITS)
            sqrt2_full = np.array([(s >> (N_DIGITS - 1 - i)) & 1 for i in range(N_DIGITS)], dtype=np.uint8)
        else:
            nd = min(N_DIGITS, max(vals) + 1)
            d = [vals[k] for k in range(0, nd)]
        seeds[name] = np.array(d, dtype=np.uint8)
    oeis_res = {}
    for name, d in seeds.items():
        x = digits_to_fraction(d)
        it = itinerary(x, len(d))
        oeis_res[name] = {"digits": len(d), "mismatches": int((it != d).sum())}
    res["oeis_seeds"] = oeis_res
    print("oeis seeds:", oeis_res)

    # (2) periodic seeds: itinerary period = multiplicative order of 2 mod q
    exceptions = []
    max_period = 0
    for q in range(3, Q_MAX_PERIOD + 1, 2):
        per, pre = orbit_period(Fraction(1, q))
        o = mult_order_2(q)
        max_period = max(max_period, per)
        if per != o or pre != 0:
            exceptions.append([q, per, pre, o])
    dyadic_fail = []
    for k in range(1, K_MAX_DYADIC + 1):
        x = Fraction(1, 1 << k)
        t = 0
        while x != 0 and t <= k:
            x = 2 * x
            x -= math.floor(x)
            t += 1
        if x != 0 or t > k:
            dyadic_fail.append(k)
    res["periodic_seeds"] = {"odd_q_tested": len(range(3, Q_MAX_PERIOD + 1, 2)),
                             "period_exceptions": exceptions, "max_period": max_period,
                             "dyadic_k_tested": K_MAX_DYADIC, "dyadic_not_reaching_zero": dyadic_fail}
    print("periodic seeds:", res["periodic_seeds"])

    # (3) compressibility of seed digits vs itinerary
    ref = np.array([lzma_ratio(rng.integers(0, 2, N_DIGITS)) for _ in range(N_RANDOM_REF)])
    ref_pct = {"p1": float(np.percentile(ref, 1)), "p50": float(np.median(ref)),
               "p99": float(np.percentile(ref, 99))}
    classes = {}
    random_bits = rng.integers(0, 2, N_DIGITS).astype(np.uint8)
    seed_sets = {k: v for k, v in seeds.items() if len(v) == N_DIGITS}
    seed_sets["sqrt2_isqrt_digits"] = sqrt2_full
    seed_sets["random_bits"] = random_bits
    q_per = 1999  # largest odd q <= Q_MAX_PERIOD
    seed_sets["rational_1_over_%d" % q_per] = long_division_bits(1, q_per, N_DIGITS)
    seed_sets["rational_1_over_7"] = long_division_bits(1, 7, N_DIGITS)
    for name, d in seed_sets.items():
        it = itinerary(digits_to_fraction(d) if not name.startswith("rational")
                       else Fraction(1, int(name.split("_")[-1])), N_DIGITS)
        r_seed = lzma_ratio(d)
        r_it = lzma_ratio(it)
        p_it, _ = serial_test_p(it)
        classes[name] = {"seed_ratio": round(r_seed, 4), "itinerary_ratio": round(r_it, 4),
                         "abs_diff": round(abs(r_seed - r_it), 4),
                         "itinerary_equals_seed_digits": bool((it == d).all()),
                         "itinerary_serial_test_p": p_it}
    res["compression"] = {"random_reference": ref_pct, "classes": classes}
    print("compression:", json.dumps(res["compression"], indent=1))

    # (4) control: x -> 3x mod 1 from 1/2^60
    x0 = Fraction(1, 1 << 60)
    seed_digits = np.zeros(N_DIGITS, dtype=np.uint8)
    seed_digits[59] = 1
    it3 = itinerary(x0, N_DIGITS, mult=3)
    p3, stat3 = serial_test_p(it3)
    # The half-interval coding of 3x mod 1 is a Markov source: P(00) = P(11) = 1/3,
    # P(01) = P(10) = 1/6 for Lebesgue-typical orbits, so block counts are not uniform.
    pairs = np.bincount(2 * it3[:-1].astype(int) + it3[1:], minlength=4) / (len(it3) - 1)
    res["control_3x_mod_1"] = {"seed": "1/2^60", "seed_ratio": round(lzma_ratio(seed_digits), 4),
                               "pair_frequencies_00_01_10_11": [round(float(v), 4) for v in pairs],
                               "pair_frequencies_expected_markov": [1 / 3, 1 / 6, 1 / 6, 1 / 3],
                               "itinerary_ratio": round(lzma_ratio(it3), 4),
                               "itinerary_ratio_over_random_median": round(lzma_ratio(it3) / ref_pct["p50"], 4),
                               "ones_fraction": float(it3.mean()),
                               "serial_test_m8_stat": stat3, "serial_test_m8_p": p3}
    print("control:", res["control_3x_mod_1"])

    # float artefact (not part of the criteria)
    xf = 0.1
    t = 0
    while xf != 0.0 and t < 200:
        xf = (2 * xf) % 1.0
        t += 1
    res["float64_collapse_to_zero_steps_from_0.1"] = t

    res["datasets"] = datasets
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as f:
        json.dump(res, f, indent=1)


if __name__ == "__main__":
    main()
