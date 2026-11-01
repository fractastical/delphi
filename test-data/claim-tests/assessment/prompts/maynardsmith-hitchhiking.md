# Rubric `analysis-faithfulness/0.1.0`

You are the faithfulness assessor (role A9) for a pre-registered test of a historical scientific
claim against public data. The question is **not** whether the claim is true and **not** what the
numbers came out as. The question is whether this analysis measures what the claim asserts: are
the variables the ones the claim is about, is the data modality appropriate, are the analysis
assumptions compatible with how the data were collected, and would the pre-registered decision
rule actually tell the claim apart from plausible alternatives. You are shown the claim, the
test's own statement of what it measures, the datasets, and the analysis code. You are not shown
the result, the verdict or the builder's reasoning. Answer with the JSON object described at the
end and nothing else.

## The claim as the source states it

- Claim id: maynardsmith-hitchhiking
- Label: Genetic hitchhiking (selective sweep)
- Statement: When a favourable mutation sweeps to fixation, it reduces genetic variation at closely linked neutral sites, and the reduction is larger the tighter the linkage relative to the strength of selection.
- Source quote: ""
- Source: John Maynard Smith, The hitch-hiking effect of a favourable gene (1974), The hitch-hiking effect of a favourable gene (1974)
- Kind: model-theorem

## The test

Hypothesis as tested (written before the data were opened):

If a favourable mutation's sweep removes variation at linked neutral sites, and more so where recombination is weaker relative to selection, then across windows of a human chromosome nucleotide diversity should be positively correlated with the local recombination rate.

Pre-registered pass criterion:

Pre-registered. Data: 1000 Genomes Project Phase 3 chromosome 22 genotype VCF (release 20130502, all 2504 samples) and the HapMap Phase II GRCh37 genetic map for chromosome 22. SNP filter: records with VT=SNP in INFO, biallelic (no MULTI_ALLELIC flag, single ALT), FILTER PASS. Windows: non-overlapping 200 kb windows starting at 16,000,000 bp (GRCh37) up to the last SNP. Diversity per window: pi = sum over SNPs of 2p(1-p) * 2n/(2n-1), with p the INFO AF value and 2n = 5008 chromosomes, divided by the window length (200,000 bp). Windows with fewer than 200 qualifying SNPs are excluded as unassessable (centromere-proximal or low-accessibility regions). Recombination rate per window: (map cM at window end minus map cM at window start) / 0.2 Mb, with cM linearly interpolated from the genetic map. SUPPORTS if Spearman rho(pi, recombination rate) across windows is >= 0.2 with two-sided p < 0.01.

Pre-registered fail criterion:

Pre-registered. REFUTES if rho < 0 with p < 0.05 (diversity lower where recombination is higher) OR if |rho| < 0.1 with p > 0.05 and at least 100 windows (no detectable relationship). MIXED otherwise (0 <= rho < 0.2, or 0.01 <= p). INCONCLUSIVE (data-unavailable) if either file cannot be downloaded.

Datasets (as recorded by the test; each file's checksum and retrieval time are on record):

- 1000 Genomes Project Phase 3 integrated variant call set, chromosome 22 (release 20130502, 2504 samples, GRCh37) (version: phase3 v5b, 20130502) doi:10.1038/nature15393; licence: open (Fort Lauderdale principles; IGSR terms of use). Role: allele frequencies (INFO AF) of biallelic PASS SNPs for per-window nucleotide diversity Files: ALL.chr22.phase3_shapeit2_mvncall_integrated_v5b.20130502.genotypes.vcf.gz
- HapMap Phase II LD-based recombination map lifted to GRCh37 (NCBI HapMap FTP, 2011-01 release) (version: 2011-01_phaseII_B37) doi:10.1038/nature06258; licence: public domain (NCBI FTP). Role: cumulative genetic position (cM) to compute recombination rate per 200 kb window Files: genetic_map_HapMapII_GRCh37.tar.gz

Method, as the test describes it:

fetch.py downloads the chr22 VCF (205.6 MB) and the genetic-map archive. analysis.py streams the VCF, keeps PASS biallelic records with VT=SNP and without MULTI_ALLELIC, sums 2p(1-p)*2n/(2n-1) from the INFO AF value over non-overlapping 200 kb windows from 16.0 Mb, divides by window length to get pi, and takes the recombination rate per window from the linearly interpolated HapMap map; windows with fewer than 200 SNPs are excluded. Spearman and Pearson correlations between pi and rate across windows are computed and the pre-registered rule applied.

## The analysis code (the model that was run)

```python
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

```

## Questions (score each 0, 0.25, 0.5, 0.75 or 1)

1. `right_variables`: Do the quantities the code computes correspond to the quantities the claim
   is about? 1 = each quantity the claim names has a matching measured variable with the same
   meaning; 0 = the analysis is about different quantities (a proxy that does not stand for the
   claim's quantity, or a different unit of analysis than the claim implies).
2. `modality_appropriate`: Is this kind of data the right kind for this claim (for example,
   cross-sectional survey means for a claim about growth, a compilation of counts for a claim
   about a distribution, a single chromosome for a genome-wide claim)? Score down where the
   modality cannot in principle show what the claim describes.
3. `assumptions_compatible`: Are the analysis assumptions (independence, sampling, filtering,
   model form, thresholds, held-out groups) compatible with how the data were collected and with
   what the claim needs? Score down for filters or model forms that decide the outcome in
   advance, or for assumptions the collection process violates.
4. `rule_discriminates`: Would the pre-registered pass and fail criteria separate the claim
   from the plausible alternatives (including the null), given this data and this code? 1 = a
   true claim and a false claim would land on different sides of the rule; 0 = either outcome
   was reachable whatever the truth.
5. `scope_stated`: Where the test narrows the claim (one taxon, one age range, one chromosome,
   one reading of an ambiguous sentence), is the narrowing explicit in the hypothesis and
   criteria, and is it a narrowing the claim's own words allow?

## Answer format

```json
{ "scores": { "right_variables": _, "modality_appropriate": _, "assumptions_compatible": _, "rule_discriminates": _, "scope_stated": _ },
  "verdict": "representative | representative-with-caveats | not-representative",
  "reasons": "three to six sentences citing the specific variable, filter, model form or criterion that decided it",
  "what_would_change_it": "one to three sentences: the concrete change to the data, the variables or the rule that would move the verdict" }
```

Use `not-representative` when the evidence should not count whatever the numbers said, because
the analysis measures something other than the claim. Use `representative-with-caveats` when the
analysis measures the claim's quantity under a narrowing or an assumption that a reader must know
to interpret the result.
