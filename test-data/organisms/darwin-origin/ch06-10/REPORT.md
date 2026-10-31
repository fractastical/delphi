# darwin-origin / ch06-10: animals of *Origin* chapters VI–X

Slice built 2026-10-31 on branch `cursor/organisms-darwin-ch06-10-f86c` from
`claim-sources/darwin-origin/claims.json` (79 claims with `chapter` ∈ {VI, VII, VIII, IX, X}) and
`claim-sources/darwin-origin/inputs/pg1228.txt` lines 5290–10411 (from the heading `CHAPTER VI.` to the line
before `CHAPTER XI.`). Everything was produced by the scripts in `scripts/` (see "How it was
built"); nothing was scored and nothing was published.

## Counts

| quantity | value |
|---|---|
| mentions (`mentions.json`) | **692** — 30 from claim `claim`/`quote` fields (19 distinct claims), 662 from the chapter text with file/line locators |
| distinct animal taxa (`taxa/*.json`) | **153** — 23 named in claims (required), 130 found only in the chapter text |
| ranks | 48 species, 40 genera, 25 families, 14 orders, 8 classes, 3 phyla, 2 subphyla, 10 other intermediate ranks, 3 historical grades (`pisces`, `ganoidei`, `pachydermata`) |
| resolved to GBIF backbone `usageKey` | **136** (+5 taxa represented by `gbif_components`, see below; 12 with no GBIF node) |
| resolved to NCBI Taxonomy | **146** |
| resolved to Wikidata | **152** (all but `ganoidei`) |
| resolved to ITIS | 139 |
| resolved to WoRMS (marine taxa) | 18 |
| resolved to Paleobiology Database (fossil taxa) | 12 |
| dataset records (`datasets/*.json`) | **224** — 141 GBIF occurrence counts, 33 PBDB occurrence counts, 42 NCBI reference genome assemblies, 7 shared databases (GBIF backbone, AnAge 15, PanTHERIA 1.0, Amniote LHD 2015, EltonTraits 1.0, AVONET v7, FishBase 25.04), 1 WoRMS record |
| taxa with no dataset | **1** (`pachydermata`, see below) |
| required (claim) taxa without a GBIF count + trait/reference dataset | 0 |

Every claim-mentioned taxon has at least one dataset record (all but `ammonoidea`, which has
only its PBDB count, have two or more); every one of the 153 taxa except `pachydermata` has at
least one, and all but 14 have at least one dataset beyond GBIF.

### Shared databases: rows found for slice taxa

| record | file rows | slice taxa covered | checksum |
|---|---|---|---|
| `anage-build-15` | 4,645 species | 103 | sha256 of `dataset.zip` (169,150 B) |
| `pantheria-1-0-wr05` | 5,416 mammal species | 40 | sha256 of `PanTHERIA_1-0_WR05_Aug2008.txt` (2,359,096 B) |
| `amniote-life-history-database-2015-08` | 21,322 amniote species | 92 | sha256 of `Amniote_Database_Aug_2015.csv` (4,728,122 B) |
| `eltontraits-1-0` | 9,993 birds + 5,400 mammals | 81 | sha256 of `BirdFuncDat.txt` and `MamFuncDat.txt` |
| `avonet-v7` | 11,009 bird species (sheet AVONET1_BirdLife) | 47 | sha256 of `AVONET Supplementary dataset 1.xlsx` (21,524,673 B); Figshare MD5 also verified |
| `fishbase-v25-04` | 36,132 fish species | 9 | sha256 of `species.parquet` and `families.parquet`; equal to the Hugging Face LFS oids |
| `worms-aphia-records-2026-10-31` | 18 Aphia records | 18 | API records, no file |

`rows_for_taxa` in each record gives the per-taxon row count. A species row is counted for the
species and for every listed higher taxon it belongs to (e.g. a *Parus major* row counts for
`parus-major`, `aves`); `n_rows_for_taxa` is therefore the sum over nested taxa, as its
description states. None of the downloaded files is committed (all but AnAge exceed 1 MB; AnAge
is kept out for consistency); the sha256 and byte size of each are in the record.

## How "animal named in a claim" was decided

The 23 required taxa come from the `claim` and `quote` fields: bats (`chiroptera`), upland
goose, woodpeckers, crustaceans and "the great Articulate class", vertebrates, "fishes" with
electric organs, monkey / horse / bat / seal, mammals, birds, the cuckoo, ants, hive-bee,
humble-bees, Melipona, (neuter) insects, the driver ant, ammonites, marsupials and edentates, and
"shells" (ch. IX-04, counted under Mollusca). Generic words ("animal", "domestic animals",
"organic beings", "palæontologists") were not treated as taxa.

## Resolution decisions and ambiguities

- **Breeds → species.** Pointer, retriever, shepherd-dog, bull-dog, greyhound, terrier and
  German Spitz are `canis-familiaris`; tumbler, fantail, pouter, carrier and rock-pigeon are
  `columba-livia`; short-horn and "humped Indian cattle" are `bos-taurus`; mule and hinny are
  recorded under `equus-asinus` with the parent species noted. Breed names are kept in
  `names_as_written`. GBIF's accepted name for the dog is *Canis lupus familiaris* (subspecies
  key 6164210), which is what the taxon file carries.
- **Archaic names.** *Galeopithecus* → Cynocephalidae (both colugos were placed in it);
  *Micropterus* of Eyton (logger-headed duck) → *Tachyeres*; *Saurophagus sulphuratus* →
  *Pitangus sulphuratus*; *Puffinuria berardi* → *Pelecanoides*; *Formica (Polyerges)
  rufescens* → *Polyergus rufescens*; *F. flava* → *Lasius flavus*; *Cryptocerus* →
  *Cephalotes*; *Anomma* → *Dorylus*; *Cervulus vaginalis* / *Reevesii* → *Muntiacus muntjak* /
  *M. reevesi*; *P. torquatus* → *Phasianus colchicus*; *Mustela vison* → *Neogale vison*
  (GBIF still accepts *Mustela vison*, key 5218823; NCBI and ITIS use *Neogale vison*);
  *Cobites* → *Cobitis*; "Mastodon" → *Mammut* (Darwin's La Plata mastodon is now
  *Notiomastodon*, noted in the file); "Edentata" → Xenarthra; "Batrachians" → Amphibia;
  "Articulata" → Arthropoda (Cuvier's Articulata also held annelids, which have their own
  entry).
- **Vernaculars resolved above species.** "monkey" → Primates, "seal" → Phocidae, "otter" →
  *Lutra*, "mice"/"rodents" → Rodentia, "vulture" → Accipitriformes (vultures are
  polyphyletic), "eagle" → Accipitridae, "Rays" with Matteucci's pseudo-electric organ →
  Rajiformes (skates), "petrels" → Procellariiformes, "thrushes" → Turdidae but "the thrush of
  South America / our British thrush" → *Turdus*, "jackals" → *Canis*, "sloth"/"anteater" →
  Folivora/Vermilingua, "gigantic birds of New Zealand" → Dinornithiformes, "flying reptiles" →
  Pterosauria, "ground woodpecker of La Plata" → *Colaptes campestris*.
- **Taxa without a GBIF backbone node.** GBIF only carries kingdom–species ranks, and its
  current backbone has no Reptilia, Actinopterygii, Marsupialia (only a spurious "family"
  record), Xenarthra (treated as a synonym of Cingulata), Pinnipedia (synonym of Phocidae),
  Batoidea, Teleostei, Ruminantia, Cirripedia, Crustacea (only a doubtful genus), Coccoidea,
  Ammonoidea, Pterosauria, Dinornithiformes, Vertebrata or Folivora/Vermilingua. Where a small
  set of accepted GBIF taxa covers the Darwin taxon, the taxon file lists them in
  `gbif_components` (Marsupialia = 7 orders; Reptilia = Squamata + Testudines + Crocodylia +
  Sphenodontia; Xenarthra = Cingulata + Pilosa; Folivora = Bradypodidae + Megalonychidae;
  Vermilingua = Myrmecophagidae + Cyclopedidae) and the GBIF occurrence record gives one count
  per component and the sum. Ray-finned fishes are ~45 orders directly under Chordata in GBIF,
  so no component list was made for `pisces`; its datasets are FishBase and AnAge.
- **Historical grades.** `pisces` ("fishes", Wikidata Q152), `ganoidei` (Agassiz's Ganoid
  fishes; counted in FishBase as the classes Chondrostei + Holostei + Cladistii; no Wikidata
  item for the historical group, the search only returns Chondrostei) and `pachydermata`
  (Cuvier's polyphyletic order, Wikidata Q1921355) have no GBIF/NCBI/ITIS node; this is stated
  in the files.
- **NCBI synonyms.** NCBI returns *Pancrustacea* for "Crustacea" and *Metatheria* for
  "Marsupialia"; both are recorded with `ncbi_scientific_name` showing the NCBI name.
- **Only `pachydermata` has no dataset**: it is an abandoned polyphyletic group mentioned three
  times in ch. X as Cuvier's order; no modern database has a row for it and a sum over
  elephants, hippos, pigs, horses, rhinos and tapirs would misrepresent the concept. The 14
  taxa with GBIF-only coverage are insects and a cnidarian (ant genera, Melipona, Dorylus,
  Vespidae, Sphecidae, Ichneumonidae, Aphididae, Odonata, Pieris, Hydra) for which none of the
  vendored trait databases has rows; BOLD or Open Tree of Life would be the next sources.
- **Datasets that could not be vendored.** FishBase has no official bulk download and
  `fishbase.ropensci.org` now serves an invalid certificate; the rOpenSci/rfishbase parquet
  snapshot on Hugging Face (v25.04, CC BY-NC 4.0) was used instead and its checksums match the
  LFS oids. The GBIF and PBDB web landing pages, the ESA `esapubs.org` directories, Figshare's
  HTML page and Wiley DOI landing pages return 403/202 to automated requests; every DOI was
  verified instead through the handle-system API (`https://doi.org/api/handles/<doi>`), GBIF
  dataset existence through the GBIF API, and all download URLs were actually fetched.
- **Mentions.** Text mentions are matched per line with hand-tuned patterns (`scripts/taxa_seed.py`);
  false positives such as "bear in mind", "fly-flapper", "hen ostriches" (→ ostrich, not fowl)
  and "upland geese" (→ *Chloephaga*, not *Anser*) are excluded explicitly. "man" is recorded
  only where Darwin names humans as organisms ("the races of man"), not as breeder or
  observer. A line that names several taxa yields one mention per taxon.

## Non-animal taxa seen (not built)

Plants: *Hippeastrum*, *Verbascum*, *Nicotiana*, *Crinum*, *Lobelia* (incl. *L. fulgens*),
*Rhododendron ponticum* / *R. catawbiense*, *Dianthus*, *Calceolaria*, *Pelargonium*,
*Fuchsia*, *Passiflora*, *Anagallis*, *Silene*, *Mirabilis*, *Matthiola*, *Robinia*, *Sorbus*,
*Orchis* and other orchids, maize, cabbage, dock-plant, heath, yew, fir, pear, apple,
gooseberry, grass; algae: *Fuci*. "Coral Reefs" (ch. IX) is the title of Darwin's book, not a
taxon mention. No fungi or microbes were found in these chapters.

## How it was built

```
python3 test-data/organisms/darwin-origin/ch06-10/scripts/build_mentions.py   # mentions.json from claims + text
python3 test-data/organisms/darwin-origin/ch06-10/scripts/resolve_taxa.py     # taxa/<slug>.json via GBIF, NCBI, Wikidata, ITIS, WoRMS, PBDB
python3 test-data/organisms/darwin-origin/ch06-10/scripts/build_datasets.py   # downloads, checksums, counts -> datasets/*.json; fills taxa[].datasets
python3 test-data/organisms/darwin-origin/ch06-10/scripts/check_records.py    # link symmetry, placeholders, every identifier and URL re-resolved
```

`taxa_seed.py` is the curated list of 153 taxa with the name patterns, resolution notes and
false-positive exclusions. API responses are cached under `/tmp/organisms-cache/` and downloads
under `/tmp/organisms-cache/dl/`; neither is committed. `check_records.py` passed with 0
problems; its 184 warnings are all 403 responses from human-facing landing pages whose
machine-readable counterparts resolved.
