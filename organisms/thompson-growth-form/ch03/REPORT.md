# thompson-growth-form / ch03 — Chapter III, The Rate of Growth

Source: `thompson-growth-form/inputs/pg55264.txt`, lines 2580–5906 (Project Gutenberg #55264,
D'Arcy Thompson, *On Growth and Form*, 1917). Claims: `thompson1917-ch03-01` … `-35` (35 claims).
Vendored 2026-10-31 by a cloud agent (`claude-fable-5.1`, branch `cursor/organisms-thompson-ch03-9300`).
Footnotes for this chapter sit outside the line range and were not mined.

## Counts

| | |
|---|---|
| mentions (`mentions.json`) | 119 (29 cite a claim id, 90 cite file lines) |
| claims with at least one animal mention | 19 of 35 |
| distinct animal taxa (`taxa/`) | 56 (24 species, 13 genera, 5 families, 1 infraorder, 1 superfamily, 2 orders, 1 infraclass, 4 classes, 1 subphylum, 2 phyla, 2 informal groups) |
| taxa with a GBIF backbone `usageKey` | 51 |
| taxa with an NCBI Taxonomy id | 52 |
| taxa with a Wikidata QID (verified via P225) | 55 |
| taxa with a WoRMS AphiaID (marine taxa only) | 18 |
| taxa with an Open Tree of Life OTT id | 54 (all except Pisces and Ungulata) |
| taxa with ITIS TSN | 0 (ITIS was not queried) |
| dataset records (`datasets/`) | 86 |
| – GBIF occurrence-count records | 51 (one per taxon with a GBIF key) |
| – NCBI reference-genome records | 22 (every species with a RefSeq/GenBank reference assembly) |
| – FishBase growth-parameter records | 4 (plaice, haddock, brown trout, smooth dogfish) |
| – shared databases (one record each) | 9: GBIF backbone matches, AnAge build 15, PanTHERIA 1.0, Amniote Life-History DB (Aug 2015), EltonTraits 1.0, AVONET (figshare v7), Open Tree TNRS (OTT 3.7), Paleobiology DB counts, MorphoSource counts |

Validator: `node organisms/validate.mjs thompson-growth-form/ch03` → 0 errors, 41 warnings
(40 × "mentioned_in is empty" for taxa that occur only in the running text and not in any claim —
`mentioned_in` holds claim ids per the README, the text mentions are in `mentions.json`; 1 ×
"no dataset" for the informal group `fishes`, see below).

## How taxa were resolved

Live queries on 2026-10-31 (every response body saved and hashed; the exact URLs, `retrieved_at`,
`byte_size` and `sha256` are in the dataset records):

- GBIF `GET /v1/species/match?name=…&verbose=true&kingdom=Animalia` (+ `rank=GENUS` for genera).
  Where the match API returned a homonym or fell back to kingdom level, the backbone usage was
  fetched explicitly with `GET /v1/species/{key}` and this is noted on the taxon: Anura (952),
  *Anguilla* Schrank 1798 (2403092, not the nematode/plant homonyms), *Fundulus* Lacepède 1803
  (2347676), *Homarus* Weber 1795 (5972002, not the weevil genus *Homarus* T.Broun 1881), and
  *Prionailurus bengalensis* (2434903; see "Felis minuta" below).
- NCBI `esearch.fcgi?db=taxonomy&term=<name>[Scientific Name]`; when more than one id came back
  (*Rana*: genus 8399 vs subgenus 121175) `esummary` was used to pick the right rank.
- Wikidata: `list=search&srsearch=haswbstatement:"P225=<name>"` then `wbgetentities` to verify
  that P225 equals the name and P31 is a taxon class; `wbsearchentities` as a fallback. The first
  pass hit HTTP 429 rate limits; all 429 responses were discarded and re-fetched.
- WoRMS `AphiaIDByName/<name>?marine_only=false`; where it returned −999 (several matches:
  *Sphaerechinus*, *Tubularia*) `AphiaRecordsByName` was used and the accepted Animalia genus taken.
- Open Tree of Life `POST /v3/tnrs/match_names` (context Animals, exact matching) for all names at once.

## Taxa that are not simple species

| slug | as written | resolution |
|---|---|---|
| `fishes` | "fishes", "fish" | informal paraphyletic group; only Wikidata Q152 (P225 "Pisces"). GBIF, NCBI and Open Tree have no such taxon. **No dataset** (nothing sensible to attach at this level; the chapter's actual fishes are separate taxa). |
| `ungulata` | "Ungulate animals" | informal; only Wikidata Q1231177 (P225 "Ungulata", instance of taxon). Not in GBIF/NCBI/Open Tree. Has a PBDB count (PBDB keeps Ungulata as a taxon). |
| `reptilia` | "the great secondary reptiles" | Wikidata Q10811 only. GBIF backbone splits Reptilia into several class usages (12170550–2) and key 358 is a pro-parte synonym pointing at Crocodylia, so no GBIF key was recorded; NCBI has no Reptilia node (Sauropsida instead). |
| `crustacea` | "Crustacea", "any ordinary crustacean" | WoRMS 1066 and Wikidata Q25364. GBIF's only "Crustacea" is a doubtful bee genus; NCBI folds Crustacea into Pancrustacea (197562, a different concept). |
| `papilionoidea` | "certain butterflies" | NCBI 37572, Wikidata Q756153, OTT; GBIF backbone carries no superfamilies. |
| `marsupialia` | "the little marsupial" | GBIF 9712517; NCBI id recorded is 9263 (Metatheria, for which NCBI lists Marsupialia as a synonym). |
| `callitrichidae` | "Marmoset" | GBIF 9620 (family); NCBI ranks the group as subfamily Callitrichinae (9480) within Cebidae — that id is recorded. |
| `prionailurus-bengalensis` | "Felis minuta" | Historical name (Temminck). GBIF match: 2434909 = SYNONYM of 6164515 (*P. bengalensis chinensis*, a subspecies); the species-level accepted usage 2434903 *Prionailurus bengalensis* is recorded, with NCBI 37029 and Wikidata Q42627. |
| `mustelus-canis` | "the dogfish" | Species taken from the cited source: Kellicott (1908) *The growth of the brain and viscera in the smooth dogfish (Mustelus canis, Mitchill)*, Am. J. Anat. 8:319–354, doi:10.1002/aja.1000080112. |
| `forficula-auricularia` | "earwigs" | Species taken from the cited source: Bateson & Brindley (1892) Proc. Zool. Soc. 585–596, which measured forceps of male *Forficula auricularia*. |
| `salmo-trutta` | "Trout (Salmo fario)" | *Salmo fario* L. is a synonym of *S. trutta*. |
| `felis-catus` | "F. domestica", "the kitten" | domestic cat. |
| `canis-familiaris` | "dog", "the puppy" | GBIF *Canis familiaris* 5219200; NCBI uses *Canis lupus familiaris* 9615 (recorded), Open Tree likewise. |
| `globicephala` | "Whale (Globiocephalus)" | old spelling of *Globicephala*; GBIF 2440595, NCBI 9729, WoRMS 137017. **No Wikidata item carries P225 "Globicephala"** (checked by haswbstatement search and SPARQL); the "pilot whale" item Q459616 carries P225 "Globicephala melas". Left null. |
| `anguilla`, `rana`, `anura`, `bufonidae`, `homarus`, `brachyura`, `alpheus`, `ateles`, `elephantidae`, `phocoenidae`, `chiroptera`, `fundulus`, `cerianthus`, `tubularia`, `sphaerechinus`, `echinus`, `echinoidea`, `echinodermata`, `branchiopoda`, `branchipus`, `artemia`, `felidae`, `mammalia`, `arthropoda` | various | Thompson gives only a vernacular or genus/group name, so these are resolved above species level. Tadpole experiments whose species he does not name (Schaper, Durbin, Ellis, Frazee, Gudernatsch) are filed under `anura`; explicit "Rana"/Hertwig-and-Peter frog data under `rana`. |
| `artemia` (names "A. milhausenii", "A. köppeniana", "Artemia (Callaonella) Jelskii", "Callaonella") | | these historical names for salinity forms do not resolve in GBIF/NCBI/Wikidata as accepted taxa (GBIF matches *Artemia milhausenii* only to the genus), so they are kept as `names_as_written` on the genus record. |

## Datasets: what was actually downloaded and inspected

All files were fetched to `/tmp` only; nothing larger than the JSON records is committed.

| dataset | file inspected | size | coverage in this slice |
|---|---|---|---|
| AnAge build 15 | `dataset.zip` → `anage_data.txt` (4,645 rows; release notes say 4,671 entries) | 169,150 B | 21 species, one row each; genus rows for *Rana* (7), *Anguilla* (9), *Ateles* (6), *Globicephala* (2), *Fundulus* (4), *Homarus* (1). Growth rate (1/days) present for 10 of the 21 species. |
| PanTHERIA 1.0 (WR05, Aug 2008) | `PanTHERIA_1-0_WR05_Aug2008.txt` from esapubs.org (5,416 rows) | 2,359,096 B | 12 mammal species; *Ateles* 7 rows, *Globicephala* 2 |
| Amniote life-history DB | `ECOL_96_269.zip` → `Amniote_Database_Aug_2015.csv` (21,322 rows) | 6,539,535 B | 16 bird+mammal species; *Ateles* 7, *Globicephala* 2 |
| EltonTraits 1.0 | `MamFuncDat.txt` (5,403), `BirdFuncDat.txt` (10,205) | 579,107 B + 2,199,507 B | 12 mammals + 4 birds; *Ateles* 7, *Globicephala* 2 |
| AVONET v7 | `AVONET Supplementary dataset 1.xlsx` (unzipped; `sharedStrings.xml` and `sheet2.xml` grepped; 11,009 rows in AVONET1_BirdLife) | 21,524,673 B | 4 birds (Gallus gallus, Columba livia, Carduelis carduelis, Pyrrhula pyrrhula) |
| FishBase | species summary + `PopGrowthList.php` HTML for each of 4 fishes | 25–70 kB each | growth studies parsed from the table: plaice 14, haddock 43, brown trout 55, smooth dogfish 8 |
| NCBI Datasets | `genome/taxon/{taxid}/dataset_report?filters.reference_only=true` | 5–7 kB each | 22 reference assemblies (accession, assembly name, submitter, release date, length, N50 recorded). No reference assembly exists for *Artemia salina* or *Mustelus canis* (empty report). |
| GBIF | `occurrence/count?taxonKey=…` | 6–11 B each | 51 taxa |
| Open Tree TNRS | one POST response | | 54 of 55 names sent matched (Ungulata unmatched; Pisces not sent) |
| Paleobiology DB | `occs/list.json?base_name=…&limit=1&rowcount` | ~300 B each | 46 taxa with ≥1 fossil occurrence |
| MorphoSource | `api/media?q=…&per_page=1` | ~5 kB each | 28 taxa with ≥1 media record |

### Databases checked but not usable from this environment

- **BOLD** (`v4.boldsystems.org`, `boldsystems.org`, `portal.boldsystems.org`): HTTP 403/400 for every endpoint tried. No BOLD record built.
- **IUCN Red List API v4**: requires an API token (403 without). No IUCN record built; FishBase pages quote the IUCN status for the four fishes but that was not vendored separately.
- **TimeTree**: no public API (`/api/pairwise/...` returns 400); not recorded.
- **FishBase ropensci API** (`fishbase.ropensci.org`): unreachable; the FishBase website HTML was used instead.
- **ITIS**: not queried (time); `itis_tsn` is null everywhere.

## Taxa with no usable dataset and why

- `fishes` (informal "Pisces"): no identifier in GBIF/NCBI/OTT, so no occurrence count, genome or
  trait rows can be attached. Covered indirectly by the specific fish taxa.
- `ungulata`, `reptilia`, `crustacea`, `papilionoidea` have no GBIF key and therefore no GBIF
  occurrence-count record; they are covered by the Open Tree, PBDB and (where ≥1 hit) MorphoSource
  shared records only.
- Every other taxon has at least a GBIF occurrence count plus the backbone-match record.

## Non-animal taxa seen (not built)

Plants: Protococcus (green alga), bamboo, Spirogyra (alga), Crocus, bean (*Phaseolus*/*Vicia*
root), *Equisetum*, *Ceratophyllum*, "water-weeds", maize, *Lupinus albus*, pea, melon, *Pinus*,
*Eucalyptus*, *Acacia*, *Quercus*, *Populus*, *Robinia*, *Melia*, "yellow pine" (Arizona, Douglass
tree rings), elm, cherry, "Alpine plants".
Protists: *Orbulina* (foraminifer), *Chilomonas paramoecium* (cryptomonad flagellate), Infusoria,
*Stentor* (ciliate).
Fungi/microbes: yeast (Roux's dough blastoderm), bacteria (Bottomley's auximones; Blackman's
doubling bacterium).

## Ambiguities and judgement calls

- **"fishes", "birds", "animals", "invertebrates", "cold-blooded vertebrates", "warm-blooded
  animals", "worms and worm-like animals" (claim 33), "Hydra" (Trembley is named, the animal is
  not)**: generic group words. Only "fishes" (claims 10 and 23) and "Ungulate animals" were given
  records; the others were judged too generic to resolve and are not in `mentions.json`.
  Claim 33 (fission in worms) therefore has no taxon record.
- **Darwin quotation** (lines 2836–2870): bat, porpoise and pigeons occur inside Thompson's
  quotation of the *Origin*; they are recorded as mentions because the names appear in this text,
  with a note on the taxon record.
- **Tadpoles**: filed under `anura` unless the passage names *Rana*; Hertwig's Fig. 28 "Frog" is
  filed under `rana` because Peter's table attributes the same data to *Rana*.
- **Eel**: Johannes Schmidt's Leptocephalus series is the European eel, but Thompson writes only
  "eel", so the genus *Anguilla* is recorded.
- **Lobster**: "the common lobster" in Britain is *Homarus gammarus*, but Przibram's and Morgan's
  regeneration experiments used *H. americanus*; genus recorded.
- **PBDB "Echinus"** returned exactly the Echinoidea total (11,662), so it was dropped from the PBDB
  record as a probable rank mis-resolution. PBDB counts for Ungulata, Reptilia, Mammalia,
  Arthropoda follow PBDB's own classification.
- **MorphoSource** counts come from a free-text `q=` search; for short genus names (Rana, Homarus)
  they may include unrelated hits. Taxa with zero hits are simply omitted from that record.
- **AVONET** was inspected by unzipping the xlsx and grepping the shared-strings and sheet XML, not
  by a spreadsheet parser; the row count is the number of `<row>` elements minus the header.
- **FishBase** has no version string on its pages (the "Version 2025-2" there is the IUCN list
  version), so `version` is "as served 2026-10-31".
- **Line numbers** in `mentions.json` were verified by the build script: every quote was located
  in the source file and `line_start`/`line_end` snapped to the exact lines containing it; quotes
  attached to a claim id were verified to occur verbatim within lines 2580–5906.
