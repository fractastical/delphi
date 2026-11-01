# Problem graph

Genuinely hard open problems in biology and mathematics that the delphisci agent swarm could
plausibly attack, and the ways agents proposed to attack them. Both are nanopublications, so the
problem graph lives on the nanopub network next to the claim graph and can be queried, cited,
assessed and extended by anyone. Browse it at `docs/problems.html`.

Nothing here is solved. A problem nanopub says what is unknown, what is known, what would resolve
it and what would refute an answer. An approach nanopub is one agent's plan, written blind from the
problem statement; it becomes evidence only when someone runs it and logs the result against the
claims it names (`test-data/claim-tests/`, `delphi_log_test_result`) or a Lean proof lands in a
project's `lean/reports`.

## Files

| Path | What |
|---|---|
| `problems.json` | The problems. Fields mirror the Delphi Frontier `Problem` schema (question, known state, acceptance criteria, falsifiers, required capabilities, data access, scales) so each can be cross-posted there, plus `related_claims` (ids in the claim graph), `tier` and `references`. |
| `approaches/INSTRUCTIONS.md` | What a proposer is asked to do. |
| `approaches/<model>.json` | One file per proposer model, written without seeing the others. |
| `dropped-links.json` | Every DOI and URL named in the sources, resolved mechanically (`build/resolve-links.mjs`): DOIs through the Handle API with the Crossref title compared against the proposer's note, URLs by request. Links that fail are omitted from the nanopubs. |
| `nanopubs/unsigned/` | `problem--<id>.trig` and `approach--<problem>--<model>--<n>.trig`. |
| `nanopubs/signed-test/`, `nanopubs/manifest.json` | Signed files and where each was published. |
| `nanopubs/omitted-links.json` | Links and claim ids left out of the nanopubs, with the reason. |

## Tiers

- **A**: a proof or an exhaustive computation; the swarm could finish it (Rule 110 in Lean, the (2,3) Turing machine, Rule 54, Rule 30, Turing-capable topologies, Hamilton's rule, phyllotaxis attractors).
- **B**: an open empirical question a pre-registered data test on public data can settle (Lewontin's paradox, metabolic scaling, species–area, clade trajectories, shell morphospace, somite number, Murray's law).
- **C**: hard and open, where these agents have an unusual angle (morphogenesis–cognition gene overlap via INDRA, the bioelectric code, memory in GRN models, falsifiable active-inference morphogenesis, Kelvin's problem in epithelia, mutant–morphant discrepancies).

## RDF shape

The ontology has no problem class and we do not mint one. A problem is `delphir:problem/<id>`,
typed `delphi:Concept` (the ontology's reusable entity that claims and plans refer to) and
`schema:Question`; its question is `dct:description`, the known state `skos:historyNote`,
acceptance criteria and falsifiers `skos:scopeNote`, the claims it bears on `skos:related`, the
literature `rdfs:seeAlso` with Crossref titles. An approach is `delphir:approach/<problem>--<model>--<n>`,
typed `prov:Plan` and `delphi:TestableHypothesis`: the hypothesis that this plan would settle the
problem, with `delphi:proposedTest` the decisive result, `delphi:context` the failure signature,
`dct:subject` the problem, and the proposer as a `prov:SoftwareAgent` that `delphi:usesModel` a
`delphi:LanguageModel`. Planned sample sizes in the text are mirrored as structured counts
(`schema:additionalProperty`) because the upstream linter requires it. Domain: `delphir:domain/open-problems`.

## Build and publish

```sh
node problems/build/resolve-links.mjs            # check every DOI and URL; writes dropped-links.json
node problems/build/build-nanopubs.mjs           # unsigned TriG + manifest (commit problems/ first: links are commit-pinned)
node problems/build/build-site.mjs               # docs/problems.json, docs/problems.html
DELPHI_PIPELINE=/path/to/project-delphi-ontology/pipeline node problems/build/publish.mjs --registry test [--dry-run]
```

`publish.mjs` signs with `~/.nanopub/id_rsa`, runs the upstream linter on the signed batch, refuses
to sign while `problems/` has uncommitted changes, and publishes to the test registry. Promotion
(`--registry production`, `PROMOTE_APPROVED_BY=<ORCID>`) only republishes files already on test and
is a human decision (`BEST_PRACTICES.md` section 4).

## Adding a problem or an approach

Add the problem to `problems.json` with at least one `related_claims` id and one reference; a new
proposer writes `approaches/<model>.json` following `INSTRUCTIONS.md`. Published nanopubs are never
rewritten: the builder keeps their manifest entries and only writes files that are not yet published.
To change a published problem, supersede it (section 7 of `BEST_PRACTICES.md`).
