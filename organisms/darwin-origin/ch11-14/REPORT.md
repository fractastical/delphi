# Organisms: Darwin, *On the Origin of Species* (1859), Chapters XI–XIV

Slice `ch11-14` of project `darwin-origin`: Geographical Distribution (XI, XII), Mutual Affinities /
Morphology / Embryology / Rudimentary Organs (XIII), Recapitulation and Conclusion (XIV).
Text: `darwin-origin/inputs/pg1228.txt`, lines 10412–14617 (the Index that follows is excluded).
Claims: the 74 rows of `darwin-origin/claims.json` whose `chapter` is XI, XII, XIII or XIV.

Built by a Cursor cloud agent (Claude Fable 5.1) on branch `cursor/darwin-ch11-14-organisms-de91`,
2026-10-31. Nothing was scored, no claim/assessment/nanopub file was touched, nothing was published.

## Counts

| | |
|---|---|
| Mentions (`mentions.json`) | **560** — 30 from claim `claim`/`quote` fields (14 of the 74 claims name an animal), 530 from the chapter text with file/line sources |
| Distinct animal taxa (`taxa/`) | **109** — 28 species, 25 genera, 22 families, 16 orders, 6 classes, 2 phyla, 10 intermediate ranks (subphylum, infraclass, suborder, infraorder, superorder, superfamily) |
| Taxa required by claims | 17 (Actinopterygii, Amphibia, Anura, Arthropoda, Aves, *Canis familiaris*, Cetacea, Chiroptera, *Columba livia*, Crustacea, *Equus caballus*, *Homo sapiens*, Mammalia, Mollusca, Ruminantia, Salamandridae, Vertebrata) — all resolved, each with 3–7 dataset records |
| Resolved to GBIF backbone | 97 / 109 |
| Resolved to NCBI Taxonomy | 107 / 109 |
| Resolved to Wikidata (P225 + P31 taxon check) | 109 / 109 |
| Resolved to ITIS | 106 / 109 |
| Resolved to WoRMS/Aphia | 85 / 109 |
| Resolved to Paleobiology Database | 105 / 109 |
| Dataset records (`datasets/`) | **209** — 97 GBIF occurrence counts, 24 NCBI reference-genome assemblies, 79 NCBI reference-genome counts for taxa above species, 3 PBDB fossil occurrence counts (extinct taxa), 6 shared databases (AnAge build 15, PanTHERIA 1.0, Amniote Life-History DB 2015, EltonTraits 1.0, AVONET figshare v7, WoRMS Aphia records) |
| Taxa with no dataset record | 0 |
| Taxa whose only datasets are GBIF + WoRMS (no trait, genome or fossil dataset) | 1 (*Helix pomatia*; see below) |
| Files vendored (< 1 MB) | 2 in `data/`: `anage_build15_dataset.zip` (169,150 B), `EltonTraits_MamFuncDat.txt` (579,107 B). PanTHERIA (2.4 MB), Amniote DB (4.7 MB), EltonTraits birds (2.2 MB) and AVONET (21.5 MB) were downloaded, inspected and checksummed but not committed |

Most-mentioned taxa: Aves 74, Mammalia 51, Actinopterygii ("fish") 33, *Homo sapiens* 28, *Columba livia* 26,
Insecta 23, Chiroptera 21, *Equus caballus* 15, Crustacea 14, *Bos taurus* 12, *Canis familiaris* 11,
Marsupialia 11.

## How it was built (`scripts/`)

- `seed.py` — the taxon list (query name, rank, vernacular, notes), the regex patterns used to sweep the
  chapter text, an exclusion list for false positives ("bear" the verb, "cuttle-fish" matching "fish"), and
  the claim-field mentions.
- `build_mentions.py` — writes `mentions.json`; every text mention carries `line_start`/`line_end` and the
  verbatim line(s); every claim mention carries the claim id, the field and a verbatim window.
- `resolve_taxa.py` — GBIF `species/match` (+ backbone lookup for higher taxa), NCBI E-utilities
  (restricted to `Metazoa[Subtree]`), Wikidata (`wbsearchentities` and `haswbstatement:P225=…`, then
  `wbgetentities` to check P225 and a taxon-class P31), ITIS, WoRMS REST, PBDB `taxa/single`. A GBIF usage
  is accepted only if it is ACCEPTED, its rank is compatible with Darwin's taxon, and (above species) it has
  descendants; rejected usages are kept under `resolution.gbif.rejected_usages`.
- `fetch_datasets.py` — downloads and checksums every file, pulls author lists and titles for every DOI from
  CrossRef (no citation typed from memory), checks each DOI against the Handle System and each landing URL,
  counts rows per taxon (species by binomial; higher taxa by lineage columns plus the explicit group lists in
  `GROUPS`), and writes the `datasets` field of each taxon file.

All API responses were cached under `/tmp`; re-running the scripts reproduces the records (GBIF/NCBI counts
will move with the live services; each record pins `retrieved_at`, `byte_size` and `sha256` of the response
actually received).

## Resolution gaps, by authority

**GBIF backbone (12 unresolved).** `Vertebrata`, `Crustacea`, `Cirripedia`, `Ruminantia`, `Marsupialia`,
`Serpentes`, `Brachyura`, `Papilionoidea`, `Dinornithiformes`, `Ichthyosauria` are ranks the current backbone
does not carry; the only usages with these names are stray ones that were rejected on purpose — a "family"
Marsupialia (9712517, 2,154 occurrences), a "family" Brachyura (11132538), a "family" Serpentes (11205692)
and a doubtful "genus" Crustacea (10996236, classified in Insecta). `Actinopterygii` (204) and `Reptilia`
(358) exist as class usages but are orphans in the current backbone (0 descendants, 0 occurrences; fish orders
hang directly from Chordata, reptiles are split into the classes Squamata, Testudines, Crocodylia and
Sphenodontia), so they were left null rather than attach a meaningless occurrence count.

**NCBI Taxonomy (2).** `Reptilia` — NCBI uses Sauropsida; "Reptilia" is only a synonym attached to
Lepidosauria/Testudines/Crocodylia. `Ichthyosauria` — no sequenced material.

**ITIS (3).** Ichthyosauria, Ruminantia, Dinornithiformes.

**WoRMS/Aphia (24).** Purely terrestrial taxa with no Aphia record (e.g. *Panthera leo*, Macropodidae,
Cynipidae, Vombatus, Dinornithiformes). The 85 that do resolve include many non-marine taxa that Aphia hosts
(flagged `is_marine` per distribution in the WoRMS dataset record).

**PBDB (4).** *Helix pomatia*, *Mimus melanotis*, *Bombyx mori*, Lumbricidae.

`Canis familiaris`: GBIF (6164210) and NCBI (9615) both file the domestic dog as the subspecies *Canis lupus
familiaris*; those usages were kept, Wikidata keeps a separate *Canis familiaris* item (Q20717272).

## Taxa without a trait/reference dataset

- ***Helix pomatia*** — only the GBIF occurrence count (and its MolluscaBase/WoRMS Aphia record). AnAge has
  no row for it, there is no NCBI genome assembly for the species (0 assemblies of any kind), and BOLD's
  public API was not reachable from this environment (HTTP 403).

Thirteen further invertebrate taxa (Aphis, Scleractinia, Coleoptera, Stylommatophora, Ichneumonidae,
Cynipidae, Ancylus, Brachyura, Dytiscus, Lumbricidae, Cirripedia, Colymbetes, Sphingidae) have no row in any
of the five trait databases (which cover vertebrates, plus a few invertebrates in AnAge); their non-GBIF
coverage is the WoRMS record and the NCBI reference-genome count for the taxon. Fossil taxa (Dusicyon
australis, Dinornithiformes, Ichthyosauria) have PBDB occurrence counts (1, 108 and 675 records
respectively; see the records for the exact values retrieved).

## Non-animal taxa seen (not built)

Plants only; no fungi or microbes are named in these chapters.

Algæ (L11299, 12473); seaweed (L11738); *Nelumbium* / *Nelumbium luteum*, the great water-lily
(L11622–11629); yellow water-lily (L11616); *Potamogeton* (L11617); duck-weed (L11560–11562);
*Helosciadium* (L10809); oak and oak-tree (L10858, 14437); wild rose (L14437); fir-trees (L14089);
Proteaceæ (L12438); Connaraceæ with *Cnestis* and *Connarus* (L12442–12446); grasses (L12464, 12474);
Malpighiaceæ and *Aspicarpa* (L12496–12500); orchids *Monochanthus*, *Myanthus*, *Catasetum* (L12710);
cowslip and primrose (L12708, 14467); pine-apple (L12671); common and swedish turnip (L12672, 12787);
ulex/furze, phyllodineous acacias, Leguminosæ (L13146–13148); Compositæ (L13503); snapdragon /
*Antirrhinum* (L13522); cauliflower (L13572); ferns (L11686); crop seeds in the sea-water and
bird-crop experiments — peas, vetches, oat, wheat, millet, canary(-grass), hemp, clover, beet (L10863,
10893); "dicotyledonous plants" (L10859).

## Ambiguous or judgement calls

- **"fish"/"fishes" → Actinopterygii.** "Fish" is paraphyletic; everything Darwin discusses (fresh-water
  and shore fishes, fish with a nascent lung-like swim-bladder) is ray-finned. *Lepidosiren* is its own taxon.
- **"Articulata"/"articulate classes" → Arthropoda.** Cuvier's Articulata also contained annelids;
  Darwin's examples (segments, jaws and legs of crustaceans, insect mouthparts) are arthropods.
- **"Pachyderms" (L12462) and "pachydermatous animal" (L12782).** Obsolete Pachydermata; no modern taxon
  corresponds, so no mention or taxon was built. The dugong sentence is recorded under *Dugong dugon*.
- **"the extinct gigantic sea-lizards" (L13043) → Ichthyosauria.** Darwin may equally have meant
  plesiosaurs; both have paddles with the pattern "obscured".
- **"gigantic wingless birds" of New Zealand (L11745) → Dinornithiformes (moa).**
- **"a thrush … created to dive and feed on sub-aquatic insects" (L14069) → Cinclus** (the dipper, which
  Darwin calls a thrush in Ch. VI); "the thrush of South America … lines her nest with mud" (L14162) →
  *Turdus*; "the thrush group" (L13143) → Turdidae; "blackbird" → *Turdus merula*.
- **"a bird, under the form of woodpecker … on the ground" (L14066) → Picidae** (the La Plata *Colaptes
  campestris* of Ch. VI, not named here). **"a petrel … fitting it for the life of an auk or grebe"
  (L14070) → Procellariiformes** (the diving petrel *Pelecanoides*). **"upland geese" → Chloephaga**;
  **"logger-headed duck" → Tachyeres**; **"fishing-eagles" → Accipitridae**.
- **"bizcacha" → *Lagostomus maximus*; "an alpine species of bizcacha" → *Lagidium*.** **"phascolomys" →
  *Vombatus*** (Phascolomys is a junior synonym). **"edentata in America" → Xenarthra.**
- **"foxes" on icebergs "in the arctic regions" (L11807) → *Vulpes*** (genus, not *V. lagopus*).
  **"a wolf-like fox" of the Falklands → *Dusicyon australis*** (extinct).
- **"wading birds", "birds of prey", "water-birds", "land-birds", "marine birds" → Aves.** Darwin's
  "order" of wading birds is the obsolete Grallatores.
- **"shells", "sea-shells", "fresh-water shells", "molluscs" → Mollusca; "land-shells" → Stylommatophora;
  "coral" → Scleractinia; "worms crawling through the damp earth" → Lumbricidae; "bug" and "an
  homopterous insect" → Hemiptera; "cuttle-fish" → Sepiida; "Dyticus" → *Dytiscus*; "newts" →
  Salamandridae; "Batrachians" → Amphibia; "ærial mammals" → Chiroptera.**
- **Domestic breeds → species**, with breed names in `names_as_written`/`notes`: pigeon (pouters, fantails,
  runts, barbs, dragons, carriers, tumblers, short-faced tumbler, carrier-pigeons, rock-pigeon), dog
  (greyhound, bulldog), horse (cart-horse, race-horse), cattle (hornless breeds, cows, calves, ox), domestic
  duck → *Anas platyrhynchos*, turkey, silk-moth → *Bombyx mori*, hive-bee → *Apis mellifera*.
- **Generic words were not treated as taxa**: "animals", "organisms", "productions", "inhabitants",
  "species", "quadrupeds" (recorded as Mammalia), "parasitic/suctorial crustaceans" (recorded as
  Crustacea). Hence only 14 of the 74 claims contribute claim-field mentions; the others speak of species,
  forms and productions generically.
- **Higher-taxon row counts in the shared databases** depend on lineage columns and the explicit group
  lists in `fetch_datasets.py` (`GROUPS`): Marsupialia via its seven orders, Ruminantia via six families,
  Cetacea via the order or its fourteen families, Serpentes via 28 families (Amniote DB), Vertebrata and
  Actinopterygii via class lists (AnAge files fishes under "Teleostei"). EltonTraits' mammal file has no
  order column; orders were filled from PanTHERIA's MSW05 family→order map. AVONET counts come from the
  `AVONET1_BirdLife` sheet only. AnAge build 15 distributes 4,645 species rows although its release notes
  announce 4,671 entries; the record states the rows as distributed.
- **The WoRMS record** lists every taxon with an AphiaID (85), including terrestrial ones that Aphia hosts
  (e.g. *Homo sapiens*, *Equus*); each distribution carries the record's `is_marine` flag. Mollusc records
  are MolluscaBase's.
- **Licences** for the three ESA Ecological Archives data papers (PanTHERIA, Amniote DB, EltonTraits) are
  not stated in the archive and are recorded as such rather than guessed; their `identifier` is the data
  paper DOI because the `esapubs.org` directory pages return 403 while the data files download normally.
- The Falkland-wolf GBIF count (and every GBIF count) includes all descendant usages and changes daily; the
  record pins the date and the checksum of the JSON actually received.
