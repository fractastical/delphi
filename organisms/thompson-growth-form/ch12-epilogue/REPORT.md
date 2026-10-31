# Organisms: *On Growth and Form* (1917), Chapters XII–XVII and Epilogue

Slice `ch12-epilogue` of project `thompson-growth-form`. Source text
`thompson-growth-form/inputs/pg55264.txt` lines 19561 (heading "CHAPTER XII") to 25432 (last line of
the Epilogue); claims from `thompson-growth-form/claims.json` with `chapter` in XII, XIII, XIV, XV,
XVI, XVII, Epilogue (95 claims). Footnotes for these chapters live in the NOTES block after line
25432 and were not swept.

Everything here was produced by the scripts in `scripts/` (run in order: `scan_mentions.py`,
`resolve_taxa.py`, `build_datasets.py`). Raw downloads were kept outside the repository
(`/tmp/organisms-data`); only their URL, byte size and SHA-256 are recorded. No claim, assessment or
nanopub file was touched; nothing was signed or published.

## Counts

| what | n |
|---|---|
| mentions (`mentions.json`) | 940 |
| &nbsp;&nbsp;from claim `claim`/`quote` fields | 97 (35 of the 95 claims name an animal) |
| &nbsp;&nbsp;from the book text (one per line hit) | 843 |
| distinct animal taxa (`taxa/`) | 220 |
| &nbsp;&nbsp;named in a claim (required) | 73 — all have a taxon file and ≥1 dataset |
| &nbsp;&nbsp;extinct | 39 |
| &nbsp;&nbsp;by rank | species 82, subspecies 2, genus 73, family 34, superfamily 2, order 14, superorder 1, subclass 2, class 9, clade 1 |
| resolved to GBIF backbone `usageKey` | 210 / 220 |
| resolved to NCBI Taxonomy id | 179 / 220 |
| resolved to Wikidata QID | 219 / 220 |
| resolved to WoRMS AphiaID (marine taxa) | 72 |
| resolved to Paleobiology Database taxon_no | 44 (all 39 extinct taxa + 5 extant higher taxa the GBIF backbone lacks) |
| ITIS TSN | not queried (`itis_tsn: null` throughout) |
| dataset records (`datasets/`) | 319 |
| &nbsp;&nbsp;GBIF occurrence counts (one per taxon with a GBIF key) | 210 |
| &nbsp;&nbsp;Paleobiology Database occurrence counts | 44 |
| &nbsp;&nbsp;NCBI Datasets reference genome assemblies (species-rank taxa) | 58 |
| &nbsp;&nbsp;shared trait/reference databases (one record each, listing all taxa they cover) | 7: AnAge build 15 (107 taxa), PanTHERIA 1.0 (57), Amniote Life-History DB 2015 (97), AVONET 2022 v7 (32), FishBase v25.04 (19), WoRMS Aphia records (71), MorphoSource media counts (88) |
| taxa with no dataset at all | 0 |
| taxa with only occurrence counts (GBIF and/or PBDB, no trait/reference/genome dataset) | 26, listed below |

Every dataset `identifier` was checked to resolve at build time (`integrity.identifier_resolves`
is `true` in all 319 records); every DOI used (AnAge 10.1093/nar/gkx1042, PanTHERIA 10.1890/08-1494.1,
Amniote DB 10.1890/15-0846R.1, AVONET 10.1111/ele.13898, PBDB API 10.1007/s12549-015-0207-y,
MorphoSource 10.1017/S1089332600002862, WoRMS 10.14284/170, NCBI Datasets 10.1038/s41597-024-03571-y,
GBIF backbone 10.15468/39omei) was confirmed to redirect at doi.org. AVONET's download was also
verified against the MD5 published by figshare. No file over 1 MB is committed; the largest
committed file is `mentions.json` (~285 kB).

## Taxa without a trait / reference dataset (occurrence counts only)

| slug | why |
|---|---|
| aceratherium, apatornis-celer, archaeopteryx-lithographica, basilosaurus, belodon, creodonta, cryptoclidus, dimorphodon, ellipsolithes, gomphotherium-angustidens, homo-erectus, homo-neanderthalensis, iguanodon, mesopithecus, notosuchus-terrestris, palaechinus, plesiosauria, protohippus | extinct; the Paleobiology Database occurrence count (and GBIF count where the backbone has the name) is the only dataset built. MorphoSource has no media filed under these GBIF taxonomy strings. |
| mammut-americanum, mammuthus-primigenius | extinct; PBDB + GBIF counts. NCBI Taxonomy knows them but NCBI Datasets lists no genome assembly under these tax_ids at all (ancient-DNA assemblies are filed elsewhere), so no genome record was made. |
| hominoidea | superfamily; not in the GBIF backbone, no column for it in the trait tables. PBDB occurrence count only. |
| ovis-gmelini (mouflon) | GBIF count only; AnAge/PanTHERIA/Amniote file the mouflon under *Ovis orientalis* / *O. aries* and were matched on the accepted name *Ovis gmelini*, so 0 rows. |
| campanularia-macroscyphus | GBIF count only; WoRMS has no exact record for the name (GBIF accepts *Campanularia macroscypha*). |
| crustacea | subphylum; GBIF count only. It was not flagged marine in `taxa_terms.py`, so WoRMS was not queried for it. |
| syrphidae, vespa | insects; no insect trait database was in scope. GBIF count only. |

Taxa with a GBIF key and at least one species-rank reference assembly got an NCBI genome record
(58, e.g. *Homo sapiens* GRCh38.p14, *Mola mola*, *Gadus morhua*, *Pleuronectes platessa*,
*Equus caballus*, *Bos taurus*, *Ovis aries*, *Gallus gallus*, *Crocodylus porosus*). Genus- and
higher-rank taxa were deliberately not given genome records (a reference genome of one member
species is not a dataset *of* the genus).

## Decisions on resolution (archaic names → accepted names)

Thompson's spelling is kept in `names_as_written`; `accepted_name` follows GBIF unless noted.

- *Orthagoriscus* / "sunfish" → *Mola mola*; *Diodon* kept at genus.
- *Eohippus* / *Hyracotherium* → *Hyracotherium* (one taxon file, as instructed). Note that PBDB
  treats *Eohippus* Marsh, 1876 as a separate valid genus (txn 42994) since Froehlich 2002; the
  taxon record uses PBDB *Hyracotherium* 43004.
- *Pithecanthropus* → *Homo erectus*; "Neanderthal" / *Homo neanderthalensis* kept.
- *Zeuglodon* / "Zeuglodonts" → *Basilosaurus* (Zeuglodon Owen, 1839 is a junior synonym).
- *Titanotherium* (incl. *T. robustum*) → *Megacerops*; "Titanotheres" → Brontotheriidae.
- *Mastodon angustidens* → *Gomphotherium angustidens*; "American mastodons" → *Mammut americanum*.
- *Palaeechinus* → *Palaechinus* McCoy, 1844 (Thompson's spelling is an orthographic variant).
- *Cryptocleidus* → *Cryptoclidus* Seeley, 1892.
- *Echinus acutus* → *Gracilechinus acutus*; *Phormosoma luculenter* / *P. tenuis* kept at genus
  *Phormosoma* (both species names are now synonyms in WoRMS).
- *Pseudopriacanthus* → *Pristigenys*; *Lupa* → *Portunus*; *Scyramathia* kept (GBIF accepts the
  name; WoRMS treats it as a synonym of *Rochinia*).
- *Clytia johnstoni* → *Clytia hemisphaerica*; *Gonothyraea hyalina* → *Gonothyraea loveni*;
  *Campanularia macroscyphus* → *C. macroscypha* (GBIF synonymy).
- *Capra sinaitica* ("Arabian wild goat") → *Capra nubiana*; *Cervus duvauceli* → *Rucervus
  duvaucelii*; "jackdaw" → *Coloeus monedula* (GBIF) though queried as *Corvus monedula*;
  "wapiti" → GBIF files it as *Cervus elaphus canadensis* (subspecies); "dog"/"puppies"/"terrier" →
  GBIF *Canis lupus familiaris*.
- *Apatornis celer*: GBIF sinks it into *Ichthyornis celer*; PBDB and the literature keep
  *Apatornis* valid. GBIF's accepted key is recorded; the disagreement is noted in the file.
- "Pinnipedia"/"seals": the GBIF backbone files Pinnipedia as a synonym of Phocidae; the Pinnipedia
  usage key 4941589 is recorded rather than the family, because Thompson's seals are the group.
- "great white rhinoceros (Ceratorhinus)" → *Ceratotherium simum*; Thompson's parenthetical
  *Ceratorhinus* is actually a synonym of *Dicerorhinus* (Sumatran rhinoceros), i.e. a misapplied
  generic name. Plain "rhinoceros" → Rhinocerotidae; "primitive rhinoceros" → *Hyrachyus*.

Vernacular names resolved above species rank (GBIF key present unless stated): "fish/fishes" →
Actinopterygii (not in the GBIF backbone as a class; NCBI/Wikidata/PBDB ids given; the
"shark", "dogfish" and "skate" mentions are separate taxa), "birds" → Aves, "mammals" → Mammalia,
"antelopes" and "hollow-horned ruminants" → Bovidae, "deer" → Cervidae, "goats"/"wild goats"/
"Siberian ibex"/"Scinde wild goat" → *Capra*, "elephants" → Elephantidae (the weighed "Elephant
(Indian)" → *Elephas maximus*), "whales" → Cetacea, "dolphin" → Delphinidae, "sea-cows" → Sirenia,
"anteaters" → Myrmecophagidae, "kangaroo" → *Macropus*, "crabs" → Brachyura, "spider-crabs" →
Majoidea (no GBIF key), "lobster" → *Homarus*, "snail" → Gastropoda, "apple-snail" → Ampullariidae,
"sea-urchins" → Echinoidea, "hydroids" → Hydroidolina (no GBIF key), "coral" → Anthozoa, "owl" →
Strigiformes, "eagle" → *Aquila*, "parrot" → Psittaciformes, "terns" → *Sterna*, "diver" → *Gavia*,
"sandpipers" → Scolopacidae, "plover" → Charadriidae, "curlews" → *Numenius*, "ungulates" →
Artiodactyla (with Perissodactyla recorded separately where named), "dinosaur(s)"/"great
saurians" → Dinosauria, "flying reptiles"/"Ornithosaurian" → Pterosauria, "crocodiles" →
Crocodylia, "tortoise" → Testudinidae, "bee(s)" → *Apis mellifera*, "the ant" → Formicidae.

## Non-animal taxa seen (not built; for a later pass)

- **Foraminifera** (the whole of Chapter XII; Thompson treats them as animals, GBIF/WoRMS place
  them in Chromista/Rhizaria): Foraminifera, Globigerina, Orbulina universa, Pulvinulina menardi,
  Fusulina, Cyclammina cancellata, Triloculina rotunda, Textularia (written "Tertularia") trochus,
  Rotalia, Rhabdammina linearis, Nodosaria, Discorbina bertheloti, Cristellaria reniformis,
  Biloculina, Peneroplis, Lagena, Astrorhiza, Trochammina, Orbitolites, Hastigerina, Cornuspira
  foliacea, Miliolina pulchella, Operculina complanata, Nummulina antiquior, Miliolidae,
  Acervularidae. Claims ch12-01 … ch12-14 therefore name no animal except *Nautilus* (ch12-03) and
  the ammonites (ch12-05).
- **Radiolaria** (lines 19595, 20135); ***Amoeba proteus*** (line 20091).
- **Plants** (Chapter XIII twining plants, Chapter XIV phyllotaxis, Chapter XVI stems, Chapter
  XVII leaves): fir-cones, Norway spruce, common larch, teasel, thistle, sunflower, daisy and
  other composites, stone-crops, mesembryanthemums, palm, woody nightshade (*Solanum dulcamara*),
  *Secale cereale*, *Lilium auratum*, *Phormium tenax*, *Papyrus antiquorum*, *Molinia coerulea*,
  *Pincenectia recurvata*, *Begonia daedalea*, *Dionaea*, bean, gourd, orange, reeds and straw.
- The "bean and the human kidney" (line 24254) contributed only the human mention.

## Ambiguities and caveats

- **"Fish"** is a paraphyletic vernacular. It was resolved to Actinopterygii because every fish
  Thompson works through in these chapters is a teleost; the GBIF backbone has no class for it,
  so that taxon has no GBIF count (PBDB count, AnAge rows via the aliases Teleostei/Chondrostei).
- **"Buffaloes"** (line 20411) → *Bubalus*; *Syncerus* is the alternative reading.
  **"Dogfish"** → *Scyliorhinus canicula*; *Squalus acanthias* is the alternative.
  **"Zebra"** → *Equus quagga*. **"Lobster"** → *Homarus*. **"Eagle"** → *Aquila*.
- **"Equus"** in Chapter XVII is recorded under *Equus caballus* (the horse skull), not the genus.
- **"Man"**: only "human", "man's", "in/of/than/with man", "modern man", and the racial labels of
  Fig. 403 were counted; generic "men's minds", "no man" etc. were not.
- **Mention granularity**: text mentions are one per source line per taxon (a line naming the same
  taxon twice yields one mention; a name split across two lines, e.g. "Cervus / Duvauceli", was
  caught by matching the species epithet). Claim mentions are one per claim per taxon; the quote
  is the sentence of the `claim` or `quote` field that contains the name.
- **GBIF kingdom check**: all 210 GBIF matches are kingdom Animalia. Ten taxa have no GBIF backbone
  usage (Actinopterygii, Selachii, Ammonoidea, Hydroidolina, Majoidea, Hominoidea, Dinosauria,
  Plesiosauria, Pterosauria, Creodonta); they carry NCBI/Wikidata/WoRMS/PBDB ids instead.
- **Wikidata**: resolved by exact match of P225 (taxon name); *Ellipsolithes* has no Wikidata item.
- **PBDB** sinks *Ellipsolithes* as an "invalid subgroup of Ammonoidea"; its own taxon_no (450543) is
  recorded with the accepted parent in the `pbdb` block.
- **Shared-database row counts** (`taxa_rows`) are column matches: species by exact binomial, genus/
  family/order/class by the corresponding column, so a class like Aves counts every bird row. A
  species filed under a different synonym in a given table (e.g. mouflon) yields 0 and is omitted.
- **MorphoSource** counts use the `taxonomy_gbif` facet, which is hierarchical, so nested taxa
  overlap (Mammalia 59 821 media includes every mammal). Media licences vary per record.
- **Landing pages that block automated clients**: www.gbif.org occurrence pages, paleobiodb.org
  "classic" pages and esapubs.org directory pages return HTTP 403 to scripts. The records therefore
  use the resolving API URL (GBIF, PBDB) or the data-paper DOI (PanTHERIA, Amniote DB) as
  `identifier`, with the human page kept in `landing_page`. FishBase.org likewise returns 403; the
  fishbase.se mirror is used.
- **Licences**: PanTHERIA and the Amniote DB carry no explicit licence (ESA Ecological Archives
  data papers); `license` is `null` with a note. FishBase is CC BY-NC 4.0, AVONET CC BY 4.0, AnAge
  CC BY 3.0, PBDB and WoRMS CC BY 4.0, GBIF per-dataset, NCBI public domain.
- **Checksums**: `sha256` of downloaded files was computed locally; only AVONET has a publisher
  checksum to compare against (MD5, matched). For API queries the `sha256` is of the cached JSON
  response body (keys sorted), noted in each distribution.
- Vernacular dataset coverage was prioritised by mention frequency; the top text-mentioned taxa
  are fish (41 lines), human (39), birds (34), sheep (31), horse (29), Bovidae (24), ox (17),
  whales (15), plaice (14), crocodiles (14), rhinoceros (13), haddock (13).

Branch: `cursor/thompson-organisms-ch12-epilogue-859f`.
