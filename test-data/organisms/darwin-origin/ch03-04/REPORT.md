# darwin-origin / ch03-04 — Chapters III (Struggle for Existence) and IV (Natural Selection)

Text: `claim-sources/darwin-origin/inputs/pg1228.txt` lines 2064–4139. Claims: `darwin1859-ch03-01` … `ch03-14`,
`darwin1859-ch04-01` … `ch04-26` (40 claims). Built 2026-10-31 by a cloud agent
(`vendored_by.run = cursor/organisms-darwin-ch03-04-30cb`); every identifier, count and checksum below was
retrieved live from the named API or file on that date. Response bodies were saved outside the repo and
their `byte_size`/`sha256` recorded in the dataset records; nothing over 1 MB is committed (largest file
here is ~70 kB).

## Counts

| what | n |
|---|---|
| mentions (`mentions.json`) | 172 (163 located in the text by file + line range, 9 in claim quotes) |
| distinct taxa (`taxa/`) | 69 — 34 species, 1 subspecies, 7 genera, 1 subfamily, 13 families, 1 suborder, 4 orders, 2 infraclasses, 4 classes, 1 subphylum, 1 clade |
| resolved to GBIF backbone `usageKey` | 64 / 69 |
| resolved to NCBI Taxonomy id | 68 / 69 |
| resolved to Wikidata QID (verified via P225 taxon name) | 69 / 69 |
| ITIS TSN (from Wikidata P815) | 67; WoRMS AphiaID (P850 or WoRMS): 40; IUCN taxon id: 26 |
| datasets (`datasets/`) | 102 — 64 GBIF occurrence counts, 32 NCBI reference genome assemblies, 6 shared databases |
| taxa with ≥ 1 dataset | 68 / 69 |
| claims with an animal mention in their quote | 4: `darwin1859-ch03-10`, `ch04-04`, `ch04-07`, `ch04-09` |

Validator: `node test-data/organisms/validate.mjs darwin-origin/ch03-04` → 0 errors, 61 warnings (see below).

## How taxa were resolved

- GBIF: `https://api.gbif.org/v1/species/match?name=<name>&kingdom=Animalia&verbose=true` (plus `rank`/`family`/`class`
  hints for homonym-prone names such as *Mus*, *Apodemus*, *Alligator*). Only `EXACT` matches at the intended rank
  were accepted; the matched `usageKey` is recorded, and where GBIF treats the name as a synonym the accepted key is
  used for the occurrence count (only *Canis familiaris* → *Canis lupus familiaris* 6164210).
- NCBI: `esearch.fcgi?db=taxonomy&term="<name>"[Scientific Name]` followed by `esummary.fcgi` to confirm the
  scientific name, rank and division (this rejected the red-alga genus *Vertebrata* 1261581 in favour of the
  vertebrate clade 7742, and the plant/insect homonyms of *Mus*, *Bombus*, *Anthophila*).
- Wikidata: `wbsearchentities` then `wbgetentities` with `props=claims`; an entity was accepted only if its P225
  (taxon name) equals the queried name, and homonyms were disambiguated by matching P685 (NCBI id) or P846 (GBIF id)
  against the ids resolved above. ITIS/WoRMS/IUCN ids are read from P815/P850/P627 of the accepted entity.
- Lineage (phylum/class/order/family) is taken from the GBIF match; for the five GBIF-null taxa it is filled by hand
  and said so in `notes`.

## Taxa not resolved by every authority

| taxon | missing | why |
|---|---|---|
| `tetraoninae` (generic "grouse") | GBIF | GBIF backbone has no accepted Tetraoninae; its fuzzy hit "Tetraonidae" is a synonym of Phasianidae. NCBI 466585, Wikidata Q201240, ITIS 553485. |
| `anthophila` (generic "bees") | GBIF | GBIF's only *Anthophila* is a choreutid moth genus. NCBI 3042114 (clade), Wikidata Q7391. Also the one taxon with **no dataset**: PBDB/trait databases do not index the clade name and there is no GBIF key to count against. The bee mentions that *are* specific (hive-bee, humble-bees) have full records under `apis-mellifera` and `bombus`. |
| `vertebrata` | GBIF | GBIF backbone has no subphylum node. NCBI 7742, Wikidata Q25241, ITIS 331030, WoRMS 146419. |
| `cirripedia` | GBIF | No Cirripedia node in GBIF backbone. NCBI 6675, Wikidata Q220457, WoRMS 1082. |
| `ruminantia` | GBIF | No Ruminantia node in GBIF backbone. NCBI 9845, Wikidata Q192164. |
| `marsupialia` | NCBI | NCBI Taxonomy uses Metatheria and has no "Marsupialia" name. GBIF 9712517 (listed by GBIF with rank FAMILY, which is wrong but is the key GBIF uses), Wikidata Q25336, ITIS 179918. |

Species-level taxa without a reference genome record (3 of 35): `canis-lupus` (NCBI's `reference_only` report for
taxid 9612 returns the dog GCF_011100685.1 and the Mexican wolf GCA_048164855.1, neither at the species taxid, so none
was recorded), `lagopus-lagopus` and `rupicola-rupicola` (no assembly flagged as reference in NCBI Datasets).

## Datasets

Per-taxon records:

- `gbif-occurrences-<slug>-2026-10-31` (64): `https://api.gbif.org/v1/occurrence/count?taxonKey=<key>`; the retrieved
  integer is in `counts[0]` and the GBIF name-match response is the second distribution. Counts include descendant
  taxa, so class-level counts (Aves 2.27 × 10⁹, Insecta 3.4 × 10⁸) are whole-clade totals.
- `ncbi-genome-<accession>` (32): `https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/<taxid>/dataset_report?filters.reference_only=true`
  for species-level taxa; accession, assembly name, submitter, release date, BioProject, sequencing technology,
  total length, N50 and chromosome count are copied from that response. The FASTA download URL is listed with
  `inspected: false`; only the JSON report was downloaded.

Shared records (one per slice, listing every covered taxon; `n_rows_for_taxa` itemises rows per taxon):

| id | file(s) inspected | matched taxa |
|---|---|---|
| `anage-build-15` | `dataset.zip` → `anage_data.txt`, 4,645 rows (release notes say 4,671 entries) | 45 |
| `pantheria-1-0-wr05-2008` | `PanTHERIA_1-0_WR05_Aug2008.txt`, 5,416 rows | 20 |
| `amniote-life-history-database-2015` | `Amniote_Database_Aug_2015.csv`, 21,322 rows | 41 |
| `eltontraits-1-0-2014` | `BirdFuncDat.txt` (9,993) + `MamFuncDat.txt` (5,400) via figshare | 36 |
| `iucn-red-list-via-gbif-2026-10-31` | per-species `https://api.gbif.org/v1/species/<key>/iucnRedListCategory` | 25 |
| `paleobiology-database-occurrences-2026-10-31` | per-taxon `https://paleobiodb.org/data1.2/occs/list.json?base_name=<name>&limit=1&rowcount` | 57 |

Trait-database rows were matched at species (genus + epithet / binomial), genus, or family level only; class- and
order-level taxa (Aves, Insecta, Carnivora …) are deliberately not attached to the trait databases because a
"covers Aves" row count would be the whole table. IUCN: species whose GBIF lookup returned `NOT_EVALUATED`
(homo-sapiens, bos-taurus, equus-caballus, apis-mellifera, felis-catus, ovis-aries, blattella-germanica,
blatta-orientalis, bombyx-mori) have no Red List assessment and were left out of the IUCN record. PBDB taxa with
zero fossil occurrences (Hippobosca, Hirudo medicinalis, Blattella germanica, Blatta orientalis, Bombyx mori, Salmo
salar, Rupicola rupicola, Paradisaeidae, Pavo cristatus, Lumbricidae, and the clade Anthophila which PBDB does not
index) were left out of the PBDB record.

Landing pages: every dataset `identifier` was requested; all 102 resolve. `www.gbif.org` returns HTTP 403 to
non-browser clients, so GBIF species/dataset pages were checked through the API record behind them
(`integrity.identifier_check` says which URL was actually fetched).

Not built, and why: **AVONET** (figshare xlsx, not inspected in this pass), **BOLD** (`v4.boldsystems.org` API
returned HTTP 403), **TimeTree** and **MorphoSource** (no anonymous machine-readable endpoint), **Open Tree of
Life** (TNRS is POST-only, so it cannot be recorded as a `download_url`), **FishBase** (the Salmo salar summary page
loads but FishBase has no stable per-species download; could be added as an `inspected: false` landing page later).

## Non-animal taxa seen (not built)

Plants: missletoe (*Viscum album*) and the apple it grows on; Scotch fir (*Pinus sylvestris*); heath/heather and
"heath-plants"; grasses and carices; *Lobelia fulgens* and another *Lobelia*; orchidaceous plants; heartsease
(*Viola tricolor*); red clover (*Trifolium pratense*) and incarnate clover (*T. incarnatum*), "our clovers";
wheat; sweet-peas; charlock; dandelion; peas and beans; Leguminosae / papilionaceous pea-family; common laurel;
holly-trees; barberry; cabbage, radish, onion; corn and rape-seed; plums and peaches; cotton-trees; the 357 native
weed seedlings and the twenty turf species; trees of New Zealand, the United States and Australia; the Madeira
flora; naturalised plants of Asa Gray's Manual. Fungi/microbes: none named ("epidemics" and "a certain disease" of
plums/peaches are unspecified).

## Ambiguities and judgement calls

- **"ostrich"** (line 2246, `struthio-camelus`): the sentence compares condor and ostrich "in the same country",
  i.e. South America, where Darwin's "ostrich" is normally the rhea (*Rhea americana*). Resolved to the name as
  written; a merger may prefer *Rhea*.
- **"a certain fly" of Paraguay** (line 2444, `diptera`): usually identified as the screwworm *Cochliomyia
  hominivorax*; Darwin does not name it, so it is recorded at order level.
- **"small Asiatic cockroach" / "its great congener"** (lines 2560–2561): resolved to *Blattella germanica* and
  *Blatta orientalis*, the conventional identification; the second is an inference from "congener".
- **"field-mice"** (`apodemus`) vs **"mice"** (`mus`): the field-mouse that raids bumblebee nests may be the wood
  mouse (*Apodemus*) or, in 1850s usage, the field vole (*Microtus agrestis*); the generic "mice" dependent on cats
  are resolved to *Mus*.
- **"grouse"** generic (`tetraoninae`) is kept separate from the three named grouse (red grouse *Lagopus lagopus*,
  ptarmigan *L. muta*, black grouse *Lyrurus tetrix*) which carry claim `darwin1859-ch04-04`.
- **"Ornithorhynchus"** and **"Lepidosiren"** are genus names but both genera are monotypic, so they are resolved to
  the species to attach genome and trait data.
- **Domestic animals** (cattle incl. black cattle / long-horns / short-horns, horses incl. race-horse, dogs incl.
  greyhounds and pointer, pigeons incl. tumblers, carriers and white pigeons, fowls incl. bantams and game-cocks,
  sheep incl. shepherd's flocks) are mapped to their species. The dog is recorded as *Canis lupus familiaris*
  (GBIF-accepted name; NCBI 9615) with "dogs", "greyhounds", "pointer" as names as written.
- **"beasts of prey"**, "carnivorous animals/quadruped" → Carnivora; **"stag"/"deer"** → Cervidae; **"hawks"** →
  Accipitridae; **"swallow"** (US species pair, unnamed) → Hirundinidae; **"locusts"** → Acrididae; **"earth-worms"**
  → Lumbricidae (all British earthworms); **"slugs", "snails", "land-mollusca"** → Gastropoda.
- **Not built**: "Ganoid fishes" (line 3443; archaic grade with no accepted node in GBIF/NCBI — the seven freshwater
  genera Darwin means are not named), "parasitic worms" causing game epidemics, the unnamed "parasite" on quadruped
  hair / bird feathers / the tiger's body, "vermin", "quadrupeds", "game"/"winged game" (all covered by other
  entries or too unspecific), "bark-feeders" (insects, inside the `insecta` claim mention), "Indians in a war-dance"
  (people as simile, not a taxon mention) and "camel-hair pencil" (an artefact).

## Validator warnings (acceptable)

- 60 × `mentioned_in is empty`: those taxa occur only in the running text, not in any claim quote; their locations
  are in `mentions.json` as `file` + `line_start`/`line_end`. Only the 9 taxa quoted in claims `ch03-10`, `ch04-04`,
  `ch04-07`, `ch04-09` have claim ids.
- 1 × `taxa/anthophila.json: no dataset` — explained above.
