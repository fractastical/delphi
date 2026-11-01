# Organisms: reference data for every animal Darwin and Thompson mention

For each animal named in *On the Origin of Species* (1859) and *On Growth and Form* (1917) we
want: the resolved taxon, where it is mentioned, and the public reference datasets that describe
it, each with the metadata and provenance the ontology's
[dataset convention](https://github.com/fractastical/project-delphi-ontology/blob/main/ONTOLOGY.md#dataset-convention)
requires, so each can later be published as a `dcat:Dataset` nanopub and cited by claims with
`prov:used`.

Someone can ask for a species, or a designed organism, to be tested from the public form at
`docs/test-organism.html` (https://delphibio.org/test-organism.html), rebuilt with
`node scripts/site/build-organism-form.mjs`. Sending the form opens a GitHub issue. That issue
is a request: it is not a taxon file, a dataset record, or a pre-registered test, and the form
does not resolve identifiers.

Layout (one directory per extraction slice so parallel agents never write the same file):

```
test-data/organisms/<project>/<slice>/mentions.json
test-data/organisms/<project>/<slice>/taxa/<slug>.json
test-data/organisms/<project>/<slice>/datasets/<dataset-id>.json
test-data/organisms/<project>/<slice>/REPORT.md
```

`<project>` is `darwin-origin`, `thompson-growth-form` or `aristotle-biology`; `<slice>` is a chapter range such as
`ch01-05`. Duplicates across slices are merged later by identifier (GBIF key / Wikidata QID).

Run `node test-data/organisms/validate.mjs [<project>/<slice>]` before committing; it checks the field
rules below, cross-references, the 1 MB limit and that no record carries an `assessment`.

## Slices

Line numbers refer to the Project Gutenberg text in `<project>/inputs/`. Claim ids for a slice
are those whose chapter key (`darwin1859-ch03-…`, `thompson1917-ch11-…`) falls in the range.

| project | slice | chapters | text lines |
|---|---|---|---|
| darwin-origin | `intro-ch02` | Introduction, I–II | 313–2063 |
| darwin-origin | `ch03-04` | III–IV | 2064–4139 |
| darwin-origin | `ch05-06` | V–VI | 4140–6369 |
| darwin-origin | `ch07-08` | VII–VIII | 6370–8460 |
| darwin-origin | `ch09-10` | IX–X | 8461–10411 |
| darwin-origin | `ch11-12` | XI–XII | 10412–12300 |
| darwin-origin | `ch13-14` | XIII–XIV | 12301–14617 |
| thompson-growth-form | `ch01-02` | I–II | 980–2579 |
| thompson-growth-form | `ch03` | III | 2580–5906 |
| thompson-growth-form | `ch04-05` | IV–V | 5907–9881 |
| thompson-growth-form | `ch06-07` | VI–VII | 9882–12091 |
| thompson-growth-form | `ch08` | VIII | 12092–14081 |
| thompson-growth-form | `ch09-10` | IX–X | 14082–16506 |
| thompson-growth-form | `ch11` | XI | 16507–19560 |
| thompson-growth-form | `ch12-14` | XII–XIV | 19561–21574 |
| thompson-growth-form | `ch15-epilogue` | XV–XVII, Epilogue | 21575–28917 |
| aristotle-biology | `ha01-04` | History of Animals I–IV | `ha.txt` 6–659 |
| aristotle-biology | `ha05-06` | History of Animals V–VI | `ha.txt` 660–1186 |
| aristotle-biology | `ha07-09` | History of Animals VII–IX | `ha.txt` 1187–1783 |
| aristotle-biology | `pa01-04` | Parts of Animals I–IV | `pa.txt` 6–481 |
| aristotle-biology | `ga01-05` | Generation of Animals I–V | `ga.txt` 6–505 |

For Aristotle the texts are `claim-sources/aristotle-biology/inputs/{ha,pa,ga}.txt` and a slice's
claims are those whose id starts with its work and book (`aristotle-ha01-…` to `aristotle-ha04-…`
for `ha01-04`). His animal names are Greek kinds in a 1910 translation ("the cestreus", "the
glanis", "the trochilus"); resolve them through the translator's identification where the
standard commentaries agree, and record the uncertainty in `notes` and `REPORT.md` otherwise.

### Claim-test slices

`claim-tests/<slice>` holds the animal species the data tests in `test-data/claim-tests/` actually
measured, which are often not the taxa the book names (the cube-law test `thompson1917-ch02-01`
uses twenty North Sea fish and jellyfish). Each slice is generated, not hand-written:

```sh
python3 test-data/organisms/claim-tests/candidates.py validated --exclude-lean   # -> validated/species.json
uv run --with pyarrow test-data/organisms/claim-tests/fetch.py validated         # -> taxa/, datasets/, mentions.json, REPORT.md, PROFILES.md, files/
```

| slice | claims | species |
|---|---|---|
| `lean-tested` | the five claims with a Lean proof and a data verdict (`thompson1917-ch02-01`, `ch03-07`, `ch07-04`, `ch07-11`, `ch17-06`); `species.json` written by hand | 26 |
| `validated` | the other biological claims with a supports or mixed verdict; 28 of the 46 count genera or regions and name no species | 110 |

`fetch.py` queries every axis `coverage.mjs` scores (GBIF, Wikidata, NCBI Taxonomy and Datasets,
WoRMS, OBIS, BOLD, PBDB, IUCN via GBIF, MorphoSource, DANDI, Open Tree, FishBase/SeaLifeBase,
AnAge), writes a dataset record only when a source returned data and lists the empty ones as gaps
in `REPORT.md`. It vendors every FishBase/SeaLifeBase row for each species in
`files/lifebase/<slug>.json` and a per-species summary of all sources in `files/profiles/<slug>.json`.
`species.json` entries may set `accepted_name` and `wikidata_qid` where the GBIF backbone still
uses an older name, so the merge does not report a conflict.

## Rules

- **Animals only** (kingdom Animalia). Record plants, fungi and microbes you notice in
  `REPORT.md` under "Non-animal taxa seen" so they can be done later, but do not build records.
- **Resolve every taxon** to real identifiers: GBIF backbone `usageKey`
  (`https://api.gbif.org/v1/species/match?name=...`), NCBI Taxonomy id, Wikidata QID; add ITIS,
  WoRMS, or other authorities when they apply. Keep the name as the author wrote it
  (`name_as_written`) separate from the accepted name. Archaic or vernacular names ("the
  rock-pigeon", "Nautilus", "the Foraminifera") are resolved to the best matching rank, which
  may be above species.
- **Only real datasets.** Every dataset record names a dataset that exists, with its official
  landing page or DOI. Never invent a name, DOI, URL, accession, count or checksum. Prefer
  curated, citable sources: GBIF (occurrence counts via the API), NCBI Datasets / ENA (genome
  assemblies), AnAge, PanTHERIA, AVONET, Amniote Life-History Database, FishBase, EltonTraits,
  TRY is plants (skip), MorphoSource and Phenome10K (3D morphology), Open Tree of Life / TimeTree
  (phylogeny), Paleobiology Database (fossils), BOLD (barcodes), IUCN Red List (status).
- **Vendor small, checksum everything.** Download only files you actually inspect, record
  `byte_size` and `sha256`, and do not commit data over 1 MB. Record API queries as
  distributions with the exact URL and the retrieved count.
- **Do not score.** The agent that vendors a dataset does not assess it (ontology rule).
  Reliability scoring (source authority, integrity, completeness, independence, authenticity) is
  a separate pass by a different agent; leave `assessment` absent.
- **Do not touch** claim files, assessments, nanopubs; never sign or publish.

## `mentions.json`

Array, one entry per mention:

```json
{
  "taxon_slug": "columba-livia",
  "name_as_written": "rock-pigeon",
  "source": { "claim_id": "darwin1859-ch01-09" },
  "quote": "…verbatim phrase containing the mention…"
}
```

For mentions found in the book text but not in a claim, `source` is
`{ "file": "claim-sources/darwin-origin/inputs/pg1228.txt", "line_start": 1234, "line_end": 1236 }`.

## `taxa/<slug>.json`

```json
{
  "slug": "columba-livia",
  "accepted_name": "Columba livia",
  "rank": "species",
  "vernacular": ["rock pigeon", "rock dove"],
  "names_as_written": ["rock-pigeon", "C. livia"],
  "identifiers": {
    "gbif_usage_key": 2495414,
    "ncbi_taxid": 8932,
    "wikidata_qid": "Q10856",
    "itis_tsn": null,
    "worms_aphia_id": null
  },
  "lineage": { "phylum": "Chordata", "class": "Aves", "order": "Columbiformes", "family": "Columbidae" },
  "mentioned_in": ["darwin1859-ch01-09", "darwin1859-ch01-10"],
  "datasets": ["gbif-occurrences-columba-livia-2026-10-31", "ncbi-genome-gca-001887795-1"],
  "notes": "Darwin's domestic breeds are all C. livia."
}
```

## `datasets/<dataset-id>.json`

Field names map one-to-one onto the dataset convention terms shown in brackets.

```json
{
  "id": "anage-build-15",
  "label": "AnAge: The Animal Ageing and Longevity Database, build 15",
  "identifier": "https://genomics.senescence.info/species/",
  "doi": "10.1093/nar/gkx1042",
  "bibliographic_citation": "Tacutu R, et al. (2018) Human Ageing Genomic Resources: new and updated databases. Nucleic Acids Res 46:D1083–D1090.",
  "is_referenced_by": "https://doi.org/10.1093/nar/gkx1042",
  "creators": ["Tacutu R", "de Magalhães JP", "..."],
  "issued": "2017-11",
  "license": "CC BY 3.0",
  "version": "build 15",
  "distributions": [
    {
      "download_url": "https://genomics.senescence.info/species/dataset.zip",
      "media_type": "application/zip",
      "byte_size": 1234567,
      "sha256": "…",
      "retrieved_at": "2026-10-31T05:12:00Z",
      "inspected": true
    }
  ],
  "counts": [
    { "property_id": "n_species", "value": 4645, "description": "species rows in anage_data.txt as distributed" },
    { "property_id": "n_rows_for_taxa", "value": 3, "description": "rows matching the taxa listed below" }
  ],
  "measurement_technique": "Literature-compiled life-history traits (maximum longevity, body mass, maturity).",
  "taxa": ["columba-livia", "canis-familiaris"],
  "role": "maximum longevity and adult body mass for the listed taxa",
  "integrity": { "identifier_resolves": true, "checksum_verified": true, "checked_at": "2026-10-31T05:12:00Z" },
  "vendored_by": { "kind": "cloud-agent", "model": "<model id>", "run": "<branch or agent id>", "date": "2026-10-31" }
}
```

Dataset ids are lowercase slugs including a version or date. Shared databases (AnAge, GBIF
backbone) get **one** record per slice listing all taxa they cover; taxon-specific queries
(GBIF occurrence counts, a genome assembly) get their own record.

## `REPORT.md`

Counts of mentions, distinct taxa, taxa resolved to each authority, datasets built, taxa with no
usable dataset and why, non-animal taxa seen, and anything ambiguous.

## Collecting results

Each slice is produced by one cloud agent on its own `cursor/organisms-*` branch, touching only
its slice directory, so the branches merge into `main` without conflicts:

```sh
git fetch origin 'refs/heads/cursor/*:refs/remotes/origin/cursor/*'
for b in $(git branch -r | grep -E 'origin/cursor/.*organisms'); do git merge --no-edit "$b"; done
node test-data/organisms/validate.mjs
node test-data/organisms/merge.mjs        # -> test-data/organisms/merged/{taxa,datasets,mentions}.json, SUMMARY.md
node test-data/organisms/coverage.mjs     # -> test-data/organisms/merged/coverage.json, COVERAGE.md
```

`coverage.mjs` ranks every taxon by how many data axes our records cover (genome sequencing
graded by assembly level, bioelectric/electrophysiology, DNA barcodes, trait tables, 3D
morphology, phylogeny, occurrences, fossils, conservation status, taxonomic resolution). Axes
with no records yet (bioelectric, barcodes) are kept so the gap is visible per organism;
`COVERAGE.md` lists the taxa with known electrophysiology sources as leads for that pass.
Dataset records may set `"category": "<axis id>"` to override the id/keyword classification.

## Images and timelines

```sh
node test-data/organisms/images.mjs       # -> test-data/organisms/images/thumbs/<slug>.*, images/manifest.json, merged/timeline.json
python3 test-data/organisms/timeline.py   # -> test-data/organisms/images/timelines/<slug>.png, images/timeline-summary.png, images/mosaic.jpg
```

`images.mjs` vendors one representative picture per merged taxon: the Wikidata item's P18 image
(else the page image of its English Wikipedia article) rendered as a 160 px Commons thumbnail,
with the Commons licence and author recorded next to the file's size and sha256 in
`images/manifest.json`. Taxa with no picture on Commons fall back to GBIF's first still image.
It also collects the dates for a per-taxon timeline into `merged/timeline.json`: the
Paleobiology Database first/last appearance range (`taxa/list?show=app`, for the name itself,
with a rank-matching record preferred among homonyms), the year of formal description from GBIF
authorship, the release years of the NCBI assemblies we hold, and the books that mention the
taxon. Re-runs only fetch what is missing; `--refresh` re-queries everything.

`timeline.py` (matplotlib + Pillow) draws a card per taxon — picture, Phanerozoic range bar on
ICS period colours, and a 1735–2030 axis with description, Darwin 1859, Thompson 1917 and genome
markers — and two summaries: `timeline-summary.png` (ranges of all 700 ranged taxa by class,
with the most-mentioned taxa pictured at their first appearance, plus descriptions and genome
releases per decade) and `mosaic.jpg` (every thumbnail, ordered by first appearance, with a
period-colour stripe). The per-taxon cards are gitignored (~110 MB); thumbnails, manifest,
timeline data and the two summaries are committed. Image licences are CC/public domain as
reported by Commons; check `manifest.json` before reusing a picture outside this repo.

### Tree of life with claims

```sh
node test-data/organisms/tree.mjs             # -> merged/tree.json, images/tree.svg (reuses the cached Open Tree answer)
node test-data/organisms/tree.mjs --refresh   # re-query Open Tree of Life
```

`tree.mjs` draws the inventory as one time-calibrated tree (`images/tree.svg`, ~1200×8200 px,
open it in a browser: boxes have tooltips and link to the claim graph). Topology comes from the
Open Tree of Life synthetic tree: every accepted name is matched with the TNRS (exact matches, the
"Animals" context for metazoan phyla so homonyms in other kingdoms cannot win) and the matched OTT
ids go to `induced_subtree`. A merged taxon that contains another (an order and one of its species)
is an internal node and is labelled there; a taxon that is not monophyletic in the synthetic tree
is attached to the MRCA node Open Tree reports for it (`broken` in `merged/tree.json`). Horizontal
position is the PBDB first appearance from `merged/timeline.json`; an internal node sits at the
oldest first appearance beneath it, which is a lower bound on the clade's age and not a divergence
time. Lineages with no PBDB range are dashed at an arbitrary position. Beside each taxon is one box
per claim that mentions it (`mentioned_in` plus `merged/mentions.json`), coloured from
`docs/claims.json`: theorem, data verdict (supports / mixed / inconclusive / refutes) or untested.
`merged/tree.json` keeps the TNRS matches, the Newick string, the unmatched names (mostly obsolete
or fossil-only names Open Tree does not carry: Pachydermata, Ichthyosauria, Productus), the ids
pruned from the synthetic tree, and each taxon's placement and claim list, with the retrieval time.

`merge.mjs` unifies taxa across slices and projects by GBIF key (else Wikidata QID, else NCBI
taxid), unions names, mentions and datasets, merges shared-database records by id, and lists
identifier conflicts for a human to resolve. The merged files are the input for the
`dcat:Dataset` nanopub builder and the dataset-reliability assessment pass.
