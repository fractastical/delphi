# Organism reference data: Darwin, *On the Origin of Species* (1859), Introduction and Chapters I–V

Slice `intro-ch05` of project `darwin-origin`. Source text: `darwin-origin/inputs/pg1228.txt`
(Project Gutenberg #1228, 1st edition), lines 313–5289 (Introduction 313–481, I 482–1588,
II 1589–2063, III 2064–2635, IV 2636–4139, V 4140–5289). Claims: the 94 rows of
`darwin-origin/claims.json` with `chapter` in {Introduction, I, II, III, IV, V}.

Everything here was produced by the scripts in `scripts/` (see "Reproducing" below). All counts
were retrieved on 2026-10-31; dates in dataset ids and `retrieved_at` fields are UTC.

## Counts

| What | Count |
|---|---|
| Mentions (`mentions.json`) | 754 |
| … from claim `claim`/`quote` fields | 41 (14 of the 94 claims name an animal) |
| … from the source text (line-sourced) | 713 |
| Distinct animal taxa (`taxa/*.json`) | 114 |
| … required by a claim (`mentioned_in` non-empty) | 23 |
| Dataset records (`datasets/*.json`) | 156 |
| Taxa with ≥ 1 dataset | 114 (all) |
| Taxa with only a GBIF occurrence-count record | 4 (see below) |

Taxa by rank: species 45, family 19, genus 18, order 12, class 6, subspecies 4, suborder 2,
infraclass 2, infraorder 2, phylum 2, subfamily 1, historical order 1 (Edentata).

Taxa by class: Mammalia 46, Aves 30, Insecta 19, Maxillopoda/Thecostraca (cirripedes) 4,
Malacostraca 2, Clitellata 2, and one each of Actinopterygii, Amphibia, Crocodylia, Dipneusti,
Gastropoda, Reptilia; plus Mollusca and Brachiopoda at phylum rank and Serpentes, *Salmo
salar* and *Amblyopsis spelaea* (GBIF lineage gives no class for these).

Most-mentioned taxa: *Columba livia* 143 (all pigeon breeds), Aves 61, Insecta 54,
*Canis lupus familiaris* 45 (all dog breeds), *Equus caballus* 40, *Bos taurus* 29,
*Ovis aries* 21, *Gallus gallus* 19, Apidae 18, *Equus asinus* 15, *Felis catus* 12,
Coleoptera 12.

## Taxa resolved to each authority

| Authority | Taxa resolved | Missing |
|---|---|---|
| Wikidata QID | 114 | — |
| NCBI Taxonomy | 110 | `sessilia` (NCBI uses Balanomorpha), `proteolepas-bivincta` (nomen dubium), `reptilia` (NCBI uses Sauropsida), `edentata` (obsolete) |
| ITIS TSN | 110 | `scarabaeus-sacer`, `ruminantia`, `ibla`, `pyrgoma` (not in ITIS) |
| GBIF backbone usageKey | 108 | `actinopterygii`, `ruminantia`, `tetraoninae`, `phthiraptera`, `reptilia`, `cirripedia` (no backbone node; see `resolution_notes`) |
| WoRMS AphiaID | 32 | only marine / marine-containing taxa were queried |

105 taxa have all three of GBIF, NCBI and Wikidata. Where GBIF has only a synonym or doubtful
usage (Edentata → Pilosa; *Proteolepas bivincta* DOUBTFUL) the usage key is kept and the status
is recorded in `resolution_notes`.

Breeds and domestic forms resolve to the species: all pigeon breeds → *Columba livia*; all dog
breeds → *Canis lupus familiaris*; cattle breeds → *Bos taurus* (humped Indian cattle →
*Bos taurus indicus*); sheep breeds → *Ovis aries*; poultry/fowl breeds → *Gallus gallus*;
horse breeds (race-horse, dray-horse, cart-horse, cob) → *Equus caballus*. The breed names are
kept in `names_as_written` and, where useful, `notes`.

## Datasets built (156 records)

Per-taxon records:

- **108 × GBIF occurrence counts** (`gbif-occurrences-<slug>-2026-10-31`): two API calls per taxon
  (`occurrence/search?taxonKey=K&limit=0` and the same with
  `hasCoordinate=true&hasGeospatialIssue=false`), with exact URL, `sha256`, `byte_size`,
  `retrieved_at`, and counts `n_occurrences` / `n_occurrences_georeferenced`. Total across the
  108 taxa (overlapping because of nesting): 3.54 × 10⁹ records.
- **41 × NCBI reference genomes** (`ncbi-genome-<accession>`): one per species/subspecies taxon
  with a RefSeq/GenBank reference assembly (NCBI Datasets v2 `dataset_report`,
  `filters.reference_only=true`). A record is built only when the assembly's organism tax id is
  the taxon itself (or a subspecies of it when the species has no assembly of its own); the
  dog's genome is therefore linked to `canis-familiaris`, not to `canis-lupus`.

Shared databases, one record per slice (`taxa` lists everything they cover; `n_rows_for_taxa`
is the number of distinct rows matching any listed taxon, and `n_rows_for_species_rank_taxa`
restricts that to our species/subspecies taxa so that higher taxa do not inflate it):

| Record | Taxa covered | File checked (not committed) | Rows for species-rank taxa |
|---|---|---|---|
| `anage-build-15` | 88 | `dataset.zip` → `anage_data.txt` (169,150 B) | 42 |
| `amniote-life-history-db-2015-08` | 75 | `Amniote_Database_Aug_2015.csv` (4,728,122 B) | 38 |
| `eltontraits-1-0-2014` | 68 | `BirdFuncDat.txt` (2,199,507 B), `MamFuncDat.txt` (579,107 B) | 38 |
| `pantheria-1-0-wr05-2008` | 42 | `PanTHERIA_1-0_WR05_Aug2008.txt` (2,359,096 B) | 19 |
| `avonet-figshare-16586228-v7` | 30 | `AVONET_Supplementary_dataset_1.xlsx` (21,524,673 B; figshare md5 verified) | 19 |
| `pbdb-taxon-occurrence-counts-2026-10-31` | 97 | PBDB `taxa/single.json?show=size` per taxon | — (97 rows, 1,289,481 fossil occurrences) |
| `worms-aphia-records-2026-10-31` | 32 | WoRMS `AphiaRecordByAphiaID` per marine taxon | — (32 rows, 30 accepted) |

Every download was hashed (`sha256`, `byte_size` in `distributions`); the files live only in
`/tmp` and none is committed (all but the AnAge zip and MamFuncDat exceed 1 MB). Higher taxa
are matched to trait tables by family/genus columns and, for ranks the tables lack (suborder,
infraorder, infraclass, subfamily), via NCBI Taxonomy subtree membership (`esearch`
`txid…[Subtree] AND family[Rank]`).

Identifiers and DOIs: every `identifier` and `doi` was checked with an HTTP request
(`integrity.identifier_resolves`) and every DOI against the Handle API
(`integrity.doi_registered`). Three records (PanTHERIA, EltonTraits, Amniote DB) are ESA
archive DOIs served by Wiley, whose landing pages return HTTP 403 to non-browser clients;
they are recorded as `identifier_resolves: "blocked"` with `doi_registered: true` and
`checksum_verified: true` for the downloaded data files.

## Taxa with no usable trait/reference dataset

All 114 taxa have at least the GBIF occurrence count. Four have nothing else:

| Taxon | Why |
|---|---|
| `scarabaeus-sacer` (*Scarabaeus sacer*) | Insect: not in AnAge/PanTHERIA/AVONET/Amniote/Elton; no NCBI reference genome; PBDB has no entry for the species. |
| `onitis` (*Onitis*, genus) | Dung-beetle genus; no PBDB entry; the trait databases are vertebrate-only. |
| `coccus` (*Coccus*, scale insects) | Same; PBDB has no *Coccus* taxon record. |
| `lumbricidae` (earthworms) | Soft-bodied; no PBDB record; no vertebrate trait data. |

Species/subspecies without an NCBI reference genome (they still have trait datasets):
`canis-lupus` (the only reference assembly under *C. lupus* is the dog's, tax id 9615),
`equus-hemionus`, `equus-quagga-quagga`, `lagopus-lagopus`, `proteus-anguinus`,
`rupicola-rupicola`, `scarabaeus-sacer`, `proteolepas-bivincta` (not in NCBI Taxonomy).

## Non-animal taxa seen (not recorded; for a later plant/fungus pass)

Plants: mistletoe (*Viscum*), *Rubus*, *Rosa*/roses, *Hieracium*, *Primula* (primrose, cowslip,
oxlip), heartsease (*Viola tricolor*), red clover (*Trifolium pratense*), white clover,
*Lobelia* (*L. fulgens*), *Dipsacus* (teasel), *Ruta*, *Antirrhinum*, Scotch fir (*Pinus
sylvestris*), heath/heather (*Calluna*/*Erica*), holly (*Ilex*), oak (*Quercus*), birch
(*Betula*), laurel, orchids (Orchideae), Umbelliferae, Compositae (daisy, dandelion),
Leguminosae/papilionaceous plants, grasses, gooseberry, plum, apple (Codlin), pear, strawberry,
cabbage, turnip, radish, onion, artichoke, kidney-bean, pea, potato, wheat, rape-seed, cotton,
chestnut, dahlia, hyacinth, pelargonium. No fungi or microbes are named in these chapters
("mould" occurs only in the sense of a casting mould).

## Ambiguities and interpretive decisions

- **Generic groups resolved above species.** "birds" → Aves, "insects" → Insecta,
  "quadrupeds" → Mammalia, "beetles" → Coleoptera, "Ganoid fishes" (Ch. IV) →
  Actinopterygii (a paraphyletic grade; the smallest containing clade is used), "snakes" →
  Serpentes, "shells" (where they mean molluscs) → Mollusca, "cockroach" → Blattodea, "bees" → Apidae (Darwin's
  "humble-bee" → *Bombus*, "hive-bee" → *Apis mellifera*), "grouse" → Tetraoninae,
  "gallinaceous birds" → Galliformes, "carnivorous birds"/"birds of prey" → Accipitridae,
  "field-mice" (Ch. III) → *Apodemus* (the British field-mouse), other "mice" → *Mus musculus*.
- **Zebra** (the striped horse-ass hybrids of Ch. V) → *Equus zebra*; Darwin does not specify
  the species. "Quagga" → *Equus quagga quagga*. The "hemionus" is *Equus hemionus*; the "ass"
  is *Equus asinus*; "horse-genus"/"equine species"/"mules" are recorded at genus *Equus*.
- **Dog, wolf, wild canids.** Dog breeds → *Canis lupus familiaris*; the Catskill wolves and
  the Ch. IV wolf → *Canis lupus*; "wild canine animals" and the dog of the fox-like comparison
  (line 4440) → genus *Canis*.
- **Onites apelles** (Ch. V, tarsus-less dung beetle) is read as the scarabaeine genus *Onitis*
  Fabricius, 1798 (an older spelling); the epithet is in no modern database, so the genus is
  used. This is an interpretation.
- **The Paraguay fly** that lays its eggs in the navels of newborn cattle (Ch. III) is recorded
  only at order Diptera; it is usually identified as a screw-worm fly (*Cochliomyia*), but
  Darwin does not name it.
- **"Parasite"** in the Ch. III lines about parasites on grouse/cattle (lines 2094, 2574) is
  taken as the lice (Phthiraptera) Darwin discusses elsewhere; other "parasitic" references
  (parasitic worms, parasitic cirripedes as a group) are not recorded as taxa.
- **Edentata** is Darwin's obsolete order (Xenarthra + Pholidota); kept as a historical-rank
  taxon with GBIF's synonym usage; "armadilloes" → Cingulata, "scaly ant-eaters" → Manidae.
- ***Proteolepas bivincta*** (Darwin 1854) is a nomen dubium, now thought to be an epicaridean
  isopod larva; GBIF marks it DOUBTFUL and WoRMS unaccepted. Kept as the name Darwin used.
- **Elephants and rhinoceroses** are recorded at family rank (Elephantidae, Rhinocerotidae);
  Darwin never names species.
- **Poultry/fowls** → *Gallus gallus*; "ducks" → *Anas platyrhynchos* (domestic duck);
  "cattle"/"oxen" → *Bos taurus*; "Indian cattle" → *Bos taurus indicus*.
- **Not recorded**: generic words with no taxon ("animals", "predators", "organic beings",
  "game", "prey", "vermin"), personal/ship names, and occurrences in chapter headings or the
  table of contents (only lines 313–5289 were swept). Each mention pattern is line- or
  claim-restricted where a word is polysemous (e.g. "camel-hair pencil", "fly" as a verb,
  "horse-genus", "shell" in non-mollusc senses); the filters are in `scripts/taxa_seed.py`.
- **PBDB** has no subspecies taxa; subspecies were queried at species rank and the match is
  noted in the record.

## Reproducing

```
cd organisms/darwin-origin/intro-ch05/scripts
python3 extract_mentions.py          # -> ../mentions.json
python3 resolve_taxa.py [slug ...]   # -> ../taxa/*.json (resets datasets; run `link` after)
python3 fetch_datasets.py gbif anage pantheria avonet elton amniote ncbi worms pbdb link
```

API responses are cached under `/tmp/org/cache` and downloads under `/tmp/org/data`; no data
files are committed. Requires Python 3.12 with `requests`, `pandas`, `openpyxl`.
