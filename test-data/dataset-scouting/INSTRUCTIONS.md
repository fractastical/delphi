# Instructions for a dataset scout

You are one agent in a swarm. You get a list of claim ids from a queue file
(`test-data/dataset-scouting/queue/<slice>.json`). For each claim you locate the public datasets
that contain the variables needed to test it, check that they really exist and really hold those
variables, and write what you found. You do **not** run the test.

## What to write

One directory per claim, nothing else:

```
test-data/dataset-scouting/<project>/<claim-id>/datasets.json
test-data/dataset-scouting/<project>/<claim-id>/REPORT.md     (optional, ≤ 40 lines)
```

`<project>` is the queue entry's `project`. Never write outside your own claim directories;
other scouts are writing their claims at the same time.

## How to scout one claim

1. Read the queue entry: `statement`, `operationalizations` (what each assessor proposed to
   measure), `obstacles`, and `candidate_datasets` (datasets the assessors already named, with
   how many of them named each). Write down the two to five **variables** a test needs
   (`variables_needed`), e.g. "adult body mass per species", "minimum gliding airspeed".
2. For **each assessor-named dataset**: fetch its landing page or API with `curl -sIL` /
   `curl -s` (or `python3 -c "import requests..."`), record the HTTP status and what you saw,
   and decide: `holds` (the variables are there, openly downloadable), `partial` (some
   variables, or wrong scope/resolution), `rejected` (exists but does not contain the
   variables, or is a paper/portal rather than a dataset), `unreachable` (no response or auth
   wall), `not-found` (the name does not resolve to anything). Prefer an API call that
   returns a record count or field list over a landing page; say what you queried.
3. **Search for datasets the assessors missed**, in at least two of: GBIF / OBIS / PBDB /
   FishBase / AnAge APIs (the adapters in `test-data/organisms/claim-tests/fetch.py` show the
   endpoints), DataCite (`https://api.datacite.org/dois?query=...`), Dryad
   (`https://datadryad.org/api/v2/search?q=...`), Zenodo (`https://zenodo.org/api/records?q=...`),
   Figshare, BioImage Archive / IDR / EMPIAR, MorphoSource, Wikidata SPARQL. Log every search
   in `search_log` with the URL and hit count, even when it found nothing.
4. Give the claim a status: `data-ready` (at least one `holds` dataset covers all variables),
   `partial` (datasets cover some variables, or a restricted scope), `gap` (nothing found; say
   what would need to be compiled), `not-empirically-resolvable` (the claim has no measurable
   consequence; say why in one sentence).
5. Write `datasets.json`, then run `node test-data/dataset-scouting/validate.mjs <project>/<claim-id>`.

Budget: about 10 minutes and 15 HTTP requests per claim. If a source is rate-limited, note it
and move on. Reuse what the organisms project already vendored:
`test-data/organisms/merged/datasets.json` lists 2,159 provenanced dataset records keyed by taxon;
if one covers your variables, cite its `id` in `reuses_organism_dataset`.

## Rules

- **Only what you fetched.** Every `landing_url`, `access_url`, DOI and number in
  `datasets.json` must come from a response you received, with its `http_status` recorded.
  Never invent a URL, accession, DOI, row count or licence. Unknown is `null`.
- **Describe, don't test.** Do not compute the statistic the claim needs, do not state whether
  the data support the claim. Tests are pre-registered in `test-data/claim-tests/` later; your
  job is to make that possible. "The table has 21,322 species with body mass" is fine; "mass
  scales as length^3" is not.
- **Scope as stated.** Judge datasets against the claim's own scope. A dataset on one species is
  `partial` for a claim about all vertebrates.
- Don't touch claim files, assessments, nanopubs, `site/`, or anything under `test-data/claim-tests/`.
- Don't download anything over 1 MB; a HEAD request or an API count is enough.
- Don't score or rank; `verdict` values are about the dataset's fit, never a probability.

## `datasets.json`

```json
{
  "claim_id": "thompson1917-ch02-06",
  "project": "thompson-growth-form",
  "scouted_at": "2026-10-31T23:10:00Z",
  "scout": { "kind": "cursor-subagent", "model": "<model id>", "run": "<slice or session id>" },
  "variables_needed": ["wing or fin area per species", "body mass per species", "measured flight speed"],
  "datasets": [
    {
      "id": "amniote-life-history-database-aug-2015",
      "name": "Amniote life-history database (Myhrvold et al. 2015)",
      "landing_url": "https://esapubs.org/archive/ecol/E096/269/",
      "access_url": "https://esapubs.org/archive/ecol/E096/269/Data_Files/Amniote_Database_Aug_2015.csv",
      "doi": "10.1890/15-0846R.1",
      "license": null,
      "suggested_by": ["gpt", "grok"],
      "checked": { "at": "2026-10-31T23:05:12Z", "method": "HEAD access_url", "http_status": 200, "bytes": 4728122 },
      "variables_present": ["adult body mass per species"],
      "variables_missing": ["wing area", "flight speed"],
      "scope": "21,322 amniote species; birds 9,802",
      "evidence": "Content-Length 4728122; column header from first 2 KB lists adult_body_mass_g, ...",
      "verdict": "partial",
      "reuses_organism_dataset": "amniote-life-history-database-aug-2015"
    }
  ],
  "search_log": [
    { "source": "DataCite", "query": "bird wing loading flight speed", "url": "https://api.datacite.org/dois?query=...", "hits": 14, "note": "two relevant: ..." }
  ],
  "status": "partial",
  "summary": "Body mass is in AnAge and the amniote database; wing area and measured speed exist only in Alerstam et al. 2007 (PLoS Biol, supplementary table), which is a paper supplement, not a repository dataset.",
  "next_step": "Compile Alerstam 2007 S1 + Greenewalt 1962 into one table; then pre-register the exponent test.",
  "obstacles_confirmed": ["No repository holds measured flight speeds across >100 species."]
}
```

Field rules (checked by `validate.mjs`): `claim_id` equals the directory name; `status` and each
dataset `verdict` take only the values above; every dataset has `landing_url` (http(s)),
`checked.http_status` (integer or `null` with a `checked.note`), `suggested_by` (array, may be
empty: then you found it), `verdict`; `search_log` has at least one entry; `scout` has `kind`,
`model`, `run`; no `assessment`, `p_true`, `truth` or `verdict` key at the top level.
