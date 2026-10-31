# darwin-origin / ch13-14: Chapters XIII–XIV (Mutual Affinities, Morphology, Embryology, Rudimentary Organs; Recapitulation)

Text: `darwin-origin/inputs/pg1228.txt` lines 12301–14617. Claims: `darwin1859-ch13-01` … `darwin1859-ch13-25`,
`darwin1859-ch14-01` … `darwin1859-ch14-14` (39 claims). Built 2026-10-31 by a cloud agent
(`vendored_by.run` = `cursor/organisms-darwin-ch13-14-4b24`). Validator: `node organisms/validate.mjs darwin-origin/ch13-14`
→ 232 mentions, 76 taxa, 90 datasets, 0 errors, 67 warnings (explained below).

## Counts

| what | n |
|---|---|
| mentions (`mentions.json`) | 232 (220 sourced to text lines, 12 sourced to claim ids) |
| distinct animal taxa (`taxa/`) | 76 |
| resolved to GBIF backbone `usageKey` | 65 |
| resolved to NCBI Taxonomy id | 71 |
| resolved to Wikidata QID (verified via P225 taxon name) | 76 |
| resolved to WoRMS AphiaID (marine taxa only) | 14 |
| ITIS | 0 (not queried) |
| datasets (`datasets/`) | 90 = 65 GBIF occurrence counts + 19 NCBI reference genomes + 6 shared databases |

Shared-database coverage (one record each for the slice): AnAge build 15 (53 taxa), PanTHERIA 1.0 (30),
Amniote Life-History Database 2015 (43), EltonTraits 1.0 (38), Paleobiology Database taxon records (70),
Open Tree of Life taxonomy TNRS (75). Each shared record carries a `taxon_coverage` map (slug → matching rows or
occurrences) in addition to the convention's `counts`.

Only two claims in this slice name taxa in their statements (`ch13-18` dogs/horses/pigeons/short-faced tumbler;
`ch13-24` whales/ruminants); four more name higher groups (`ch13-12` birds/vertebrates, `ch13-14` mammals,
`ch13-15` crustaceans/vertebrates, `ch13-25` island birds, `ch14-10` man). Most of Darwin's organisms in these chapters
are illustrative examples in the running text, so most mentions are line-sourced.

## How identifiers were obtained

- GBIF: `https://api.gbif.org/v1/species/match?name=<name>&kingdom=Animalia[&rank=<rank>]&verbose=true`. A match was
  accepted only if `canonicalName` equals the queried name and `kingdom` is Animalia; where the default match fell back
  to a higher rank or a homonym, the matching entry was taken from `alternatives` (e.g. *Mus* 9800657). Names GBIF does
  not carry as matchable ranks (Ruminantia, Cirripedia, Crustacea, Vertebrata, Papilionoidea, Apoidea) were also
  checked with `species?name=…&datasetKey=<backbone>` and left null.
- NCBI: `esearch.fcgi?db=taxonomy&term=<name>[Scientific Name]` followed by `esummary` to check the rank and division
  (this is how the red alga *Vertebrata* 1261581 and the crinoid Articulata 35070 were rejected).
- Wikidata: `wbsearchentities` then `wbgetentities` (P225, P31, P105) to pick the entity whose taxon name equals the
  query; where two entities share the name (Vertebrata, Homoptera, Elephantidae, Aphis, Canis familiaris) the one at the
  correct rank is recorded and the alternative noted in the taxon file.
- WoRMS: `AphiaIDByName/<name>?marine_only=false` for the 14 marine/aquatic taxa.
- Every taxon file keeps the exact query URLs and retrieval time under `resolution`.

## Taxa with no or reduced datasets, and why

- `pachydermata` (Cuvier's obsolete order; "Pachyderms", "pachydermatous animal"): Wikidata Q1921355 only. Not in GBIF,
  NCBI, PBDB or Open Tree, so **no dataset** (validator warning "no dataset").
- `fish` ("fish", "fishes"; recorded as the informal group Pisces, Wikidata Q152, WoRMS 11676): no GBIF key, so no
  occurrence count; only the Open Tree record covers it.
- `homoptera` (obsolete suborder, Wikidata Q921647): Open Tree only.
- `reptilia`: GBIF treats Reptilia as a pro parte synonym split over four orders and NCBI has no Reptilia node, so no
  GBIF count or genome; covered by AnAge, Amniote DB, PBDB and Open Tree.
- `ruminantia`, `cirripedia`, `crustacea`, `vertebrata`, `papilionoidea`, `apoidea`, `xenarthra`: no GBIF key (not a
  matchable backbone rank, or, for Xenarthra, GBIF's entry is a synonym of Cingulata only), so no occurrence count; they
  are covered by PBDB/Open Tree and, where applicable, the trait databases.
- `lagostomus-maximus` (bizcacha): NCBI Datasets has no reference genome (`reports` empty); GBIF count and trait rows
  recorded instead.
- Genome records for genus-level taxa are for a member species and say so in `role`: *Lepidosiren paradoxa*
  (monotypic), *Vombatus ursinus* (Darwin's "phascolomys"), *Trichechus inunguis* (Darwin's "manatee", species
  unspecified). The giraffe reference assembly GCA_017591445.1 is labelled *Giraffa camelopardalis rothschildi*.
- Reference genomes were only sought for species/subspecies-level taxa and monotypic or small genera; class/order/family
  taxa have none (a "reference genome of Mammalia" would be arbitrary).

## Non-animal taxa seen (not built)

Plants: Proteaceæ, Connaraceæ (*Cnestis*, *Connarus*), Grasses, Malpighiaceæ (*Aspicarpa*), pine-apple, swedish and common
turnip, cowslip, primrose, Orchideæ (*Monochanthus*, *Myanthus*, *Catasetum*), *Ulex* (furze), phyllodineous acacias,
Leguminosæ, Compositæ, *Antirrhinum* (snapdragon), cauliflower, fir-trees, wild rose, oak-tree, British brambles,
flowering plants / dicotyledons and monocotyledons generally. Algae: "certain Algæ" (mere colour as a character). No
fungi or microbes are named.

## Ambiguities and decisions

- **Articulata** (Cuvier's embranchement: "class of the Articulata", "the articulata", "articulate classes", lines
  12550, 13053, 13082–13089, claim `ch13-15`) could **not be resolved**: GBIF and NCBI have no such taxon (NCBI's
  Articulata 35070 is a crinoid subclass), and Wikidata has items only for the crinoid, brachiopod and bryozoan
  homonyms and for the modern "Articulata hypothesis" (Q1526314), none of which is Cuvier's group. No taxon file was
  built and its mentions are omitted from `mentions.json`; the claim-level mention of "articulates" in `ch13-15` is
  therefore not represented.
- "extinct gigantic sea-lizards" (line 13043, paddles): Darwin does not name a group; ichthyosaurs and/or plesiosaurs
  are meant. Not resolved; noted here only.
- "animals inhabiting dark caverns", "blind animals inhabiting the dark caves of America and Europe" (13579, 14107–14108)
  and "various fancy animals" (13252): not taxa; omitted.
- "the thrush" that dives and feeds on sub-aquatic insects (14069) is the dipper (*Cinclus*) in Darwin's sense, but he
  writes "thrush"; recorded under `turdidae` as written, with the South American mud-nesting thrush under `turdus`.
- "a petrel … fitting it for the life of an auk or grebe" (14070) is the diving petrel (*Pelecanoides*); recorded at the
  order written ("petrel" → Procellariiformes).
- "worms crawling through the damp earth" (14595) read as earthworms → Lumbricidae.
- "bee or bug" in the mouthparts passage (13001) is a generic bee → Apoidea; the hive-bee, drones and queen bee of
  Chapter XIV → *Apis mellifera*.
- "dog-genus" → *Canis*; "dog", "Dogs", "greyhound", "bulldog" → *Canis lupus familiaris* (GBIF's accepted usage for
  *Canis familiaris*; NCBI 9615). "genus Bos" → *Bos*; cattle/calves/cows/ox → *Bos taurus*. "horse-genus" → *Equus*;
  horse/racehorse/cart-horse → *Equus caballus*.
- "Ornithorhynchus", "Lepidosiren" are monotypic genera; the platypus is recorded at species level, *Lepidosiren* at
  genus as written.
- "pedunculated and sessile" cirripedes (13179–13180) correspond to the former orders Pedunculata and Sessilia; kept
  under `cirripedia`.
- "mankind", "races of man", "Hottentot", "Negro", "our own children", "man" → *Homo sapiens*.
- GBIF backbone rank labels differ from current usage for several accepted names and are noted in the taxon files:
  Marsupialia 9712517, Brachyura 11132538 and Serpentes 11205692 are labelled FAMILY in the backbone; Cetacea 733 is an
  ORDER in GBIF but an infraorder in NCBI. The `rank` field records the conventional rank.
- Shared-database `n_rows_for_taxa` sums rows per listed taxon without deduplicating nested taxa (e.g. the Mammalia
  rows of AnAge are counted again under Carnivora, Felidae, *Panthera leo*); the per-taxon `taxon_coverage` map is the
  precise figure.

## Validator warnings (67, all acceptable)

- 66 × `mentioned_in is empty`: these taxa are mentioned only in the running text (line-sourced mentions), not in any
  claim statement. `mentioned_in` is reserved for claim ids per the README; the text mentions are in `mentions.json`.
- 1 × `taxa/pachydermata.json: no dataset` (see above).

## Not done / could not be done

- BOLD Systems API returned HTTP 403 from this environment; no BOLD record.
- IUCN Red List API requires a token; no IUCN record.
- AVONET (xlsx on Figshare), TimeTree, MorphoSource, FishBase, Phenome10K: not vendored in this pass. The Open Tree
  TNRS record supplies phylogeny identifiers (OTT ids) instead of TimeTree.
- No raw API response bodies or database files are committed (AnAge zip 169 150 B, PanTHERIA 2.36 MB, Amniote DB
  4.73 MB, EltonTraits 2.20 MB + 0.58 MB exceed or approach the 1 MB limit); their `byte_size` and `sha256` are recorded
  in the dataset records.
