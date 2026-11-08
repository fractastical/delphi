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
3. **Publish every batch to the test registry first**, and commit and push the signed files
   and manifest in the same step. Never go straight to production.
4. **Promote to production only after review**, never during the hack by default.
5. **Source every assertion** with a dataset identifier or the paper it was extracted from.
6. **Give every dataset its own nanopub**, and have claims point at its IRI.
7. **Never overwrite: supersede or retract**, signed with the same key.
8. **Record every publication** in a manifest, and never commit keys.
9. **Use the ontology as defined**: reuse standard terms, keep claims, scores, and
   probabilities distinct.
10. **Query without assuming inference**: enumerate every spelling of a term.
11. **While attempting an approach, publish each PKG nanopub before the next step**:
    the choice, then each step rating, then that step's outcome. Production is the
    timestamp. The step waits until that URI is in the manifest and the commit is pushed.
12. **Log which agent did which task.** One append-only line per task: time, agent name,
    model if known, the task in one sentence, and where the result is. A failed task stays.
13. **Causal links use the Relation Ontology, and molecular chains are linked to, not
    copied.** An RO IRI for every causal edge; an INDRA statement hash, GO-CAM model or
    SIGNOR record for the mechanism, fetched live and dated.

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

**Publish, commit and push together.** Publishing to test, committing the signed TriG files
and the updated manifest (section 8), and pushing are one step. Do not leave published
files uncommitted or unpushed, and do not commit signed files that have not been published.
Commit only the batch, not unrelated work in the tree, and name the registry and file count
in the commit message. If the publish fails partway, commit what reached the registry,
record the failures in the manifest, and say so in the commit message. If the push fails,
fix it before starting another batch. Promotion to production follows the same rule.

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
A PKG step graph (section 11) is this kind of record: each choice, step rating and step
outcome is published to test and promoted to production, on its own, before the next step
starts. That approval covers those files and no other batch.

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
promoted. The manifest is committed and pushed together with the publication (section 3).

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

## 11. Rate the attempt as you go: the PKG step graph

When an agent executes an approach from `problems/approaches/`, it records the
PKG step graph as nanopublications. Each probability is its own TriG file,
published to production before the step it rates. The outcome of that step is
a second nanopub, published before the next rating. A later reader compares
the registry timestamps and sees, step by step, where the attempt matched the
agent's own ratings. The whole-approach numbers in `problems/forecasts/` stay
a separate, blind round scored from `runs.json`.

The attempt id is `<approach-id>--<YYYY-MM-DD>` of the approach the agent
chooses. Files go in `problems/nanopubs/unsigned/` and follow the same shape as
the problem, approach and run nanopubs (Head, assertion, provenance, pubinfo;
`delphir:` individuals; `prov:SoftwareAgent` with `delphi:usesModel`). They
cite approach and problem IRIs. `build-nanopubs.mjs` keeps these files as written and
lists them in the manifest; it does not regenerate them. Do not edit a nanopub once
it has been published. A correction is a new nanopub.

**Publish each one before the next action.** A file in git can still be rewritten.
The production registry timestamp is the record that the rating preceded the step.
Publish with:

```sh
PROMOTE_APPROVED_BY=<orcid in ~/.nanopub/profile.yml> \
DELPHI_PIPELINE=/path/to/project-delphi-ontology/pipeline \
node problems/build/publish-pkg.mjs --file <your-file>.trig
```

`publish-pkg.mjs` signs only the named PKG file, publishes it to the test registry, and promotes
that same signed file to production. It does not publish the other problem nanopubs.
`PROMOTE_APPROVED_BY` must be the key owner's ORCID. This standing approval, given
2026-11-02, covers these files only. Then commit and push the signed file and the
manifest (section 3) before going on. The step, or the next rating, waits until the
production trusty URI is in `problems/nanopubs/manifest.json` and that commit is on
the remote. A test-registry URI is not that record.

The chain is what makes a backwards rating impossible to publish. The choice nanopub
is published first. Each step rating `prov:wasDerivedFrom` the production trusty URI
of the choice, or of the previous step's outcome. Each outcome `prov:wasDerivedFrom`
the production trusty URI of its step rating and `prov:used` the step IRI. The
publisher rejects a step or an outcome that does not carry such a URI.

**Choice nanopub, before any step.**
`pkg-choice--<attempt>.trig` introduces `delphir:pkg/<attempt>`, a
`prov:Activity`. It rates every approach to that problem the agent is actually
choosing among, at least two when the problem has more than one. Each rating is
a `schema:PropertyValue` with `schema:propertyID` `"p_complete"`,
`schema:value` an `xsd:decimal` in [0, 1], `dct:subject` the approach IRI, and
a `skos:note` of one sentence saying why. `p_complete` is the agent's
probability that trying that approach now would produce its decisive result.
Exactly one approach is the plan of the activity
(`prov:qualifiedAssociation` / `prov:hadPlan`).

**Step nanopub, then do the step.**
`pkg-step--<attempt>--<n>.trig` introduces `delphir:pkg-step/<attempt>/<n>`, a
`prov:Plan` and not a `delphi:TestableHypothesis`. `dct:isPartOf` the attempt,
`schema:position` is `n`, `rdfs:label` is the step text from the approach's
`steps` (a step absent from the proposal carries a `skos:note` `"added during
the attempt"`), and `prov:generatedAtTime` is when the rating was written. Its
`schema:PropertyValue` has `schema:propertyID` `"p_success"`: the probability
this step produces what it says, given the outcomes already recorded. Publish it
to production, commit and push, and only then start the step. It contains no
`schema:actionStatus`. Its provenance `prov:wasDerivedFrom` the production trusty
URI of the choice nanopub, or of the previous step's outcome.

**Outcome nanopub, after the step.**
`pkg-step-outcome--<attempt>--<n>.trig` introduces
`delphir:pkg-outcome/<attempt>/<n>`, a `prov:Activity` with `dct:isPartOf` the
attempt, `prov:used` the step IRI, and `schema:actionStatus`
`schema:CompletedActionStatus` (succeeded), `schema:FailedActionStatus`
(failed), or `schema:PotentialActionStatus` (blocked or skipped). A
`schema:PropertyValue` with `schema:propertyID` `"outcome"` holds the word
`succeeded`, `failed`, `blocked` or `skipped`. `prov:endedAtTime` is when the
step finished. A revised chance that the rest of the attempt finishes is
another `schema:PropertyValue`, `schema:propertyID` `"p_rest"`, on this
nanopub. Provenance `prov:wasDerivedFrom` the production trusty URI of the step
rating. Publish it to production before rating the next step.

A probability written after the outcome is not a rating. If the choice nanopub
has no production trusty URI, the attempt has not started: do the rating, publish
it, and do not write ratings backwards.

**What these numbers are.** Each `schema:value` is the attempting agent's
prediction of its own next action. `delphi:hasProbability` remains P(the claim
is true), and a rubric rating remains `delphi:hasScore`. The run is still
logged in `problems/forecasts/runs.json`, and the run's `note` names these
files. Someone other than the builder still assesses the scientific result.

```trig
@prefix this: <http://purl.org/nanopub/temp/np1/> .
@prefix sub: <http://purl.org/nanopub/temp/np1/> .
@prefix np: <http://www.nanopub.org/nschema#> .
@prefix npx: <http://purl.org/nanopub/x/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .
@prefix dct: <http://purl.org/dc/terms/> .
@prefix prov: <http://www.w3.org/ns/prov#> .
@prefix skos: <http://www.w3.org/2004/02/skos/core#> .
@prefix schema: <https://schema.org/> .
@prefix delphi: <https://w3id.org/delphi/ontology/> .

sub:Head {
  this: a np:Nanopublication ;
    np:hasAssertion sub:assertion ;
    np:hasProvenance sub:provenance ;
    np:hasPublicationInfo sub:pubinfo .
}

sub:assertion {
  <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02> a prov:Activity ;
    rdfs:label "Choice of approach for hygromorph-bilayer-scaling on 2026-11-02" ;
    dct:subject <https://w3id.org/delphi/resource/problem/hygromorph-bilayer-scaling> ;
    prov:qualifiedAssociation <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02#chosen> ;
    prov:startedAtTime "2026-11-02T05:00:00Z"^^xsd:dateTime ;
    schema:additionalProperty <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02#p-1>, <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02#p-2> .
  <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02#chosen> a prov:Association ;
    prov:hadPlan <https://w3id.org/delphi/resource/approach/hygromorph-bilayer-scaling--claude-opus-5-5--1> .
  <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02#p-1> a schema:PropertyValue ;
    schema:propertyID "p_complete" ;
    schema:value "0.35"^^xsd:decimal ;
    schema:description "Attempting agent's probability that trying this approach now produces its decisive result. A prediction of the work, not P(a claim is true)." ;
    dct:subject <https://w3id.org/delphi/resource/approach/hygromorph-bilayer-scaling--claude-opus-5-5--1> ;
    skos:note "The specimen table is already specified and the inputs are public." .
  <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02#p-2> a schema:PropertyValue ;
    schema:propertyID "p_complete" ;
    schema:value "0.12"^^xsd:decimal ;
    schema:description "Attempting agent's probability that trying this approach now produces its decisive result. A prediction of the work, not P(a claim is true)." ;
    dct:subject <https://w3id.org/delphi/resource/approach/hygromorph-bilayer-scaling--claude-opus-5-5--2> ;
    skos:note "The finite-element correction needs a solver the swarm has not run." .
  <https://w3id.org/delphi/resource/approach/hygromorph-bilayer-scaling--claude-opus-5-5--1> a prov:Plan ;
    rdfs:label "Literature-extracted test of curvature and h^2/D response time across species" .
  <https://w3id.org/delphi/resource/problem/hygromorph-bilayer-scaling> a delphi:Concept, schema:Question ;
    rdfs:label "Do real hygromorphs follow bilayer curvature and diffusive response-time scaling?" .
}

sub:provenance {
  sub:assertion prov:wasAttributedTo <https://w3id.org/delphi/resource/agent/delphisci-approach-runner-example-model> ;
    prov:wasDerivedFrom <https://w3id.org/delphi/resource/approach/hygromorph-bilayer-scaling--claude-opus-5-5--1> ;
    prov:wasGeneratedBy sub:rating .
  sub:rating a prov:Activity ;
    rdfs:label "Rating the approaches under consideration before attempting one, following BEST_PRACTICES.md section 11" ;
    prov:wasAssociatedWith <https://w3id.org/delphi/resource/agent/delphisci-approach-runner-example-model> .
  <https://w3id.org/delphi/resource/agent/delphisci-approach-runner-example-model> a prov:SoftwareAgent ;
    rdfs:label "delphisci approach runner (example-model)" ;
    delphi:usesModel <https://w3id.org/delphi/resource/model/example-model> ;
    prov:actedOnBehalfOf <https://orcid.org/0009-0007-4948-9192> .
  <https://w3id.org/delphi/resource/model/example-model> a delphi:LanguageModel ;
    rdfs:label "example-model" ;
    dct:identifier "example-model" .
}

sub:pubinfo {
  this: dct:created "2026-11-02T05:00:00Z"^^xsd:dateTime ;
    dct:creator <https://orcid.org/0009-0007-4948-9192> ;
    rdfs:label "Choice of approach for hygromorph-bilayer-scaling on 2026-11-02" ;
    dct:license <https://creativecommons.org/licenses/by/4.0/> ;
    npx:hasNanopubType prov:Activity ;
    npx:introduces <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02> ;
    delphi:domain <https://w3id.org/delphi/resource/domain/open-problems> .
}
```

A step rating uses the same prefixes, Head, provenance and pubinfo. Its
assertion introduces the step and stops before any outcome:

```trig
sub:assertion {
  <https://w3id.org/delphi/resource/pkg-step/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1> a prov:Plan ;
    rdfs:label "Extract specimen-level thicknesses, moduli, swelling strains and curvature for the named hygromorphs." ;
    dct:isPartOf <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02> ;
    schema:position 1 ;
    prov:generatedAtTime "2026-11-02T05:10:00Z"^^xsd:dateTime ;
    prov:wasDerivedFrom <https://w3id.org/np/RA_production_trusty_uri_of_the_choice> ;
    schema:additionalProperty <https://w3id.org/delphi/resource/pkg-step/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1#p_success> .
  <https://w3id.org/delphi/resource/pkg-step/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1#p_success> a schema:PropertyValue ;
    schema:propertyID "p_success" ;
    schema:value "0.70"^^xsd:decimal ;
    schema:description "Probability this step produces what it says, given the outcomes already recorded. Written before the step. A prediction of the work, not P(a claim is true)." .
}
```

The outcome nanopub's assertion, written after that step and derived from it:

```trig
sub:assertion {
  <https://w3id.org/delphi/resource/pkg-outcome/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1> a prov:Activity ;
    rdfs:label "Outcome of step 1" ;
    dct:isPartOf <https://w3id.org/delphi/resource/pkg/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02> ;
    prov:used <https://w3id.org/delphi/resource/pkg-step/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1> ;
    prov:wasDerivedFrom <https://w3id.org/np/RA_production_trusty_uri_of_the_step_rating> ;
    schema:actionStatus schema:CompletedActionStatus ;
    prov:endedAtTime "2026-11-02T06:40:00Z"^^xsd:dateTime ;
    schema:additionalProperty <https://w3id.org/delphi/resource/pkg-outcome/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1#outcome>, <https://w3id.org/delphi/resource/pkg-outcome/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1#p_rest> .
  <https://w3id.org/delphi/resource/pkg-outcome/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1#outcome> a schema:PropertyValue ;
    schema:propertyID "outcome" ;
    schema:value "succeeded" ;
    schema:description "What the step did: succeeded, failed, blocked or skipped." .
  <https://w3id.org/delphi/resource/pkg-outcome/hygromorph-bilayer-scaling--claude-opus-5-5--1--2026-11-02/1#p_rest> a schema:PropertyValue ;
    schema:propertyID "p_rest" ;
    schema:value "0.40"^^xsd:decimal ;
    schema:description "Revised probability that the rest of the attempt finishes, written with the outcome." .
}
```

## 12. Log which agent did which task

A published record names its sources. It does not, by itself, say which agent did the work
that produced it. Keep a separate log.

Append one line per task. Do not rewrite or delete a line because the task failed, was
abandoned, or was redone. Each line has:

- the time (ISO-8601),
- the agent that did the task, by the name it uses (forum name, session name), and the
  model if you know it,
- the task in one sentence,
- where the result is: a repo path, a commit, a forum post URL, or `none`.

Do not invent an agent name. If you do not know which agent it was, write `unknown` and
what you do know.

In this repository, Cursor sessions are already transcribed under `chats/`. A run that is
not one of those sessions writes its log next to the work (for example beside a claim
test) or, when the work is posted on the forum, includes the new lines in that post. The
forum name on a post is the public half of the same record, not a substitute for the log
of agents that never posted.

## 13. Causal links: use the Relation Ontology, and link out to the graphs that curate them

Other biology knowledge graphs already represent causal chains, all at the molecular
level: [GO-CAM](https://wiki.geneontology.org/Annotation_Relations) (chains of gene-product
activities), [INDRA CoGEx](https://github.com/gyorilab/indra_cogex) (signed, literature-mined
statements with evidence counts and PMIDs) and [SIGNOR](https://signor.uniroma2.it/)
(manually curated signed signalling edges). Two rules follow.

- **Every causal edge carries a Relation Ontology predicate, never a term of our own.**
  GO-CAM and RO's own
  [causal relations](https://oborel.github.io/obo-relations/causal-relations/) draw from the
  `causally upstream of or within` branch (`RO:0002418`): `causally upstream of`
  (`RO:0002411`), `causally upstream of, positive effect` (`RO:0002304`) / `negative effect`
  (`RO:0002305`), `directly positively regulates` (`RO:0002629`) / `directly negatively
  regulates` (`RO:0002630`), `provides input for` (`RO:0002413`). Pick the weakest relation
  the evidence supports: `causally upstream of` when the sign is unknown, the signed form
  when the sign is known, a `regulates` form only when the mechanism is known. RO defines
  these over processes, so the same predicates serve a molecular edge and an
  organism-level one (a bioelectric prepattern upstream of a morphological outcome). CiTO
  stays for relations between *records* (`cito:supports`, `cito:disagreesWith`); RO is for
  relations between the *things the records are about*. Between whole claims, prefer
  `skos:closeMatch` / `skos:exactMatch` for "the same regularity in another source". This is
  section 9's reuse rule applied to causation.
- **Link to a molecular chain; do not republish it.** When a claim rests on a mechanism
  that INDRA, GO-CAM or SIGNOR already curates, the record points at it: the INDRA statement
  hash with its PMIDs, the GO-CAM model id, or the SIGNOR record, with the grounding used
  (`hgnc:`, UBERON, GO, ChEBI IRIs) and the retrieval date. Fetch the chain live when it is
  needed (`indra-cogex` MCP, `AGENTS.md`). Copying their edges into our nanopubs adds no
  evidence, goes stale, and hides where the curation happened.

A chain fetched from one of these graphs is an observation someone else reported, graded by
their evidence count. In our vocabulary it is motivation or prior art for a claim test,
never evidence that the organism-level claim holds, and it never changes a verdict. The
edge nobody else curates, a mechanism linked across scales to a regularity about form,
behaviour or selection, is the one worth asserting here, with its agent, its reading of the
claim, and its evidence item like any other record.

## Solvers

Solver work follows [studio/engineering/solvers/BEST_PRACTICES.md](studio/engineering/solvers/BEST_PRACTICES.md).
A solver computes a receipt and writes that receipt as an unsigned nanopub.
The nanopub cites the mathematical subset the solver implements, such as
aerodynamics. It tests a law only when that receipt names the law.
The reliability report does not carry a confidence score. Signing waits for
the ORCID key owner.
