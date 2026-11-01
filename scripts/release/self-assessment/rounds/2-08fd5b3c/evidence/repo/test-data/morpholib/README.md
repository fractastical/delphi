# MorphoEval audits linked to claims

[morpholib](https://github.com/fractastical/morpholib) runs published morphogenesis models
(Turing, Murray, Vogel, Raup, Thompson's transformations, …) against real specimens and publishes
each run as a MorphoEval claim nanopub with rubric assessments. `links.json` says which of those
audits bear on which claims here.

- `source`: the morpholib commit the bundles were read from (`morphoeval/kg/` on `origin/main`) and
  the date the registries were checked.
- `claims`: every current MorphoEval claim (the newest bundle per claim IRI, under both the
  `probknow` and `delphi` vocabularies), with its nanopub, `registry` (`production` when the
  production query endpoint returns it, `test`, `unconfirmed` when morpholib's `published.json`
  says production but the endpoint does not, or `unpublished`), the bundle's `REPORT.md`, verdict,
  score and weight of evidence, and, for audits of a Thompson claim, morpholib's own
  `thompson_1917_claims.json` entry and its verdict.
- `links`: `claim` (an id in `docs/claims.json`) ← `morpholib` (an id in `claims`), with a one-line
  `note`.
  - `tests`: the audit measured the claim's own assertion on specimens or data.
  - `models`: the audit simulates the mechanism the claim proposes, without checking its assertion.

The MorphoEval `verdict` (faithful, mostly faithful, …) grades whether the simulation reproduces
the specimens, not whether the claim is true. For the Thompson audits, `thompson.verdict`
(supported, mixed) is the verdict on Thompson's claim. Neither sets a claim's `evidence`, which
comes only from `test-data/claim-tests/`.

The links were judged, not computed: TF-IDF over label, statement and the audit's
`reported_in_source` proposed up to 15 candidate claims per audit (every claim in the same chapter
for Thompson audits), and each candidate was then accepted or rejected by reading both. Most were
rejected; shared topic or vocabulary is not enough.

`node scripts/site/build-claim-graph.mjs` attaches the links to each claim as `morpholib` in
`docs/claims.json` and fails if a link names a claim that no longer exists. Over MCP, the claim
tools return them in `status.morpholib`, and `delphi_graph` takes `morpholib: "tests" | "models" | "any"`.

`python3 scripts/site/morpholib-thumbs.py` fetches each linked model's committed animation from
morpholib's `docs/media/` at the pinned commit, takes its final frame and writes a small JPEG to
`docs/thumbs/<morpholib-id>.jpg`, with `docs/thumbs/index.json` recording the source file and
frame. The claim graph shows it as the picture on the claim's card (black frame: the model tests
the claim; grey: it models the mechanism), and `docs/claims.json` carries it as `thumbnail`. Run
it after changing `links.json` or its pinned commit; models with no media are listed under
`no_media` in the index.
