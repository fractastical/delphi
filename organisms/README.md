# Organisms: reference data for every animal Darwin and Thompson mention

For each animal named in *On the Origin of Species* (1859) and *On Growth and Form* (1917) we
want: the resolved taxon, where it is mentioned, and the public reference datasets that describe
it, each with the metadata and provenance the ontology's
[dataset convention](https://github.com/fractastical/project-delphi-ontology/blob/main/ONTOLOGY.md#dataset-convention)
requires, so each can later be published as a `dcat:Dataset` nanopub and cited by claims with
`prov:used`.

Layout (one directory per extraction slice so parallel agents never write the same file):

```
organisms/<project>/<slice>/mentions.json
organisms/<project>/<slice>/taxa/<slug>.json
organisms/<project>/<slice>/datasets/<dataset-id>.json
organisms/<project>/<slice>/REPORT.md
```

`<project>` is `darwin-origin` or `thompson-growth-form`; `<slice>` is a chapter range such as
`ch01-05`. Duplicates across slices are merged later by identifier (GBIF key / Wikidata QID).

Run `node organisms/validate.mjs [<project>/<slice>]` before committing; it checks the field
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
`{ "file": "darwin-origin/inputs/pg1228.txt", "line_start": 1234, "line_end": 1236 }`.

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
node organisms/validate.mjs
node organisms/merge.mjs        # -> organisms/merged/{taxa,datasets,mentions}.json, SUMMARY.md
```

`merge.mjs` unifies taxa across slices and projects by GBIF key (else Wikidata QID, else NCBI
taxid), unions names, mentions and datasets, merges shared-database records by id, and lists
identifier conflicts for a human to resolve. The merged files are the input for the
`dcat:Dataset` nanopub builder and the dataset-reliability assessment pass.
