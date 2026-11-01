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

- Claim id: thompson1917-ch03-07
- Label: Weight tends to vary as the cube of linear dimensions during growth
- Statement: Whatever the law of increase in a linear dimension, volume and therefore weight tend to vary as the cube of linear dimensions, which mainly (though not wholly) explains why the human weight curve differs in shape from the stature curve.
- Source quote: "whatever be the law of increment in a linear dimension, the law of increase in volume, and therefore in weight, will be that these latter magnitudes tend to vary as the cubes of the linear dimensions."
- Source: D'Arcy Wentworth Thompson, On Growth and Form (1917), Ch. III: The Rate of Growth
- Kind: mathematical-law

## The test

Hypothesis as tested (written before the data were opened):

If weight varies as the cube of a linear dimension during growth, then across childhood and adolescence the population mean body weight scales with the population mean stature with a log-log exponent near 3, so the weight-for-age curve is approximately the cube of the stature-for-age curve.

Pre-registered pass criterion:

Pre-registered. Data: US NHANES examination data, cycles 2013-2014, 2015-2016 and 2017-2018 (Body Measures BMX_H/I/J and Demographics DEMO_H/I/J XPT files), examined participants aged 2 to 19 years with measured standing height (BMXHT, cm) and weight (BMXWT, kg). For each sex, compute MEC-exam-weighted (WTMEC2YR) mean height and mean weight in 1-year age bins (18 bins), regress log(mean weight) on log(mean height) by ordinary least squares, and also fit the constrained model weight = k * height^3 with k estimated by least squares on the log scale. SUPPORTS if, for both sexes, the free exponent b lies in [2.5, 3.5] AND the cubic model reproduces the age-bin mean weights with R^2 >= 0.90 on the original scale.

Pre-registered fail criterion:

Pre-registered. REFUTES if, for either sex, b lies outside [2.5, 3.5] OR the cubic model's R^2 on the age-bin weight curve is < 0.90. MIXED is not possible under this rule except as follows: if the two sexes disagree (one passes, the other fails) the verdict is MIXED. INCONCLUSIVE (data-unavailable) if the files cannot be downloaded.

Datasets (as recorded by the test; each file's checksum and retrieval time are on record):

- US National Health and Nutrition Examination Survey (NHANES) 2013-2014, 2015-2016 and 2017-2018: Body Measures (BMX) and Demographics (DEMO) files (version: public release XPT files as served 2026-10-31); licence: public domain (US federal government data). Role: measured standing height and weight with age, sex and MEC exam weights Files: BMX_H.xpt, DEMO_H.xpt, BMX_I.xpt, DEMO_I.xpt, BMX_J.xpt, DEMO_J.xpt

Method, as the test describes it:

fetch.py downloads six XPT files (16.5 MB). analysis.py merges body measures with demographics per cycle, keeps examined participants aged 2-19 with both measurements, computes MEC-weighted mean height and weight per completed year of age and sex, regresses log mean weight on log mean height (free exponent with 95% CI), fits weight = k * height^3 by least squares on the log scale, and scores the cubic model's R^2 on the original scale.

## The analysis code (the model that was run)

```python
"""Test of thompson1917-ch03-07 (weight varies as the cube of linear dimensions during growth) on NHANES 2013-2018.

Reads data/BMX_{H,I,J}.xpt and data/DEMO_{H,I,J}.xpt (run fetch.py first). Writes derived/age_bins.csv and derived/summary.json.
"""
import json
import os

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")


def load():
    parts = []
    for s in "HIJ":
        b = pd.read_sas(os.path.join(DATA, f"BMX_{s}.xpt"), format="xport")[["SEQN", "BMXWT", "BMXHT"]]
        d = pd.read_sas(os.path.join(DATA, f"DEMO_{s}.xpt"), format="xport")[["SEQN", "RIAGENDR", "RIDAGEYR", "WTMEC2YR"]]
        m = b.merge(d, on="SEQN")
        m["cycle"] = s
        parts.append(m)
    df = pd.concat(parts, ignore_index=True)
    df = df[(df["RIDAGEYR"] >= 2) & (df["RIDAGEYR"] <= 19) & df["BMXWT"].notna() & df["BMXHT"].notna() & (df["WTMEC2YR"] > 0)]
    return df


def per_sex(df):
    g = df.groupby("RIDAGEYR")
    w = g.apply(lambda x: np.average(x["BMXWT"], weights=x["WTMEC2YR"]), include_groups=False)
    h = g.apply(lambda x: np.average(x["BMXHT"], weights=x["WTMEC2YR"]), include_groups=False)
    n = g.size()
    bins = pd.DataFrame({"age": w.index.astype(int), "mean_weight_kg": w.values, "mean_height_cm": h.values, "n": n.values})
    lw, lh = np.log(bins["mean_weight_kg"]), np.log(bins["mean_height_cm"])
    free = stats.linregress(lh, lw)
    tcrit = stats.t.ppf(0.975, len(bins) - 2)
    logk = float(np.mean(lw - 3 * lh))
    pred = np.exp(logk) * bins["mean_height_cm"] ** 3
    ss_res = float(np.sum((bins["mean_weight_kg"] - pred) ** 2))
    ss_tot = float(np.sum((bins["mean_weight_kg"] - bins["mean_weight_kg"].mean()) ** 2))
    r2 = 1 - ss_res / ss_tot
    bins["cubic_model_weight_kg"] = pred.values
    return bins, {"n_participants": int(len(df)), "n_age_bins": int(len(bins)), "free_exponent_b": float(free.slope),
                  "b_ci95": [float(free.slope - tcrit * free.stderr), float(free.slope + tcrit * free.stderr)], "free_fit_r2_log": float(free.rvalue ** 2),
                  "cubic_k_kg_per_cm3": float(np.exp(logk)), "cubic_model_r2_original_scale": float(r2),
                  "height_range_cm": [float(bins["mean_height_cm"].min()), float(bins["mean_height_cm"].max())],
                  "weight_range_kg": [float(bins["mean_weight_kg"].min()), float(bins["mean_weight_kg"].max())]}


def main():
    os.makedirs(DERIVED, exist_ok=True)
    df = load()
    res, tables = {}, []
    for code, name in ((1, "male"), (2, "female")):
        bins, r = per_sex(df[df["RIAGENDR"] == code])
        bins.insert(0, "sex", name)
        tables.append(bins)
        r["passes"] = bool(2.5 <= r["free_exponent_b"] <= 3.5 and r["cubic_model_r2_original_scale"] >= 0.90)
        res[name] = r
    p = [res["male"]["passes"], res["female"]["passes"]]
    verdict = "supports" if all(p) else ("refutes" if not any(p) else "mixed")
    out = {"cycles": ["2013-2014", "2015-2016", "2017-2018"], "ages": "2-19 completed years", **res, "verdict": verdict}
    pd.concat(tables).to_csv(os.path.join(DERIVED, "age_bins.csv"), index=False)
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
