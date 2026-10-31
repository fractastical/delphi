# Best practices

How this project builds, publishes, and queries Project Delphi nanopublications. It is
adapted from the
[Project Delphi Ontology](https://github.com/fractastical/project-delphi-ontology), mainly
its [publishing best practice](https://github.com/fractastical/project-delphi-ontology/blob/main/PUBLISHING.md)
and [ontology reference](https://github.com/fractastical/project-delphi-ontology/blob/main/ONTOLOGY.md).
Where this file and upstream disagree, upstream wins. Fix this file.

Published nanopubs are immutable. A mistake that reaches production costs a supersede or
retract round, and the mistaken version stays on the network forever. A hackathon deadline
is not a reason to skip the checks below. Publish to the test registry and promote later.

## The short version

1. **Build through the 12-step loop** wherever the work allows it.
2. **Inspect for dummy data** before anything is signed.
3. **Publish every batch to the test registry first.** Never go straight to production.
4. **Promote to production only after review**, never during the hack by default.
5. **Source every assertion** with a dataset identifier or the paper it was extracted from.
6. **Give every dataset its own nanopub**, and have claims point at its IRI.
7. **Never overwrite: supersede or retract**, signed with the same key.
8. **Record every publication** in a manifest, and never commit keys.
9. **Use the ontology as defined**: reuse standard terms, keep claims, scores, and
   probabilities distinct.
10. **Query without assuming inference**: enumerate every spelling of a term.

## 1. Use the 12-step loop where possible

The [MorphoEval 12-step closed loop](https://github.com/fractastical/morpholib#the-12-step-closed-loop)
is the default route to a published claim:

| Tier | Steps | What it guarantees before publication |
|---|---|---|
| A: build | 1 Scout · 2 Paper · 3 Formal source · 4 Pin the rules (Lean 4) · 5 Script · 6 Output & compare | Inputs are vendored and SHA-256 locked, the paper's invariants are machine-checked, and outputs sit beside real specimens. |
| B: audit | 7 Dual-agent audit · 8 Measure · 9 Write as claims · 10 Sign & publish · 11 Public record · 12 Remediate | Two assessors from **different providers** score the work, outputs are hashed and measured independently, and every defect loops back to step 5. |

- **`assessor != builder`.** The model or agent that built something never scores it.
- **AI-audited is not expert-validated.** Only describe a finding as validated by an expert
  if a human validation record exists.
- **At least two assessor providers, none the builder's.** If an assessor's provider fails
  or stalls, publish with the providers that completed, provided at least two remain, and
  record the dropped assessor in the commit message and the summary. Never fill its place
  with the builder's model.
- **Assessors work blind.** Give them only the claim, its quote, the rubric and the source
  text, never the builder's own triage or another assessor's output.
- **A changed rubric is a new rubric version.** Change the version (and its concept IRI)
  whenever any question, anchor or weight wording changes; scores under different
  versions are not pooled.
- When the loop does not fit (a pre-registration, an ontology or template change, an
  inventory or entity nanopub), say so in the nanopub's provenance or the manifest, and
  still apply sections 2–8.

## 2. Always inspect for dummy data

Nothing synthetic, templated, or placeholder is published as if it were real. Check every
batch for:

- **Synthetic series presented as measurements**: random or formula-generated values in
  place of the paper's or dataset's actual numbers.
- **Fabricated identifiers**: DOIs, accessions, or URLs that do not resolve, or that encode
  a run or slot number rather than a real record.
- **Template provenance**: a shared helper's default sources reused for an unrelated claim.
- **Stub proofs**: Lean files with 0 `sorry` that prove generic arithmetic rather than the
  stated law.
- **Placeholder IRIs and text**: `example.org`, `TODO`, `TBD`, `XXX`, `lorem`, unreplaced
  `~~~ARTIFACTCODE~~~` markers, or empty labels.
- **Numbers that disagree**: a count in a label that differs from the structured value or
  the report that shows the same quantity.

Run the upstream publish-time lint on every batch, before test and again before
production. Any finding blocks the batch:

```bash
git clone https://github.com/fractastical/project-delphi-ontology.git
cd project-delphi-ontology/pipeline && npm install
npx tsx lint.ts /path/to/batch/ --published-datasets datasets.txt
```

Use `--extracted` for claims extracted from a paper's text, and `--exempt <file>` for
claims with no empirical input (claim IRI, tab, reason). Also open a few signed TriG files
by hand, chosen at random rather than the first few.

- **Model-proposed identifiers are checked mechanically.** Every URL or DOI an extractor or
  assessor proposes is resolved by script before publication. One that does not resolve is
  dropped and listed in a `dropped-*.json` report, even if the site is real but blocks
  automated requests.
- **Editing model output.** If text written by a model has to change to pass lint, keep the
  raw output file untouched, record the edit (old text, new text, reason) in an
  `edits.json` that the build applies and fails on if the old text no longer matches, and
  never change the meaning. Do not invent a number to satisfy a lint rule: if the source
  gives no exact value, drop the number from the text.

## 3. Publish to the test registry first

As soon as a batch is signed and passes section 2, publish all of it to the test registry
(`https://test.registry.knowledgepixels.com/`), then check:

- `np check` (the nanopub-py CLI, `pipx install nanopub`) passes on the signed files, and
  nanopub-js `verifySignature` accepts them (the publish scripts run it before upload).
- A sample renders correctly in [Nanodash](https://nanodash.knowledgepixels.com/), and its
  links and cited identifiers resolve.
- A [Nanopub Query](https://query.knowledgepixels.com/) count matches the number of files
  published.

Test is a staging area, not a record. Do not cite test URIs in demos, slides, papers, or
other nanopubs' `prov:wasDerivedFrom`. They change when the batch is promoted.

## 4. Promote to production only after review

Promote a batch only if all of these hold:

- [ ] The **same** batch passed on test: same generator commit, same inputs, same files.
- [ ] Sections 2, 5, and 6 pass with zero errors.
- [ ] A human has reviewed a sample. Public-facing claims need a second reviewer.
- [ ] The result is final. Anything still being remediated stays on test.
- [ ] Nothing it depends on (datasets, superseded nanopubs, templates) is still on test.

Batches that fail are fixed, rebuilt, and go back through section 3.

**Exception: pre-registrations.** A blind prediction's value is its timestamp, so it goes
to production as soon as it passes sections 2 and 3. Its outcome follows the normal path.

## 5. Source every assertion

- **Every claim names each dataset it used** with `prov:used delphir:dataset/<id>`. A claim
  extracted from a paper cites the paper with `prov:wasDerivedFrom` its `https://doi.org/` IRI.
- **Claims from a book or other work without a DOI** cite the edition's Wikidata item, or,
  if the edition has none, its digitised edition page linked to the Wikidata item for the
  work. Vendor the exact text file, pin its SHA-256, and give each claim a **verbatim**
  quote with a line locator into that file (RFC 5147 `#line=a,b`). The build fails if any
  quote is not found verbatim. Transcriber artefacts (page markers such as `{12}`,
  footnote markers such as `[3]`) are removed from both quote and text before matching.
  Record the claim as the author made it, even when modern science considers it wrong.
- **Pin versions**: input file SHA-256 or dataset version, and the generator's commit. The
  commit must be pushed and the tree clean for the files the generator reads before
  anything is signed, so every commit-pinned link in provenance resolves.
- **Put sample sizes in structured triples**, not only in labels.
- **Cite secondary sources separately** from the primary data.
- **State results in the nanopub**: the hypothesis, the pre-registered pass criterion, the
  measured value, and the verdict. A link to a report is supplementary.
- **No hard-coded provenance defaults** in shared helpers. A builder must be given its
  sources and fail if it is not.
- **Attribute the agent** (human, model, or script) with `prov:wasAttributedTo` and
  `prov:actedOnBehalfOf`, and include label, license, and creator in pubinfo.

## 6. Every dataset gets its own nanopub

Each dataset is published once as an entity nanopub introducing `delphir:dataset/<id>`,
typed `dcat:Dataset`, following the upstream
[dataset convention](https://github.com/fractastical/project-delphi-ontology/blob/main/ONTOLOGY.md#dataset-convention).
It carries its persistent identifier and citation, the paper that describes it, creators,
license, version, one distribution per file used (download URL and SHA-256), structured
counts that say exactly what was counted, and the agent that vendored it.

Confidence in the dataset is a separate rubric assessment scoring source authority,
integrity, completeness, independence, and authenticity, each with `delphi:hasScore`. The
agent that vendored the dataset does not score it. Whether a dataset fits a particular
claim is judged in that claim's assessment, not the dataset's.

The dataset nanopub and its assessment reach production before any claim that cites them.

## 7. Corrections: supersede or retract, never overwrite

- **Supersede** (`npx:supersedes`) when the claim still stands but its content, sources, or
  values change. State what changed and why.
- **Retract** (`npx:retracts`) when the claim should not exist.
- Sign both with the **same key** as the original, or the network ignores them.
- Corrections go through the same test-then-production path.

## 8. Record every publication, and protect keys

Record every published file in a manifest with its file path, trusty URI, registry (test or
production), timestamp, and generator commit. A batch not in the test manifest cannot be
promoted.

Never commit signing keys, nanopub profiles, or API tokens. Keys stay in `~/.nanopub/` or a
CI secret store.

## 9. Use the ontology as defined

Use the canonical namespaces from
[ontology 2.0](https://github.com/fractastical/project-delphi-ontology/blob/main/ONTOLOGY.md):

| Prefix | IRI | Holds |
|---|---|---|
| `delphi:` | `https://w3id.org/delphi/ontology/` | Terms (classes and properties) |
| `delphir:` | `https://w3id.org/delphi/resource/` | Individuals (`delphir:<kind>/<id>`) |

- **Reuse a standard term wherever one means the same thing** (PROV-O, SKOS, Dublin Core,
  DCAT, FaBiO, schema.org). Only propose a new `delphi:` term upstream when none does.
- **A claim is a belief, not a fact.** `delphi:Claim` is a subclass of `delphi:Hypothesis`;
  its credibility lives in attached `delphi:Assessment`s.
- **Keep scores, weights, and probabilities apart.** `delphi:hasScore` is a rubric rating in
  [0,1], `delphi:weightOfEvidence` is a 0–1 weight, and `delphi:hasProbability` is
  P(claim true). Never put a rubric score in `hasProbability`.
- **Use the 2.0 attribution shape**: `prov:wasAttributedTo` a `prov:SoftwareAgent` that
  `delphi:usesModel` a `delphi:LanguageModel`, and `prov:wasDerivedFrom` for sources. Do not
  emit the deprecated `delphi:Model`, `delphi:assessedBy`, `delphi:derivedFromPaper`, or
  `delphi:Paper`.
- **Formulas and Lean live on a law concept, not on the claim.** Follow the upstream
  [formal-verification convention](https://github.com/fractastical/project-delphi-ontology/blob/main/ONTOLOGY.md#formal-verification-convention-v13):
  each mathematical law is a `delphi:Concept` (`delphir:math-law/<id>`) in its own nanopub,
  carrying the formula as `skos:notation` (LaTeX), the Lean 4 source as `skos:definition`
  typed `delphi:lean4`, `delphi:leanDeclaration` / `delphi:leanTheorem` /
  `delphi:leanVerified`, and commit-pinned `rdfs:seeAlso` links to the Lean module. The
  claim is linked to it with `<claim> dct:conformsTo <law>`, asserted in the concept's
  nanopub, so adding a formula or proof never requires republishing a signed claim. Set
  `leanVerified true` only if the kernel accepted the module with no `sorry` and no added
  axioms. The Lean statement must encode the stated law, with its physical assumptions as
  explicit hypotheses (see stub proofs in section 2); whether it is a faithful rendering is
  an assessment question for an assessor from a different provider than the one that wrote
  the Lean.
- **Model agreement is not replication.** Two models agreeing is not independent
  experimental evidence.
- **Never mint `example.org`, `urn:pkg:`, or `w3id.org/probknow/...` IRIs** in new nanopubs.
  Upstream builders reject them.

## 10. Query without assuming inference

[Nanopub Query](https://query.knowledgepixels.com/) runs on RDF4J **without inference**, so
the ontology's equivalence and subclass axioms have no effect at query time.

- Enumerate every spelling of a term you need with a `VALUES` block: the canonical
  `delphi:` form, the `probknow` slash and 1.0 hash forms, and the `levin-kg` and `urn:`
  forms. See the upstream
  [published queries](https://github.com/fractastical/project-delphi-ontology/tree/main/nanopubs/queries-views).
- To reach both ontology generations, query the deprecated and replacement terms together
  (for example `delphi:assessedBy` and `prov:wasAttributedTo`).
- Prefer the published query templates (`https://query.knowledgepixels.com/api/<artifact-code>/<query-name>`)
  over ad-hoc copies, so fixes upstream reach us.
- Treat high scores in results as high assigned scores, not proven claims.
