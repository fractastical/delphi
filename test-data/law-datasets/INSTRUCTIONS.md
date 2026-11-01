# Instructions for a law scout

You are one agent in a swarm. Your slice is **one law in one kingdom** (`plants`, `animals` or
`fossils`; `fossils` covers fossil plants and fossil animals). Find as many real papers and datasets
as you can where the law's quantity is measured, tested or can be extracted, check each against the
live source, and write one record. You do **not** run the test, and you do not say whether a source
supports the law.

Your queue entry is `test-data/law-datasets/queue/<law>/<kingdom>.json`. It has the law, its claim
ids and statements, the variables needed, what to look for in this kingdom, datasets the assessors
already named for those claims, datasets already vendored by the organisms project, and what
the claim scouts already found.

## What to write

Exactly one file: `test-data/law-datasets/records/<law>/<kingdom>.json`. Never write anywhere else;
other scouts are writing their slices at the same time.

## Goal and budget

Breadth with verification. Aim for **25 to 50 distinct sources** (at least 10 unless the kingdom is
genuinely thin; then set `gap_note` saying what you searched and why it is thin). Spread them: different taxa groups,
different methods, different decades, different data holders. Prefer:

1. **Open datasets** with a download (Dryad, Zenodo, Figshare, MorphoSource, GBIF, PBDB, Neotoma,
   FishBase, AnAge, Tallo, TRY, BioImage Archive, Movebank, GenBank, supplementary tables).
2. **Papers that report the measured quantity** across many specimens or species (cite the DOI and say where the numbers are).
3. Specimen collections or atlases (scans, cleared-leaf collections, museum image archives).
4. Context papers only when nothing better exists for a sub-group.

Include sources that look unfavourable to the law as well as favourable ones. Pick by whether the
data bear on the law, never by whether they flatter it. Do not label any source as supporting or
refuting.

About 60 HTTP requests in total is reasonable. Work through APIs that return counts and metadata:
Crossref (`https://api.crossref.org/works?query=...&rows=20`), DataCite
(`https://api.datacite.org/dois?query=...`), Dryad (`https://datadryad.org/api/v2/search?q=...`),
Zenodo (`https://zenodo.org/api/records?q=...`), GBIF (`https://api.gbif.org/v1/...`), PBDB
(`https://paleobiodb.org/data1.2/...`), OpenAlex (`https://api.openalex.org/works?search=...`),
Europe PMC (`https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=...&format=json`),
Neotoma, FishBase via `https://fishbase.ropensci.org`, BioImage Archive, MorphoSource, Wikidata.
Log every search in `search_log`, including empty ones.

## Rules

- **Only what you fetched.** Every `url`, `access_url`, DOI, title, year, record count, licence
  and quotation must come from a response you received, with `checked.http_status` recorded. Never
  invent or reconstruct a DOI, accession, URL, author list or number from memory. Unknown is `null`.
  A source you cannot reach is `unreachable` or `not-found`, not guessed.
- **Quotes are verbatim.** `reported.quote` (at most 400 characters) is copied from the abstract,
  landing page, API response or table you fetched, and `reported.locator` says where. If you did not
  read the text, leave `reported` as `null`.
- **Describe, don't test.** Do not compute the law's statistic, do not write a verdict on the law,
  and do not use the words supports, refutes or confirms about a source. "Reports b = 3.01 for 142
  fish species (quote, abstract)" is fine; "so the cube law holds" is not.
- **Scope as stated.** A dataset on one species is `partial` for a claim about all vertebrates.
- No dummy data: no templated records, no placeholder IDs, no synthetic numbers.
- Don't download anything over 1 MB. A HEAD request, an API count or the first KB is enough.
- Don't touch claim files, assessments, nanopubs, `docs/`, `claim-tests/` or other slices.
- For fossils, give `geologic_age` (`interval`, `ma_min`, `ma_max`) from the source or PBDB when the source is about specimens or occurrences.

## Record format

```json
{
  "law_id": "log-spiral",
  "kingdom": "fossils",
  "scouted_at": "2026-11-01T01:18:00Z",
  "scout": { "kind": "cursor-subagent", "model": "<your model id>", "run": "log-spiral/fossils" },
  "sources": [
    {
      "id": "short-lowercase-slug",
      "type": "paper | dataset | database | specimen-collection | supplement",
      "title": "as returned by the source",
      "authors_year": "First author et al.",
      "year": 2012,
      "doi": "10.xxxx/real-doi-you-fetched",
      "url": "https://landing.page",
      "access_url": "https://direct.download or API url (or null)",
      "license": "CC BY 4.0 (or null)",
      "open_access": true,
      "taxa": [ { "name": "Ammonoidea", "rank": "class", "group": "ammonoids" } ],
      "geologic_age": { "interval": "Jurassic", "ma_min": 145, "ma_max": 201 },
      "measurements": ["whorl expansion rate W", "umbilical ratio D", "shell diameter"],
      "n": "412 specimens, 38 species (as stated by the source)",
      "claims": ["thompson1917-ch13-03"],
      "relevance": "measures-quantity | tests-law-directly | raw-specimens | context",
      "reported": { "quote": "verbatim, at most 400 characters", "locator": "abstract" },
      "checked": { "at": "2026-11-01T01:05:12Z", "method": "GET api.crossref.org/works/<doi>", "http_status": 200 },
      "verdict": "holds | partial | rejected | unreachable | not-found",
      "evidence": "what the response showed (required when verdict is holds)",
      "variables_present": ["..."],
      "variables_missing": ["..."],
      "suggested_by": ["gpt"]
    }
  ],
  "coverage": {
    "groups_covered": ["ammonoids", "gastropods"],
    "intervals_covered": ["Devonian", "Jurassic"],
    "gaps": ["no brachiopod coiling dataset found"]
  },
  "search_log": [ { "source": "Crossref", "query": "ammonoid coiling log spiral", "url": "https://api.crossref.org/works?query=...", "hits": 312, "note": "kept 9" } ],
  "summary": "Two or three sentences: how much was found, from where, what is thin.",
  "gap_note": null
}
```

`verdict` is about the source's fit to the variables: `holds` (the variables are there and open),
`partial` (some variables, wrong scope, behind a paper's supplement), `rejected` (exists but does
not contain them, or is a different thing), `unreachable`, `not-found`. Each source's `claims`
must be claim ids of this law. `remediation` and `dropped` are added by later rounds; leave them out.

When done, run `node test-data/law-datasets/validate.mjs <law>/<kingdom>`, fix every error, and
reply with: the number of sources by verdict, the groups covered, and the biggest gap.
