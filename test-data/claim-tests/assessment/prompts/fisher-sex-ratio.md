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

- Claim id: fisher-sex-ratio
- Label: Fisher's principle of equal investment in the sexes
- Statement: Under random mating and autosomal inheritance, selection drives parents to invest equally in sons and daughters, which gives a 1:1 sex ratio when the two cost the same.
- Source quote: ""
- Source: Ronald A. Fisher, The Genetical Theory of Natural Selection (1930), The Genetical Theory of Natural Selection (1930)
- Kind: model-theorem

## The test

Hypothesis as tested (written before the data were opened):

If parents are selected to invest equally in sons and daughters and a son costs the same as a daughter, then the primary (birth) sex ratio of human populations should be close to one male per female and should not vary widely between populations.

Pre-registered pass criterion:

Pre-registered. Data: United Nations World Population Prospects 2024, Demographic Indicators, medium variant CSV (WPP2024_Demographic_Indicators_Medium.csv.gz), variable SRB (sex ratio at birth, males per 100 female births), rows with LocTypeName == 'Country/Area', years 1950 to 1979 inclusive (before prenatal sex determination was widely available, so the ratio reflects biology rather than sex-selective abortion), country-years with total mid-year population >= 1 million. Criterion A (equality): the median SRB across qualifying country-years lies in [95, 105] (within 5% of equal numbers). Criterion B (uniform near-equality): at least 95% of qualifying country-years lie in [90, 110]. SUPPORTS if A and B both hold.

Pre-registered fail criterion:

Pre-registered. REFUTES if the median SRB lies outside [90, 110] OR fewer than 80% of qualifying country-years lie in [90, 110]. MIXED otherwise (for example a consistent small excess of one sex between 5% and 10%, with B holding). INCONCLUSIVE (data-unavailable) if the file cannot be downloaded or has no SRB column.

Datasets (as recorded by the test; each file's checksum and retrieval time are on record):

- United Nations World Population Prospects 2024, Demographic Indicators, medium variant (CSV) (version: WPP 2024 (July 2024 release)); licence: CC BY 3.0 IGO. Role: sex ratio at birth (SRB, males per 100 female births) and mid-year population by country and year Files: WPP2024_Demographic_Indicators_Medium.csv.gz

Method, as the test describes it:

fetch.py downloads the gzipped CSV (16.6 MB). analysis.py keeps rows of type Country/Area for 1950-1979 with mid-year population >= 1 million and a non-missing SRB, and computes the median, mean, SD, 5th and 95th percentiles of SRB over country-years, the fractions inside [95,105] and [90,110], and per-country means; the pre-registered rule is applied.

## The analysis code (the model that was run)

```python
"""Test of fisher-sex-ratio: is the human sex ratio at birth close to 1:1 and uniform across populations, 1950-1979?

Reads data/WPP2024_Demographic_Indicators_Medium.csv.gz (run fetch.py first). Writes derived/country_years.csv and
derived/summary.json. SRB is males per 100 female births as published by the UN.
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data", "WPP2024_Demographic_Indicators_Medium.csv.gz")
DERIVED = os.path.join(HERE, "derived")


def main():
    os.makedirs(DERIVED, exist_ok=True)
    d = pd.read_csv(DATA, low_memory=False, usecols=["LocID", "ISO3_code", "Location", "LocTypeName", "Time", "TPopulation1July", "SRB"])
    d = d[(d["LocTypeName"] == "Country/Area") & (d["Time"] >= 1950) & (d["Time"] <= 1979)].copy()
    d["TPopulation1July"] = pd.to_numeric(d["TPopulation1July"], errors="coerce")  # thousands
    d["SRB"] = pd.to_numeric(d["SRB"], errors="coerce")
    d = d[(d["TPopulation1July"] >= 1000) & d["SRB"].notna()].copy()
    srb = d["SRB"].to_numpy()
    med = float(np.median(srb))
    in_90_110 = float(np.mean((srb >= 90) & (srb <= 110)))
    in_95_105 = float(np.mean((srb >= 95) & (srb <= 105)))
    a = 95 <= med <= 105
    b = in_90_110 >= 0.95
    if a and b:
        verdict = "supports"
    elif not (90 <= med <= 110) or in_90_110 < 0.80:
        verdict = "refutes"
    else:
        verdict = "mixed"
    by_country = d.groupby(["LocID", "Location"])["SRB"].agg(["mean", "min", "max", "count"]).reset_index()
    summary = {
        "n_country_years": int(len(d)),
        "n_countries": int(d["LocID"].nunique()),
        "years": [int(d["Time"].min()), int(d["Time"].max())],
        "srb_median": med,
        "srb_mean": float(srb.mean()),
        "srb_sd": float(srb.std(ddof=1)),
        "srb_min": float(srb.min()),
        "srb_max": float(srb.max()),
        "srb_p05": float(np.percentile(srb, 5)),
        "srb_p95": float(np.percentile(srb, 95)),
        "fraction_in_90_110": in_90_110,
        "fraction_in_95_105": in_95_105,
        "criterion_A_median_in_95_105": bool(a),
        "criterion_B_95pct_in_90_110": bool(b),
        "country_means_min": float(by_country["mean"].min()),
        "country_means_max": float(by_country["mean"].max()),
        "verdict": verdict,
    }
    d[["LocID", "ISO3_code", "Location", "Time", "TPopulation1July", "SRB"]].to_csv(os.path.join(DERIVED, "country_years.csv"), index=False)
    by_country.to_csv(os.path.join(DERIVED, "country_means.csv"), index=False)
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
