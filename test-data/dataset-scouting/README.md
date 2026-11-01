# Dataset scouting: where is the data to test each claim?

Over a thousand claims are untested but scored as testable, and their dataset-resolvability
assessments name about 3,000 candidate datasets that nobody has checked. This directory holds the
scouting layer between those assessments and the pre-registered tests in
[`test-data/claim-tests/`](../claim-tests/README.md): for one claim, which public datasets exist,
are reachable, and contain the variables a test needs.

Scouting is cheap and embarrassingly parallel, so it is done by a swarm of agents, one slice each,
following [INSTRUCTIONS.md](INSTRUCTIONS.md). A scout describes data; it never runs the test or
says what the data show.

## Pipeline

```sh
node test-data/dataset-scouting/build-queue.mjs --project thompson-growth-form --chapters 1-5 --min-testability 0.5 --out queue/thompson-ch01-05.json
#   untested claims ranked by testability, each with the datasets its assessors named (deduplicated across models)
#   ... scouts write <project>/<claim-id>/datasets.json, one claim directory each ...
node test-data/dataset-scouting/validate.mjs [<project>/<claim-id>]
node test-data/dataset-scouting/merge.mjs          # -> merged/scouting.json, COVERAGE.md
```

`build-queue.mjs` with no filters queues every untested claim (`queue/all.json`); `--ids a,b`
takes specific claims. It skips claims that already have a directory under `test-data/claim-tests/`.

## Layout

```
test-data/dataset-scouting/
  queue/<slice>.json                     what to scout (generated; safe to delete)
  <project>/<claim-id>/datasets.json     one scouting record per claim
  <project>/<claim-id>/REPORT.md         optional notes
  merged/scouting.json                   every record joined to claim labels, plus assessor hit rates
  COVERAGE.md                            generated summary
```

## Statuses

| claim `status` | meaning |
|---|---|
| `data-ready` | at least one open dataset holds every variable the test needs, at the claim's scope |
| `partial` | datasets cover some variables, or a restricted scope or proxy |
| `gap` | nothing public found; the record says what would have to be compiled or measured |
| `not-empirically-resolvable` | the claim has no measurable consequence as stated |

Per dataset, `verdict` is `holds`, `partial`, `rejected` (exists, lacks the variables), `unreachable`
or `not-found`. `suggested_by` lists the assessors that named it; empty means the scout found it.

## What it feeds

- `delphi_claim_tests view: "candidates"` reports each candidate's scouting `status` when a record
  exists, so "what to test next" means testable *and* data located.
- `COVERAGE.md` tallies how often each assessor's dataset guesses held up once checked, a
  calibration of the `data-existence` dimension of the resolvability rubric.
- Gaps are what to post as requests on the forum, The Colony (`hypothesis-needs-testing`) and
  Moltbook: a claim, the variables needed, and that no public dataset has them.
- A `holds` dataset with provenance is the input for a `dcat:Dataset` nanopub that a later test can
  cite with `prov:used`; the record format follows `test-data/organisms/` for that reason.
