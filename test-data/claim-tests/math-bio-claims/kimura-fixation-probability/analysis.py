"""Test of kimura-fixation-probability on Buri's (1956) 107 replicate Drosophila populations (bw75 at initial frequency 0.5).

Reads derived/buri1956_fly.csv (written by fetch.py from the CRAN popgenr tarball). The popgenr 'fly' object is a
generation x allele-count table: row g holds, for each possible number of bw75 copies k = 0..32, how many of the 107 lines
had k copies in generation g. 'Fixed' = k = 32, 'lost' = k = 0 at the last recorded generation. Writes derived/summary.json.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "derived", "buri1956_fly.csv")


def main():
    d = pd.read_csv(CSV)
    counts = d.drop(columns=["generation"]).to_numpy(dtype=float)
    n_gen, n_k = counts.shape
    if n_k != 33:
        raise SystemExit(f"expected 33 allele-count columns (k = 0..32), found {n_k}")
    k = np.arange(33)
    row_tot = counts.sum(axis=1)
    last = counts[-1]
    fixed = int(last[32])
    lost = int(last[0])
    m = fixed + lost
    p_binom = float(stats.binomtest(fixed, m, 0.5).pvalue) if m > 0 else None
    frac = fixed / m if m > 0 else None
    mean_freq_last = float((counts[-1] * k).sum() / (row_tot[-1] * 32))
    mean_freq_first = float((counts[0] * k).sum() / (row_tot[0] * 32))
    # Heterozygosity decay across generations gives an effective size, reported for context only.
    H = []
    for g in range(n_gen):
        pk = k / 32
        w = counts[g] / row_tot[g]
        H.append(float(np.sum(w * 2 * pk * (1 - pk))))
    gens = np.arange(n_gen)
    sl = stats.linregress(gens[1:], np.log(np.array(H[1:])))
    ne_from_H = float(-1 / (2 * (np.exp(sl.slope) - 1))) if sl.slope < 0 else None
    if m < 20:
        verdict = "inconclusive"
    elif p_binom > 0.05 and abs(frac - 0.5) < 0.15:
        verdict = "supports"
    elif p_binom < 0.01 or abs(frac - 0.5) >= 0.25:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary = {
        "n_generations_recorded": int(n_gen), "lines_per_generation": [int(x) for x in row_tot],
        "fixed_bw75_last_gen": fixed, "lost_bw75_last_gen": lost, "m_fixed_or_lost": m, "fraction_fixed_bw75": frac,
        "binomial_two_sided_p": p_binom, "mean_bw75_frequency_first_gen": mean_freq_first, "mean_bw75_frequency_last_gen": mean_freq_last,
        "heterozygosity_by_generation": H, "ne_from_heterozygosity_decay": ne_from_H, "verdict": verdict,
    }
    json.dump(summary, open(os.path.join(HERE, "derived", "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
