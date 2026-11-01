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

- Claim id: thompson1917-ch04-13
- Label: Chromosome numbers of germ-nuclei mostly lie between six and sixteen
- Statement: Although chromosome number is constant within a species, the range of numbers across plants and animals is small: few organisms have fewer than six chromosomes in the germ-nuclei and fewer still have more than sixteen.
- Source quote: "(as regards the germ-nuclei) few organisms have less than six chromosomes, and fewer still have more than sixteen"
- Source: D'Arcy Wentworth Thompson, On Growth and Form (1917), Ch. IV: On the Internal Form and Structure of the Cell
- Kind: empirical-generalization

## The test

Hypothesis as tested (written before the data were opened):

If chromosome numbers of germ-nuclei mostly lie between six and sixteen, with few below six and fewer still above sixteen, then across plant species the haploid (gametic) number n has most of its mass in 6 <= n <= 16, a small lower tail (n < 6) and a still smaller upper tail (n > 16).

Pre-registered pass criterion:

Pre-registered. Data: the Chromosome Counts Database (CCDB, Rice et al. 2015), 'statistics' API output (one row per resolved species name with the median gametophytic/sporophytic counts) retrieved per major group (Angiosperms, Gymnosperms, Pteridophytes, Bryophytes) in CSV. One n per species: the median resolved gametophytic count; where only a sporophytic (2n) count is given, n = 2n/2; species with no usable count excluded. SUPPORTS if all three hold: (a) at least 70% of species have 6 <= n <= 16; (b) fewer than 15% have n < 6; (c) the share with n > 16 is smaller than the share with n < 6.

Pre-registered fail criterion:

Pre-registered. REFUTES if any holds: fewer than 50% of species have 6 <= n <= 16; the share with n > 16 is >= the share with n < 6; or the share with n > 16 is >= 15%. MIXED otherwise. INCONCLUSIVE (data-unavailable) if the API cannot be read; INCONCLUSIVE (underpowered) if fewer than 1000 species have a usable n.

Datasets (as recorded by the test; each file's checksum and retrieval time are on record):

- Chromosome Counts Database (CCDB, Rice et al. 2015), 'statistics' API output per major plant group (one row per resolved species name with minimum, median and maximum count) (version: live database as served 2026-10-31) doi:10.1111/nph.13191; licence: not stated on the site; community database, cite the paper. Role: median gametophytic (n) count per species Files: ?majorGroup=Angiosperms&format=csv, ?majorGroup=Gymnosperms&format=csv, ?majorGroup=Pteridophytes&format=csv, ?majorGroup=Bryophytes&format=csv

Method, as the test describes it:

fetch.py downloads four CSV files (2.7 MB). analysis.py takes the median count per resolved species name, confirms on six reference species (Arabidopsis n=5, maize 10, wheat 21, rice 12, Scots pine 12, silver fir 12) that the column is at the haploid level, drops duplicates and non-numeric rows, and computes the shares of species with n < 6, 6 <= n <= 16 and n > 16, overall and by major group. The pre-registered rule is applied.

## The analysis code (the model that was run)

```python
"""Test of thompson1917-ch04-13 (germ-nucleus chromosome numbers mostly 6 to 16) on the Chromosome Counts Database (plants).

Reads data/ccdb_statistics_<group>.csv (run fetch.py first): one row per resolved species name with the median count.
CCDB 'statistics' counts are at the gametophytic (n) level (checked on reference species listed in derived/summary.json).
Writes derived/n_distribution.csv and derived/summary.json.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
GROUPS = ["Angiosperms", "Gymnosperms", "Pteridophytes", "Bryophytes"]
# Species with well-known haploid numbers, used only to confirm which level the 'median' column reports.
REFERENCE = {"Arabidopsis thaliana": 5, "Zea mays": 10, "Triticum aestivum": 21, "Oryza sativa": 12, "Pinus sylvestris": 12, "Abies alba": 12}


def main():
    os.makedirs(DERIVED, exist_ok=True)
    parts = []
    for g in GROUPS:
        d = pd.read_csv(os.path.join(DATA, f"ccdb_statistics_{g}.csv"))
        d["group"] = g
        parts.append(d)
    df = pd.concat(parts, ignore_index=True)
    df["n"] = pd.to_numeric(df["median"], errors="coerce")
    df = df[df["n"].notna() & (df["n"] > 0)].drop_duplicates(subset="resolved_name")
    ref_check = {sp: (float(df.loc[df["resolved_name"] == sp, "n"].iloc[0]) if (df["resolved_name"] == sp).any() else None) for sp in REFERENCE}
    level_ok = sum(1 for sp, v in ref_check.items() if v is not None and abs(v - REFERENCE[sp]) < 0.5)
    level_2n = sum(1 for sp, v in ref_check.items() if v is not None and abs(v - 2 * REFERENCE[sp]) < 0.5)
    note = "median column matches haploid n on reference species" if level_ok > level_2n else "median column looks like 2n; halved"
    if level_2n > level_ok:
        df["n"] = df["n"] / 2
    n = df["n"].to_numpy()
    tot = len(n)
    in_range = float(np.mean((n >= 6) & (n <= 16)))
    below = float(np.mean(n < 6))
    above = float(np.mean(n > 16))
    a = in_range >= 0.70
    b = below < 0.15
    c = above < below
    if a and b and c:
        verdict = "supports"
    elif in_range < 0.50 or above >= below or above >= 0.15:
        verdict = "refutes"
    else:
        verdict = "mixed"
    by_group = df.groupby("group")["n"].agg(count="size", median="median", frac_6_16=lambda x: float(np.mean((x >= 6) & (x <= 16))),
                                            frac_below_6=lambda x: float(np.mean(x < 6)), frac_above_16=lambda x: float(np.mean(x > 16)))
    # Post-hoc sensitivity (added after the pre-registered result, at the hub's request to enumerate readings; not part of the rule):
    # (i) lowest count per species instead of the median, which removes polyploid cytotypes within a species;
    # (ii) one value per genus (median of species medians), which damps polyploid species radiations.
    df["n_min"] = pd.to_numeric(df["minimum"], errors="coerce")
    if level_2n > level_ok:
        df["n_min"] = df["n_min"] / 2
    nm = df["n_min"].dropna().to_numpy()
    df["genus"] = df["resolved_name"].astype(str).str.split().str[0]
    gen = df.groupby("genus")["n"].median().to_numpy()
    sensitivity = {
        "min_count_per_species": {"n": int(len(nm)), "fraction_6_to_16": float(np.mean((nm >= 6) & (nm <= 16))), "fraction_below_6": float(np.mean(nm < 6)), "fraction_above_16": float(np.mean(nm > 16))},
        "genus_level_median": {"n_genera": int(len(gen)), "fraction_6_to_16": float(np.mean((gen >= 6) & (gen <= 16))), "fraction_below_6": float(np.mean(gen < 6)), "fraction_above_16": float(np.mean(gen > 16))},
        "angiosperms_only_species": {"fraction_above_16": float(np.mean(df.loc[df["group"] == "Angiosperms", "n"] > 16)), "fraction_below_6": float(np.mean(df.loc[df["group"] == "Angiosperms", "n"] < 6))},
    }
    for k, v in sensitivity.items():
        v["would_refute_under_rule"] = bool(v["fraction_above_16"] >= v["fraction_below_6"] or v["fraction_above_16"] >= 0.15 or v.get("fraction_6_to_16", 1) < 0.5)
    hist = df["n"].clip(upper=60).round().astype(int).value_counts().sort_index()
    pd.DataFrame({"n_capped_at_60": hist.index, "species": hist.values}).to_csv(os.path.join(DERIVED, "n_distribution.csv"), index=False)
    out = {"n_species_with_count": int(tot), "fraction_6_to_16": in_range, "fraction_below_6": below, "fraction_above_16": above,
           "median_n": float(np.median(n)), "mode_n": int(hist.idxmax()), "n_quantiles_5_25_50_75_95": [float(x) for x in np.percentile(n, [5, 25, 50, 75, 95])],
           "reference_species_check": ref_check, "count_level_note": note, "by_group": by_group.reset_index().to_dict("records"),
           "criterion_a": bool(a), "criterion_b": bool(b), "criterion_c": bool(c), "verdict": verdict, "post_hoc_sensitivity": sensitivity}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


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
