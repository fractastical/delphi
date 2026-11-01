"""Test of maynardsmith-hitchhiking: is nucleotide diversity positively correlated with recombination rate along human chr22?

Reads data/ALL.chr22...genotypes.vcf.gz and data/genetic_map_HapMapII_GRCh37.tar.gz (run fetch.py first). Streams the VCF
without loading genotypes; uses INFO AF, VT and MULTI_ALLELIC. Writes derived/windows.csv and derived/summary.json.
"""
import gzip
import io
import json
import os
import tarfile

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
VCF = os.path.join(DATA, "ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz")
MAP_TAR = os.path.join(DATA, "genetic_map_HapMapII_GRCh37.tar.gz")
DERIVED = os.path.join(HERE, "derived")
WIN = 200_000
START = 16_000_000
MIN_SNPS = 200
N_CHROM = 5008


def read_map():
    with tarfile.open(MAP_TAR, "r:gz") as tf:
        member = [m for m in tf.getmembers() if m.name.endswith("chr22.txt")]
        if not member:
            raise SystemExit("chr22 map not found in tarball")
        txt = tf.extractfile(member[0]).read().decode()
    df = pd.read_csv(io.StringIO(txt), sep=r"\s+")
    pos_col = [c for c in df.columns if "Position" in c][0]
    cm_col = [c for c in df.columns if c.startswith("Map")][0]
    return df[pos_col].to_numpy(dtype=float), df[cm_col].to_numpy(dtype=float), member[0].name


def main():
    os.makedirs(DERIVED, exist_ok=True)
    pos_map, cm_map, map_name = read_map()
    het = {}  # window index -> sum of 2p(1-p)
    nsnp = {}
    n_total = n_kept = 0
    last_pos = 0
    corr = N_CHROM / (N_CHROM - 1)
    with gzip.open(VCF, "rt") as f:
        for line in f:
            if line[0] == "#":
                continue
            n_total += 1
            # Only the first 8 columns are needed; avoid splitting the 2504 genotype columns.
            p = line.split("\t", 8)
            pos = int(p[1]); alt = p[4]; filt = p[6]; info = p[7]
            if filt != "PASS" or "," in alt or "VT=SNP" not in info or "MULTI_ALLELIC" in info:
                continue
            af = None
            for tok in info.split(";"):
                if tok.startswith("AF="):
                    af = float(tok[3:].split(",")[0]); break
            if af is None or af <= 0 or af >= 1:
                continue
            if pos < START:
                continue
            w = (pos - START) // WIN
            het[w] = het.get(w, 0.0) + 2 * af * (1 - af) * corr
            nsnp[w] = nsnp.get(w, 0) + 1
            n_kept += 1
            last_pos = pos
    rows = []
    for w in sorted(het):
        s = START + w * WIN
        e = s + WIN
        cm_s, cm_e = np.interp([s, e], pos_map, cm_map)
        rows.append({"window_start": s, "window_end": e, "n_snps": nsnp[w], "pi": het[w] / WIN, "rec_rate_cM_per_Mb": (cm_e - cm_s) / (WIN / 1e6),
                     "assessable": nsnp[w] >= MIN_SNPS and e <= last_pos + WIN})
    df = pd.DataFrame(rows)
    a = df[df["assessable"]]
    rho, p = stats.spearmanr(a["pi"], a["rec_rate_cM_per_Mb"])
    r, pr = stats.pearsonr(a["pi"], a["rec_rate_cM_per_Mb"])
    n = len(a)
    if rho >= 0.2 and p < 0.01:
        verdict = "supports"
    elif (rho < 0 and p < 0.05) or (abs(rho) < 0.1 and p > 0.05 and n >= 100):
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary = {"map_file": map_name, "n_vcf_records": n_total, "n_snps_used": n_kept, "n_windows_total": int(len(df)), "n_windows_assessable": int(n),
               "spearman_rho": float(rho), "spearman_p": float(p), "pearson_r": float(r), "pearson_p": float(pr),
               "median_pi": float(a["pi"].median()), "median_rec_rate": float(a["rec_rate_cM_per_Mb"].median()),
               "pi_quartile_by_rec_rate": {str(k): float(v) for k, v in a.groupby(pd.qcut(a["rec_rate_cM_per_Mb"], 4, labels=["Q1 low", "Q2", "Q3", "Q4 high"]), observed=True)["pi"].median().items()},
               "verdict": verdict}
    df.to_csv(os.path.join(DERIVED, "windows.csv"), index=False)
    json.dump(summary, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
