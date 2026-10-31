# Schema notes from the claim and evidence adapters

Single-reader (corpus session, Claude Sonnet 5.5), **not Codex-reviewed**. Written against core `1b329cc`
(`Claim.origin`, `Evidence.relation`, `Evidence.produced_by`, `Evidence.artifacts` as `ArtifactRef`, `Action.inputs`).
This file proposes nothing for `models.py`; root integrates. It records how the adapters use the new fields and what real use
exposed.

## How `frontier_adapters` uses the core fields
| field | adapter behaviour | why |
|---|---|---|
| `Claim.origin` | omitted (= unknown) for every Delphi claim; the adapter **refuses** to set `source_statement` | it cannot check that a pipeline-written statement says what its source says. A reviewer who read the source must assert it |
| `Evidence.relation` | set explicitly (`qualifies` for the NCA sweep), with the reason in `context`, and labelled a declaration by the importing adapter, not a review | the producer did not label it, and relation does not change review status |
| `Evidence.produced_by` | pins an `Action` with the **same target** (the store enforces this) | joins the evidence to the action that is said to have produced it |
| `Evidence.artifacts` | `urn:sha256:<digest>`, `availability: referenced`, `license: null`, with the git commit and path in `title` | the bytes are not at a public HTTPS URL we can vouch for, and no licence is stated. Switch to the served URL and `downloadable` only after the site serves it and an owner states a licence |
| `Action.inputs` | pins the exact Claim versions the analysis used | gives `uses` edges. It is a **declaration**: it does not show the action ran |
| `Source.license` | always null for Delphi claims and runs | means source-content rights. Delphi's record licence (CC-BY-4.0, on the nanopub) is kept under `prior_review.delphi_original.record` |

Separate counts are kept in `chain.json` (`reuse_counts`): imported records, declared reuse, executed reuse, independently
reviewed reuse. In the NCA example: 6 records, 2 Actions, **1** run, 0 independently reviewed.

## What real use exposed (small, optional)
1. **A record-provenance home on `Claim`.** Delphi's non-mappable fields (record licence, creator, registry, upstream
   verification labels, quote digest) sit under `prior_review.delphi_original`, but `prior_review` is meant for reviews. A typed
   `Claim.original: dict` (as `Problem` already has) would stop overloading it.
2. **`ArtifactRef` has no field for *where* the bytes are.** With `urn:sha256:` pointers the git commit/path lives in free-text
   `title`. An optional `locator: Short | None` would make it inspectable and checkable.
3. **`TimeClaim.basis = "witnessed"` is undefined.** The adapter uses it for the OpenResearch supervisor's own clock on the
   producing machine (uncorroborated). Say whether that qualifies.
4. **No way to record an externally executed action with its receipt.** The Action lifecycle is `proposed -> ... -> accepted`
   inside the store. An action that an outside system already ran can only be a `proposed` Action plus Evidence that
   points at it. A receipt reference on the Action (or a `record_imported`-style transition) would state this honestly.
5. **Inputs are not first-class on an executed run.** The run in the example read two input files that its record does not
   list; the adapter found the second only because replay without it silently changed the output. `Action.inputs` pins
   Claims/Evidence, not data files. Input artifacts live in `Evidence.artifacts` with role `input`; consider requiring at least one
   `input` artifact when `produced_by` is set and the Action's `cache_key.input` names data.

## Proposed root `pyproject.toml` changes (root owns it)
- No new runtime dependency.
- `[project.optional-dependencies] test = ["pytest==9.0.2", "rdflib==7.6.0"]` (rdflib only for one independent TriG parse
  test, which is skipped with a stated reason when absent).
- `[tool.pytest.ini_options] testpaths = ["tests", "frontier_adapters/tests"]`.
- Live re-verification of the NCA example is opt-in through `NCA_REPO` and `ORX_STORE` (environment variables naming a git
  checkout and an OpenResearch data directory); nothing in the package depends on an absolute path.
