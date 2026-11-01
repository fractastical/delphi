#!/usr/bin/env python3
"""Test of levin-2025-wisdom-05 (and levin-2023-agential-15): barium-adapted planarian heads
change expression of only a handful of genes.

GEO GSE98084 (Dugesia japonica heads, 2 control vs 2 BaCl2-adapted). The deposit has per-replicate
FPKM in two files (control_i vs BaCl2_i) and the authors' pooled Cuffdiff table. Per transcript:
Welch t-test on log2(FPKM+1) across the four samples, transcripts with mean FPKM >= 1 in either
group, Benjamini-Hochberg FDR; count FDR < 0.05 and |log2FC| >= 1. Thresholds are in result.json.

Needs: numpy, scipy, requests (fetch.py). Run: python3 analysis.py   (downloads data/ if missing)
"""
import json
import os

import numpy as np
from scipy import stats

from xlsx import read_rows

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
FILES = ["GSE98084_All_Data_BaCl2.xlsx", "GSE98084_FPKM_Replicate_1.xlsx", "GSE98084_FPKM_Replicate_2.xlsx"]


def table(name):
    rows = read_rows(os.path.join(DATA, name))
    head = rows[0]
    return [dict(zip(head, r)) for r in rows[1:] if r and r[0]]


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def bh(p):
    p = np.asarray(p)
    n = len(p)
    order = np.argsort(p)
    q = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def count_de(fdr, lfc, p=None):
    return int(np.sum((fdr < 0.05) & (np.abs(lfc) >= 1)))


def main():
    if not all(os.path.exists(os.path.join(DATA, f)) for f in FILES):
        import fetch
        fetch.main()
    pooled = table(FILES[0])
    r1 = {r["Transcript_id"]: r for r in table(FILES[1])}
    r2 = {r["Transcript_id"]: r for r in table(FILES[2])}
    common = sorted(set(r1) & set(r2))

    wt = np.array([[num(r1[t]["FPKM_WildType_Head_1"]), num(r2[t]["FPKM_WildType_Head_2"])] for t in common])
    ba = np.array([[num(r1[t]["FPKM_BaCl2_Head_1"]), num(r2[t]["FPKM_BaCl2_Head_2"])] for t in common])
    ok = np.isfinite(wt).all(1) & np.isfinite(ba).all(1)
    expressed = ok & ((wt.mean(1) >= 1) | (ba.mean(1) >= 1))
    lw, lb = np.log2(wt[expressed] + 1), np.log2(ba[expressed] + 1)
    lfc = lb.mean(1) - lw.mean(1)
    with np.errstate(all="ignore"):
        t, p = stats.ttest_ind(lb, lw, axis=1, equal_var=False)
    p = np.where(np.isfinite(p), p, 1.0)
    fdr = bh(p)
    n_tested = int(expressed.sum())
    n_de = count_de(fdr, lfc)
    n_nominal = int(np.sum((p < 0.01) & (np.abs(lfc) >= 1)))
    n_lfc1_both = int(np.sum((np.sign(lb[:, 0] - lw[:, 0]) == np.sign(lb[:, 1] - lw[:, 1]))
                             & (np.abs(lb[:, 0] - lw[:, 0]) >= 1) & (np.abs(lb[:, 1] - lw[:, 1]) >= 1)))

    pq = np.array([num(r["q_value"]) for r in pooled])
    pl = np.array([num(r["log2(fold_change)"]) for r in pooled])
    pw = np.array([num(r["FPKM_WildType_Head"]) for r in pooled])
    pb = np.array([num(r["FPKM_BaCl2_Head"]) for r in pooled])
    pexp = (pw >= 1) | (pb >= 1)
    pooled_de = int(np.sum((pq < 0.05) & (np.abs(pl) >= 1)))
    pooled_de_expr = int(np.sum((pq < 0.05) & (np.abs(pl) >= 1) & pexp))
    pooled_up = int(np.sum((pq < 0.05) & (pl >= 1)))
    pooled_down = int(np.sum((pq < 0.05) & (pl <= -1)))
    rep_q = {}
    for k, rr in (("replicate_1", r1), ("replicate_2", r2)):
        q = np.array([num(v["q_value"]) for v in rr.values()])
        l = np.array([num(v["log2(fold_change)"]) for v in rr.values()])
        rep_q[k] = int(np.sum((q < 0.05) & (np.abs(l) >= 1)))

    frac = n_de / n_tested
    verdict = ("supports" if n_de <= 20 and frac <= 0.002 else "refutes" if n_de >= 100 else "mixed")
    out = {
        "value": n_de,
        "unit": "transcripts with BH FDR < 0.05 and |log2FC| >= 1, BaCl2-adapted vs control heads (Welch t on log2(FPKM+1), 2 vs 2)",
        "n": n_tested,
        "uncertainty": "2 replicates per group; Welch t-test has ~1-2 degrees of freedom and very low power",
        "extra": {
            "transcripts_in_both_replicate_files": len(common),
            "transcripts_tested_mean_fpkm_ge_1": n_tested,
            "fraction_de": round(frac, 6),
            "min_fdr": float(f"{fdr.min():.4g}"),
            "sensitivity_nominal_p_lt_0.01_and_abs_log2fc_ge_1": n_nominal,
            "sensitivity_same_direction_2fold_in_both_replicate_pairs": n_lfc1_both,
            "authors_pooled_cuffdiff_q_lt_0.05_abs_log2fc_ge_1": pooled_de,
            "authors_pooled_cuffdiff_q_lt_0.05_abs_log2fc_ge_1_fpkm_ge_1": pooled_de_expr,
            "authors_pooled_cuffdiff_up": pooled_up,
            "authors_pooled_cuffdiff_down": pooled_down,
            "authors_pooled_transcripts": len(pooled),
            "authors_per_replicate_cuffdiff_q_lt_0.05_abs_log2fc_ge_1": rep_q,
            "verdict_by_preregistered_rule": verdict,
        },
    }
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived", "measured.json"), "w") as fh:
        json.dump(out, fh, indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
