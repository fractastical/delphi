#!/usr/bin/env python3
"""Test of wolfram2002-ch02-17: in which pre-declared respects do the primes below 10^8 look
random, compared with Cramer's model? Fetches two OEIS b-files for validation.
Writes derived/measurements.json.
"""
import datetime
import hashlib
import json
import lzma
import math
import os
import sys

import numpy as np
from scipy.special import expi
from scipy.stats import poisson

HERE = os.path.dirname(os.path.abspath(__file__))
N = 10 ** 8
SEED = 20261031
OEIS = {"A000040": "https://oeis.org/A000040/b000040.txt", "A006880": "https://oeis.org/A006880/b006880.txt"}


def sieve(n):
    s = np.ones(n, dtype=bool)
    s[:2] = False
    for p in range(2, int(n ** 0.5) + 1):
        if s[p]:
            s[p * p::p] = False
    return np.flatnonzero(s)


def cramer(n, rng):
    """Positions in [3, n) that are 'prime' in Cramer's model, chunked."""
    out = []
    for lo in range(3, n, 10 ** 7):
        hi = min(n, lo + 10 ** 7)
        x = np.arange(lo, hi, dtype=np.float64)
        hit = rng.random(hi - lo) < 1.0 / np.log(x)
        out.append(np.flatnonzero(hit) + lo)
    return np.concatenate([np.array([2])] + out)


def li(x):
    return expi(np.log(x))


def fetch(url):
    import requests
    r = requests.get(url, timeout=60, headers={"User-Agent": "delphi-claim-tests/1.0"})
    r.raise_for_status()
    data = r.content
    terms = [tuple(map(int, line.split())) for line in data.decode().splitlines() if line.strip() and not line.startswith("#")]
    meta = {"download_url": url, "retrieved_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return meta, terms


# ------------------------------------------------------------- the respects
def respects(p, label):
    """p: sorted array of 'primes' in [2, N). Returns dict of statistics."""
    w = p[(p >= N // 2) & (p < N)]
    gaps = np.diff(w).astype(np.int64)
    mean_gap = gaps.mean()
    out = {"n_in_window": int(len(w)), "mean_gap": float(mean_gap)}

    # R1 coarse gap CDF versus exponential
    js = np.arange(1, int(gaps.max() // 30) + 1)
    f_emp = np.searchsorted(np.sort(gaps), 30 * js, side="right") / len(gaps)
    f_exp = 1 - np.exp(-30 * js / mean_gap)
    out["R1_coarse_gap_cdf_maxdev"] = float(np.max(np.abs(f_emp - f_exp)))
    out["R1_coarse_gap_cdf_first_points"] = [[int(30 * j), round(float(a), 4), round(float(b), 4)] for j, a, b in zip(js[:4], f_emp[:4], f_exp[:4])]

    # R2 consecutive gap correlation
    out["R2_consecutive_gap_corr"] = float(np.corrcoef(gaps[:-1], gaps[1:])[0, 1])

    # R3 residues coprime to 12
    r = p % 12
    cop = p[np.isin(r, [1, 5, 7, 11])]
    shares = np.array([np.mean(cop % 12 == c) for c in (1, 5, 7, 11)])
    out["R3_coprime12_shares"] = shares.tolist()
    out["R3_coprime12_maxdev"] = float(np.max(np.abs(shares - 0.25)))

    # R4 counts in intervals of length H
    H = int(round(math.log(N)))
    edges = np.arange(N // 2, N + 1, H)
    counts = np.diff(np.searchsorted(w, edges))
    lam = counts.mean()
    kmax = counts.max()
    emp = np.bincount(counts, minlength=kmax + 1) / len(counts)
    theo = poisson.pmf(np.arange(kmax + 1), lam)
    out["R4_interval_length"] = H
    out["R4_mean_count"] = float(lam)
    out["R4_fano_factor"] = float(counts.var() / lam)
    out["R4_poisson_tv"] = float(0.5 * (np.abs(emp - theo).sum() + (1 - theo.sum())))

    # R5 Fourier of the indicator over odd numbers just below N
    L = 1 << 22
    odd = np.arange(N - 2 * L + 1, N, 2)
    ind = np.zeros(L, dtype=np.float64)
    inset = np.isin(odd, p)
    ind[inset] = 1.0
    ind -= ind.mean()
    power = np.abs(np.fft.rfft(ind)[1:]) ** 2
    out["R5_fourier_max_over_mean"] = float(power.max() / power.mean())
    out["R5_fourier_peak_share_of_total"] = float(power.max() / power.sum())
    kpk = int(np.argmax(power)) + 1
    out["R5_fourier_peak_frequency_cycles_per_odd"] = kpk / L
    out["R5_fourier_peak_period_in_odd_numbers"] = L / kpk

    # R6 sequential compressibility of half-gaps
    hg = np.clip(gaps // 2, 0, 255).astype(np.uint8).tobytes()
    rng = np.random.default_rng(SEED + 1)
    perm = np.frombuffer(hg, dtype=np.uint8)[rng.permutation(len(hg))].tobytes()
    c_real = len(lzma.compress(hg, preset=9 | lzma.PRESET_EXTREME))
    c_perm = len(lzma.compress(perm, preset=9 | lzma.PRESET_EXTREME))
    out["R6_lzma_ratio_vs_shuffled"] = c_real / c_perm
    out["R6_lzma_ratio_raw"] = c_real / len(hg)

    # R7 pi(x) - Li(x) fluctuation scale
    xs = np.unique(np.concatenate([np.logspace(1, 8, 2000), np.array([N - 1], dtype=float)]))
    xs = xs[xs >= 10]
    pix = np.searchsorted(p, xs, side="right")
    dev = (pix - li(xs)) / np.sqrt(xs / np.log(xs))
    out["R7_max_abs_scaled_dev"] = float(np.max(np.abs(dev)))
    out["R7_scaled_dev_at_N"] = float(dev[-1])
    out["R7_pi_minus_li_at_N"] = float(pix[-1] - li(xs[-1]))
    return out


THRESHOLDS = {
    "R1_coarse_gap_cdf_maxdev": ("<", 0.03), "R2_consecutive_gap_corr": ("abs<", 0.05), "R3_coprime12_maxdev": ("<", 0.005),
    "R4_poisson_tv": ("<", 0.02), "R5_fourier_max_over_mean": ("<", 30), "R6_lzma_ratio_vs_shuffled": (">=", 0.98), "R7_max_abs_scaled_dev": ("<", 3),
}


def passes(stats):
    out = {}
    for k, (op, thr) in THRESHOLDS.items():
        v = stats[k]
        out[k] = bool(v < thr) if op == "<" else (bool(abs(v) < thr) if op == "abs<" else bool(v >= thr))
    return out


def main():
    print("sieving", flush=True)
    primes = sieve(N)
    validation = {"pi_1e8": int(len(primes)), "pi_1e8_published": 5761455, "pi_match": int(len(primes)) == 5761455}
    files = {}
    try:
        meta, terms = fetch(OEIS["A000040"])
        files["A000040"] = meta
        k = min(len(terms), 10000)
        validation["A000040_terms_in_bfile"] = len(terms)
        validation["A000040_first_10000_match"] = bool(np.array_equal(primes[:k], np.array([v for _, v in terms[:k]])))
        meta, terms = fetch(OEIS["A006880"])
        files["A006880"] = meta
        validation["A006880_pi_1e8"] = int(dict(terms)[8])
        validation["pi_match_oeis"] = validation["A006880_pi_1e8"] == int(len(primes))
        validation["oeis_status"] = "ok"
    except Exception as e:  # noqa: BLE001
        validation["oeis_status"] = f"fetch-failed: {e}"
    print("validation:", validation, flush=True)

    print("simulating Cramer model", flush=True)
    cr = cramer(N, np.random.default_rng(SEED))
    print("statistics (primes)", flush=True)
    s_real = respects(primes, "primes")
    print("statistics (Cramer)", flush=True)
    s_cr = respects(cr, "cramer")
    p_real, p_cr = passes(s_real), passes(s_cr)
    calibrated = [k for k in THRESHOLDS if p_cr[k]]
    n_cal = len(calibrated)
    n_pass = sum(p_real[k] for k in calibrated)
    plainly_regular = s_real["R6_lzma_ratio_raw"] < 0.1 or s_real["R5_fourier_peak_share_of_total"] > 0.5
    if validation.get("oeis_status") == "ok" and not (validation["A000040_first_10000_match"] and validation["pi_match_oeis"]):
        verdict = "inconclusive"
    elif plainly_regular or n_pass <= n_cal - 4:
        verdict = "refutes"
    elif n_pass >= n_cal - 2:
        verdict = "supports"
    else:
        verdict = "mixed"
    res = {"N": N, "validation": validation, "oeis_files": files, "primes": s_real, "cramer": s_cr,
           "random_like_primes": p_real, "random_like_cramer": p_cr, "calibrated_respects": calibrated,
           "n_calibrated": n_cal, "n_random_like": n_pass, "plainly_regular": plainly_regular, "verdict": verdict}
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measurements.json"), "w") as f:
        json.dump(res, f, indent=1)
    print(json.dumps(res, indent=1))


if __name__ == "__main__":
    sys.exit(main())
