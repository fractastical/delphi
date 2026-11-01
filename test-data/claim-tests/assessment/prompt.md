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

- Claim id: {{claim_id}}
- Label: {{label}}
- Statement: {{statement}}
- Source quote: "{{quote}}"
- Source: {{thinker}}, {{work}} ({{year}}), {{chapter}}
- Kind: {{kind}}

## The test

Hypothesis as tested (written before the data were opened):

{{hypothesis}}

Pre-registered pass criterion:

{{pass_criterion}}

Pre-registered fail criterion:

{{fail_criterion}}

Datasets (as recorded by the test; each file's checksum and retrieval time are on record):

{{datasets}}

Method, as the test describes it:

{{method}}

## The analysis code (the model that was run)

```python
{{analysis_source}}
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
