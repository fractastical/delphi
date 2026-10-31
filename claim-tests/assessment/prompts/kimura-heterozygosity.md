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

- Claim id: kimura-heterozygosity
- Label: Neutral equilibrium heterozygosity (Kimura-Crow)
- Statement: Under neutral mutation to new alleles and drift, expected heterozygosity reaches an equilibrium that rises with the product of effective population size and mutation rate.
- Source quote: ""
- Source: Motoo Kimura, The number of alleles that can be maintained in a finite population (1964), The number of alleles that can be maintained in a finite population (1964)
- Kind: model-theorem

## The test

Hypothesis as tested (written before the data were opened):

If neutral equilibrium heterozygosity H = theta/(1+theta) with theta = 4*Ne*mu holds and effective size scales with census size across species, then genome-wide nucleotide diversity (pi, the per-site heterozygosity) across metazoan species rises with census population size N: for pi << 1, H is approximately 4*Ne*mu, so log10(pi) should increase with log10(N) with a slope near 1 when mu and Ne/N are comparable across species, and the rank correlation between pi and N should be strongly positive.

Pre-registered pass criterion:

Pre-registered. Data: Buffalo (2021) combined_data.tsv from github.com/vsbuffalo/paradox_variation (commit b8f91d5, 2021-09-27), metazoan species (kingdom == Animalia) with a non-missing diversity value (pairwise nucleotide diversity, column 'diversity') and a non-missing census-size estimate (column 'log10_popsize', the posterior mean of log10 census size from the author's range x density model; if the file carries another census-size point estimate instead, the column actually used is recorded in 'method'). One row per species. SUPPORTS if Spearman rho(log10 pi, log10 N) > 0.5 with p < 0.001 AND the ordinary-least-squares slope of log10 pi on log10 N has a point estimate >= 0.3 with a 95% confidence interval that includes some value >= 0.5 (diversity rises at least about a third as fast as census size on a log scale, i.e. within a factor of about 3 of the law's slope of 1). AMENDMENT (2026-10-31, before any data were downloaded, at the request of the holdout thread): species of class Aves are excluded from the primary analysis and from all criteria above; bird rows are held out and only reported separately, unfitted, as a holdout check. The taxonomic class is taken from the file's own taxonomy columns.

Pre-registered fail criterion:

Pre-registered. REFUTES if the 95% confidence interval of the slope lies entirely below 0.25 (diversity rises less than a quarter as fast as census size on a log scale, so the law with N as the proxy for Ne is quantitatively wrong by orders of magnitude across the range of N: the Lewontin's-paradox pattern) OR rho <= 0. MIXED otherwise. INCONCLUSIVE (underpowered) if fewer than 50 species qualify; INCONCLUSIVE (data-unavailable) if the file cannot be downloaded.

Datasets (as recorded by the test; each file's checksum and retrieval time are on record):

- Buffalo (2021) 'Why do species get a thin slice of pi?' combined species table: pairwise nucleotide diversity (collated from Leffler et al. 2012, Romiguier et al. 2014, Corbett-Detig et al. 2015) and census population size estimates (range x density model) for 300 metazoan species (version: git commit b8f91d5c34675733db8cae8dcab625dcbb55c30a (2021-09-27)) doi:10.7554/eLife.67509; licence: not stated in the repository; the article is CC BY 4.0. Role: per-species diversity (column 'diversity') and log10 census size (column 'log10_popsize', posterior mean) Files: combined_data.tsv

Method, as the test describes it:

fetch.py downloads combined_data.tsv at the pinned commit. analysis.py keeps Animalia rows with a diversity value > 0 and a log10_popsize value (one row per species), drops the 13 class-Aves species (held out, never fitted), and on the remaining species computes Spearman rho between log10 diversity and log10 census size and an ordinary-least-squares regression of log10 diversity on log10 census size with a t-based 95% confidence interval on the slope. The decision rule is the pre-registered one.

## The analysis code (the model that was run)

```python
"""Test of kimura-heterozygosity: does nucleotide diversity rise with census population size across metazoa?

Reads data/combined_data.tsv (run fetch.py first). Writes derived/species_table.csv and derived/summary.json.
Primary analysis excludes class Aves (held out); bird rows are reported separately and are not fitted.
"""
import json
import os
import sys

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "combined_data.tsv")
DERIVED = os.path.join(HERE, "derived")


def fit(d):
    x = d["log10_popsize"].to_numpy()
    y = np.log10(d["diversity"].to_numpy())
    rho, p_rho = stats.spearmanr(x, y)
    ols = stats.linregress(x, y)
    tcrit = stats.t.ppf(0.975, len(d) - 2)
    return {
        "n_species": int(len(d)),
        "spearman_rho": float(rho),
        "spearman_p": float(p_rho),
        "ols_slope": float(ols.slope),
        "ols_slope_se": float(ols.stderr),
        "ols_slope_ci95": [float(ols.slope - tcrit * ols.stderr), float(ols.slope + tcrit * ols.stderr)],
        "ols_intercept": float(ols.intercept),
        "pearson_r": float(ols.rvalue),
        "log10_N_range": [float(x.min()), float(x.max())],
        "log10_pi_range": [float(y.min()), float(y.max())],
    }


def main():
    os.makedirs(DERIVED, exist_ok=True)
    d = pd.read_csv(DATA, sep="\t")
    d = d[(d["kingdom"] == "Animalia") & d["diversity"].notna() & d["log10_popsize"].notna()].copy()
    d = d[(d["diversity"] > 0)]
    d = d.drop_duplicates(subset="species")
    birds = d[d["class"] == "Aves"].copy()
    main_d = d[d["class"] != "Aves"].copy()
    res = fit(main_d)
    # Holdout: class Aves is exam data. Bird rows are never fitted, and their residuals from the main fit are computed only
    # when the holdout thread runs this script with --exam, after building has stopped.
    holdout = {"n_bird_species_held_out": int(len(birds)), "note": "class Aves excluded from fitting at the holdout thread's request; scored only with --exam"}
    if "--exam" in sys.argv[1:]:
        pred_birds = res["ols_intercept"] + res["ols_slope"] * birds["log10_popsize"].to_numpy()
        holdout["bird_mean_residual_log10_pi_from_main_fit"] = float(np.mean(np.log10(birds["diversity"].to_numpy()) - pred_birds)) if len(birds) else None
        holdout["bird_species"] = birds[["species", "diversity", "log10_popsize"]].to_dict("records")
    # Pre-registered decision rule.
    lo, hi = res["ols_slope_ci95"]
    if res["n_species"] < 50:
        verdict = "inconclusive"
    elif res["spearman_rho"] > 0.5 and res["spearman_p"] < 0.001 and res["ols_slope"] >= 0.3 and hi >= 0.5:
        verdict = "supports"
    elif hi < 0.25 or res["spearman_rho"] <= 0:
        verdict = "refutes"
    else:
        verdict = "mixed"
    summary = {"main": res, "holdout_aves": holdout, "verdict": verdict,
               "diversity_sources": main_d["diversity_data_source"].value_counts(dropna=False).to_dict(),
               "classes_in_main": main_d["class"].value_counts(dropna=False).to_dict()}
    cols = ["species", "phylum", "class", "diversity", "diversity_data_source", "log10_popsize", "log10_range", "log10_body_mass", "log10_density"]
    d.assign(held_out=(d["class"] == "Aves"))[cols + ["held_out"]].sort_values("log10_popsize").to_csv(os.path.join(DERIVED, "species_table.csv"), index=False)
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
