# darwin-origin / ch05-06 — animal taxa in Chapters V–VI of *On the Origin of Species*

Slice: `darwin-origin/inputs/pg1228.txt` lines 4140–6369 (Chapter V "Laws of Variation", Chapter VI
"Difficulties on Theory") and claims `darwin1859-ch05-*` (17) and `darwin1859-ch06-*` (17).
Built 2026-10-31 by a cloud agent (`claude-fable-5.1`, branch `cursor/organisms-darwin-ch05-06-5739`).
No `assessment` fields were written; nothing was signed or published.

## Counts

| what | count |
|---|---|
| mentions in `mentions.json` | 214 (11 sourced to claim ids, 203 to text line ranges) |
| distinct animal taxa (`taxa/`) | 112 |
| taxa resolved to GBIF backbone `usageKey` | 104 |
| taxa resolved to NCBI Taxonomy taxid | 109 |
| taxa resolved to Wikidata QID (P225 verified) | 112 |
| taxa resolved to all three authorities | 102 |
| dataset records (`datasets/`) | 137 |
| — GBIF occurrence-count records (one per taxon) | 101 |
| — NCBI genome assembly records (one per species-level taxon with an assembly) | 28 |
| — shared trait / fossil / status databases | 5 (AnAge, EltonTraits, PanTHERIA, PBDB, IUCN via GBIF) |
| — taxonomy authority records for the slice | 3 (GBIF backbone, NCBI Taxonomy, Wikidata) |

Taxa by rank: species 31, subspecies 2, genus 27, subfamily 2, tribe 1, family 21, infraorder 2,
suborder 1, order 13, superorder 1, infraclass 1, class 5, subphylum 2, phylum 3.

Every quote in `mentions.json` was checked verbatim (whitespace-normalised) against the cited text
lines or the claim's `quote`. Claim-sourced mentions are only recorded where the claim's own quote
contains the name; e.g. claim `darwin1859-ch06-12` names monkey/horse/bat/seal in its *claim* text
but not in its quote, so those are recorded as text mentions at lines 6159–6167 instead.

All taxa and dataset identifiers were obtained from live API responses on 2026-10-31 (GBIF
`species/match` with `kingdom=Animalia`, NCBI E-utilities `esearch`+`esummary`, Wikidata
`wbsearchentities`+`wbgetentities` with the P225 taxon name checked). The raw responses were saved
and their `byte_size`/`sha256` recorded in the taxonomy dataset records; the bodies themselves are
not committed (only `REPORT.md`, `mentions.json`, `taxa/`, `datasets/`).

## Shared datasets and coverage

| dataset id | taxa covered | what was inspected |
|---|---|---|
| `anage-build-15` | 78 | `dataset.zip` (169,150 B) → `anage_data.txt`, 4,645 rows (release notes say 4,671) |
| `eltontraits-1-0` | 65 | `BirdFuncDat.txt` (10,011 rows) and `MamFuncDat.txt` (5,400 rows) from figshare 3559887 |
| `pantheria-1-0-wr05-aug2008` | 35 | `PanTHERIA_1-0_WR05_Aug2008.txt`, 5,416 rows |
| `pbdb-occurrence-counts-2026-10-31` | 103 | one `occs/list.json?base_name=…&rowcount=true` response per taxon |
| `iucn-red-list-via-gbif-2026-10-31` | 23 | GBIF `species/{key}/iucnRedListCategory` per species-level taxon |
| `gbif-backbone-taxonomy-2026-10-31` | 104 | one `species/match` response per taxon (+ `species/{key}` for 9 manually verified keys) |
| `ncbi-taxonomy-2026-10-31` | 109 | one `esearch` response per taxon |
| `wikidata-taxon-items-2026-10-31` | 112 | one `wbgetentities` response per taxon |

Higher-rank coverage in AnAge / EltonTraits / PanTHERIA is matched on the files' own
Phylum/Class/Order/Family/Genus columns; ranks those files do not carry (subfamily, tribe,
infraorder, suborder, superorder, subphylum, infraclass, subspecies) are not matched, so e.g.
Cirripedia, Serpentes, Batoidea have no AnAge rows even though AnAge contains barnacles, snakes and
rays. Per-taxon row counts are in each record's `counts` (`n_rows:<slug>`).

Not used, and why:

- **BOLD**: `v4.boldsystems.org/index.php/API_Public/stats` returned HTTP 403 from this environment.
- **FishBase**: the `fishbase.ropensci.org` API returned empty responses; no file inspected.
- **AVONET**, **Amniote Life-History Database**: distributed as multi-MB xlsx/csv; not downloaded in
  this pass, so no coverage could be verified and no record was written.
- **IUCN Red List API**: requires a token; categories were taken instead from the IUCN checklist as
  indexed by GBIF (dataset `19491596-35ae-4a91-9a98-85cf505f1bd3`, DOI 10.15468/0qnb58).
- **TimeTree**, **MorphoSource**, **Open Tree of Life**: not queried in this pass.

## Taxa with no usable dataset

- `proteolepas` — only the three taxonomy-authority records. GBIF key 2203053 (Proteolepas Darwin,
  1854) is `DOUBTFUL`, placed in Isopoda: Crinoniscidae, with 0 occurrences; not in NCBI Taxonomy
  or PBDB. Darwin's "cirripede" is now regarded as a parasitic isopod larva.

Taxa with **no GBIF occurrence-count record** (11): `scarabaeinae`, `cirripedia`, `lutrinae`,
`pteromyini`, `crustacea`, `batoidea`, `vertebrata`, `simiiformes` have no GBIF backbone usage
(the backbone lacks these ranks/nodes); `reptilia` (key 358 is a pro-parte synonym), `actinopterygii`
(class key 204 is in the backbone but the occurrence index attaches no records to it: fish
occurrences carry `classKey: null`) and `proteolepas` returned count 0, which was not recorded as a
dataset. The GBIF keys 11132538 (Brachyura) and 11205692 (Serpentes) are backbone placeholders
ranked FAMILY with no descendants; their non-zero counts (30,320 and 5,490) are recorded but should
be read as records matched to the bare name, not the whole infraorder/suborder.

Species-level taxa with **no genome assembly** in NCBI Datasets (reference or otherwise, checked
without the `reference_only` filter): `scarabaeus-sacer`, `proteus-anguinus`, `equus-hemionus`,
`equus-quagga-quagga`, `colaptes-campestris`. For `canis-lupus` the reference query returns only
subspecies assemblies; the Mexican wolf `GCF_048164855.1` is recorded for the wolf and the dog
`GCF_011100685.1` for `canis-familiaris`.

## Resolution notes and ambiguities

- **Edentata** (line 4543) is not a valid taxon; "armadilloes" → Cingulata, "scaly ant-eaters" →
  Pholidota. No record for "Edentata" itself.
- **Articulata** (lines 5792, 5812) is Cuvier's group (Arthropoda + Annelida); resolved to
  Arthropoda because Darwin's examples are crustacean eyes.
- **"Rays"** → Batoidea; Wikidata's item Q6495741 carries P225 "Batomorphi" with Batoidea as alias.
- **"zebra"** → *Equus zebra* (mountain zebra, the 1859 sense of "the zebra"); Darwin may have meant
  zebras generally. **"quagga"** → *Equus quagga quagga* (extinct subspecies). **"koulan of
  Pallas"** → *Equus hemionus* (subspecies kulan). Mules and ass×zebra / ass×hemionus hybrids are
  recorded under the genus `equus`.
- **"logger-headed duck" / "Micropterus of Eyton"** → genus *Tachyeres* (Micropterus Eyton is a
  junior homonym); species not determinable.
- **"Onites apelles"** → genus *Onitis*; the epithet does not match a backbone name.
- **"Ateuchus or sacred beetle"** → *Scarabaeus sacer*.
- **"Engidæ"** (Westwood) → Erotylidae (type genus Engis = Dacne).
- **"Galeopithecus or flying lemur"** → Cynocephalidae; **"Lemuridæ"** recorded as Darwin wrote it.
- **"Puffinuria berardi"** → genus *Pelecanoides* (*P. urinatrix berard(i)* / *P. magellani*).
- **"Saurophagus sulphuratus"** → *Pitangus sulphuratus*; **"Mustela vison"** → *Neogale vison*
  (GBIF's accepted name is still *Mustela vison*, key 5218823).
- **"cave-rat"** → *Neotoma* (Mammoth Cave Allegheny woodrat); **"crabs"** of the Kentucky/Styrian
  caves recorded as Brachyura although the Mammoth Cave decapods are crayfish.
- **"fish"/"fishes"** (incl. electric fishes) → Actinopterygii; Darwin's electric fishes also
  include *Torpedo* (Chondrichthyes).
- **"stags"** → *Cervus*; **"kestrel"** → *Falco*; **"creeper"** → *Certhia*; **"nuthatch"** →
  *Sitta*; **"shrike"** → Laniidae; **"eagle"** → *Aquila*; **"seal"** → Phocidae; **"monkey"** →
  Simiiformes; **"otter"** → Lutrinae; **"polecats"** → *Mustela*; **"quail"/"partridge"** →
  *Coturnix coturnix* / *Perdix perdix* (British sense); **"wasp"** → Vespidae; **"ichneumon"** →
  Ichneumonidae; **"flies"** → Diptera; **"hare"** → *Lepus*; **"rat"/"mouse"** → *Rattus* / *Mus*.
- **Canis familiaris**: GBIF treats it as a synonym of *Canis lupus familiaris* (accepted key
  6164210, recorded; synonym key 5219200 noted); NCBI 9615; Wikidata Q20717272.
- **Reptilia**: GBIF key 358 is a pro-parte synonym and NCBI has no Reptilia node (`ncbi_taxid`
  null). **Crustacea**: no GBIF node; NCBI merged 6657 into Pancrustacea (`ncbi_taxid` null).
- GBIF `species/match` returned higher-rank fallbacks for Amblyopsis, Mus, Balanus, Mustela,
  Actinopterygii, Hydra; the correct usages were taken from the `alternatives` list and verified at
  `species/{key}`. For *Balanus* the backbone has two genus usages; key 2115691 (Costa, 1778,
  `DOUBTFUL`, 168 descendants) is recorded rather than the 3-descendant artefact "Balanus Da, 1778".
- Not resolved to any record: **"vulture"** (line 6088; polyphyletic Accipitridae/Cathartidae) and
  **"grallatores"** (line 5733; obsolete order of wading birds). Generic phrases ("beasts of prey",
  "domestic quadrupeds", "larger quadrupeds", "cave-animals", "animals kept by savages", "mountain
  breeds") were not recorded.

## Non-animal taxa seen (not built)

Plants: "sporting" plants (4174), Moquin-Tandon's fleshy-leaved sea-shore plants (4195), succulent
plants (4402), pines and rhododendrons from the Himalaya (4414), European plants from the Azores
(4419), fruit trees of the United States (4472), Jerusalem artichoke (4476), kidney-bean (4479),
cabbage (4620), Compositae/Compositous plants and the daisy (4549–4563), Umbelliferae (4550, 4558,
4585), garden pelargoniums (4570), polyandrous flowers (4673), Swedish turnip, Ruta baga and common
turnip (4977–4981), snapdragon *Antirrhinum* (5031–5032), plants with blue/red flowers (4833), yew
(5685), exotic plants (5676), *Orchis* and *Asclepias* (5976–5977), trailing bamboo of the Malay
Archipelago (6080), orchis (6252), fir-trees (6254), plants of New Zealand/Europe (6218).
Fungi and microbes: none noticed in this slice (*Proteus* here is the olm, not the bacterium;
*Hydra* is the cnidarian).

## Validator

`node organisms/validate.mjs darwin-origin/ch05-06` → 214 mentions, 112 taxa, 137 datasets,
0 errors, 0 warnings.

## Taxon table

| slug | accepted name | rank | GBIF | NCBI | Wikidata | GBIF occ. | datasets |
|---|---|---|---|---|---|---|---|
| actinopterygii | Actinopterygii | class | 204 | 7898 | Q127282 | 0 | 5 |
| alcedinidae | Alcedinidae | family | 2984 | 8937 | Q8154335 | 15,553,075 | 7 |
| alcidae | Alcidae | family | 2985 | 28683 | Q28294 | 4,388,105 | 7 |
| amblyopsis | Amblyopsis | genus | 2401736 | 940463 | Q2842124 | 665 | 4 |
| anas-platyrhynchos | Anas platyrhynchos | species | 9761484 | 8839 | Q25348 | 32,837,623 | 9 |
| anatidae | Anatidae | family | 2986 | 8830 | Q7556 | 199,340,785 | 7 |
| annelida | Annelida | phylum | 42 | 6340 | Q25522 | 10,039,471 | 6 |
| apis-mellifera | Apis mellifera | species | 1341976 | 7460 | Q30034 | 1,325,010 | 7 |
| apteryx | Apteryx | genus | 2495138 | 8821 | Q43642 | 14,051 | 7 |
| aquila | Aquila | genus | 2480498 | 8960 | Q30085 | 2,107,856 | 7 |
| arthropoda | Arthropoda | phylum | 54 | 6656 | Q1360 | 392,596,717 | 6 |
| aves | Aves | class | 212 | 8782 | Q5113 | 2,265,012,529 | 7 |
| balanidae | Balanidae | family | 9152 | 37806 | Q266221 | 407,191 | 5 |
| balanus | Balanus | genus | 2115691 | 6677 | Q2336729 | 281,478 | 5 |
| batoidea | Batoidea | superorder | — | 117893 | Q6495741 | — | 3 |
| bos-taurus | Bos taurus | species | 2441022 | 9913 | Q19610691 | 467,812 | 9 |
| brachyura | Brachyura | infraorder | 11132538 | 6752 | Q40802 | 30,320 | 5 |
| canis-familiaris | Canis lupus familiaris | subspecies | 6164210 | 9615 | Q20717272 | 124,431 | 6 |
| canis-lupus | Canis lupus | species | 5219173 | 9612 | Q18498 | 263,719 | 10 |
| carnivora | Carnivora | order | 732 | 33554 | Q25306 | 9,750,357 | 7 |
| certhia | Certhia | genus | 2487601 | 73329 | Q1991437 | 6,059,865 | 7 |
| cervus | Cervus | genus | 2440948 | 9859 | Q644255 | 732,951 | 8 |
| cetacea | Cetacea | order | 733 | 9721 | Q160 | 3,226,115 | 7 |
| chiroptera | Chiroptera | order | 734 | 9397 | Q28425 | 10,135,671 | 7 |
| chloephaga-picta | Chloephaga picta | species | 5232428 | 8861 | Q129036 | 90,463 | 8 |
| cinclus-cinclus | Cinclus cinclus | species | 2495093 | 127875 | Q201831 | 691,012 | 9 |
| cingulata | Cingulata | order | 735 | 948951 | Q1242326 | 104,081 | 7 |
| cirripedia | Cirripedia | infraclass | — | 6675 | Q220457 | — | 3 |
| cobitis | Cobitis | genus | 2349691 | 47718 | Q868117 | 100,697 | 5 |
| colaptes-campestris | Colaptes campestris | species | 2478233 | 555237 | Q1274176 | 161,971 | 7 |
| coleoptera | Coleoptera | order | 1470 | 7041 | Q22671 | 40,873,178 | 5 |
| columba-livia | Columba livia | species | 2495414 | 8932 | Q42326 | 15,304,825 | 9 |
| coturnix-coturnix | Coturnix coturnix | species | 2474156 | 9091 | Q28358 | 527,401 | 9 |
| crex-crex | Crex crex | species | 4408498 | 185586 | Q26017 | 296,881 | 8 |
| crotalus | Crotalus | genus | 2444354 | 8728 | Q463637 | 182,223 | 6 |
| crustacea | Crustacea | subphylum | — | — | Q25364 | — | 2 |
| ctenomys | Ctenomys | genus | 2439605 | 33551 | Q908146 | 8,238 | 8 |
| cynocephalidae | Cynocephalidae | family | 9370 | 30657 | Q11762767 | 3,745 | 8 |
| diptera | Diptera | order | 811 | 7147 | Q25312 | 45,886,191 | 6 |
| elephantidae | Elephantidae | family | 9427 | 9780 | Q2372824 | 81,382 | 8 |
| equus-asinus | Equus asinus | species | 2440891 | 9793 | Q19829417 | 12,774 | 9 |
| equus-caballus | Equus caballus | species | 2440886 | 9796 | Q10758650 | 107,617 | 9 |
| equus-hemionus | Equus hemionus | species | 2440893 | 9794 | Q180960 | 8,639 | 9 |
| equus-quagga-quagga | Equus quagga quagga | subspecies | 5787161 | 555873 | Q45969 | 8 | 4 |
| equus-zebra | Equus zebra | species | 2440888 | 9791 | Q243213 | 1,998 | 10 |
| equus | Equus | genus | 8652950 | 9789 | Q27022 | 224,802 | 8 |
| erotylidae | Erotylidae | family | 6981 | 196992 | Q1194119 | 167,191 | 5 |
| exocoetidae | Exocoetidae | family | 2968 | 76072 | Q183686 | 36,708 | 5 |
| falco | Falco | genus | 2480996 | 8952 | Q43489 | 18,967,810 | 7 |
| felis-catus | Felis catus | species | 2435035 | 9685 | Q20980826 | 231,047 | 9 |
| fregata | Fregata | genus | 2480184 | 37041 | Q203472 | 873,916 | 7 |
| fulica | Fulica | genus | 2474376 | 9120 | Q637533 | 12,315,856 | 7 |
| galliformes | Galliformes | order | 723 | 8976 | Q21659 | 18,747,373 | 7 |
| gallinula-chloropus | Gallinula chloropus | species | 5228199 | 9123 | Q18847 | 6,093,370 | 9 |
| gallus-gallus | Gallus gallus | species | 9326020 | 9031 | Q184774 | 298,032 | 9 |
| giraffa-camelopardalis | Giraffa camelopardalis | species | 2441205 | 9894 | Q15083 | 6,816 | 10 |
| homo-sapiens | Homo sapiens | species | 2436436 | 9606 | Q15978631 | 24,173 | 9 |
| hydra | Hydra | genus | 9811888 | 6083 | Q192290 | 12,461 | 4 |
| hymenoptera | Hymenoptera | order | 1457 | 7399 | Q22651 | 32,110,163 | 6 |
| ibla | Ibla | genus | 2113884 | 58184 | Q15896258 | 359 | 4 |
| ichneumonidae | Ichneumonidae | family | 3512 | 7408 | Q1138186 | 1,710,214 | 5 |
| insecta | Insecta | class | 216 | 50557 | Q1390 | 344,562,868 | 6 |
| laniidae | Laniidae | family | 9315 | 9193 | Q171052 | 6,636,854 | 7 |
| lemuridae | Lemuridae | family | 5485 | 9445 | Q186462 | 14,532 | 8 |
| lepidoptera | Lepidoptera | order | 797 | 7088 | Q28319 | 173,621,126 | 6 |
| lepus | Lepus | genus | 2436691 | 9980 | Q46076 | 2,245,175 | 8 |
| lutrinae | Lutrinae | subfamily | — | 169417 | Q200184 | — | 3 |
| mammalia | Mammalia | class | 359 | 40674 | Q7377 | 59,014,871 | 8 |
| meleagris-gallopavo | Meleagris gallopavo | species | 9606290 | 9103 | Q26844 | 2,757,440 | 9 |
| mollusca | Mollusca | phylum | 52 | 6447 | Q25326 | 34,583,597 | 6 |
| mus | Mus | genus | 9800657 | 10088 | Q39275 | 317,012 | 8 |
| mustela | Mustela | genus | 2433922 | 9665 | Q28521 | 526,104 | 8 |
| neogale-vison | Neogale vison | species | 5218823 | 452646 | Q27179 | 89,339 | 10 |
| neotoma | Neotoma | genus | 2438433 | 42407 | Q468544 | 97,724 | 8 |
| odonata | Odonata | order | 789 | 6961 | Q25375 | 17,337,759 | 5 |
| onitis | Onitis | genus | 1093671 | 166329 | Q518542 | 15,193 | 4 |
| otididae | Otididae | family | 9610 | 54375 | Q21755 | 538,524 | 7 |
| ovis-aries | Ovis aries | species | 2441110 | 9940 | Q29350771 | 167,893 | 9 |
| parus-major | Parus major | species | 9705453 | 9157 | Q25485 | 14,626,271 | 9 |
| pelecanoides | Pelecanoides | genus | 2481417 | 37077 | Q539433 | 40,045 | 6 |
| perdix-perdix | Perdix perdix | species | 2473958 | 9052 | Q26106 | 697,776 | 9 |
| phocidae | Phocidae | family | 5310 | 9709 | Q25587 | 2,572,468 | 8 |
| pholidota | Pholidota | order | 796 | 9971 | Q1300407 | 5,564 | 7 |
| picidae | Picidae | family | 9333 | 9220 | Q25439 | 89,637,867 | 7 |
| picus-viridis | Picus viridis | species | 2478523 | 100825 | Q166171 | 2,618,961 | 9 |
| pitangus-sulphuratus | Pitangus sulphuratus | species | 2482755 | 371930 | Q202804 | 2,440,928 | 8 |
| podicipedidae | Podicipedidae | family | 9338 | 30448 | Q21695 | 18,265,528 | 7 |
| pongo | Pongo | genus | 5219531 | 9599 | Q41050 | 8,805 | 8 |
| procellariiformes | Procellariiformes | order | 7192755 | 30449 | Q21685 | 5,354,740 | 7 |
| proteolepas | Proteolepas | genus | 2203053 | — | Q11847165 | 0 | 2 |
| proteus-anguinus | Proteus anguinus | species | 2432042 | 221568 | Q15856 | 777 | 6 |
| pteromyini | Pteromyini | tribe | — | 337748 | Q9490 | — | 3 |
| pyrgoma | Pyrgoma | genus | 4335560 | 432342 | Q18593191 | 353 | 5 |
| rattus | Rattus | genus | 2439223 | 10114 | Q36396 | 762,568 | 8 |
| reptilia | Reptilia | class | 358 | — | Q10811 | 0 | 4 |
| rhinocerotidae | Rhinocerotidae | family | 9415 | 9803 | Q34718 | 45,686 | 8 |
| rodentia | Rodentia | order | 1459 | 9989 | Q10850 | 11,849,723 | 7 |
| scarabaeinae | Scarabaeinae | subfamily | — | 41142 | Q2412715 | — | 3 |
| scarabaeus-sacer | Scarabaeus sacer | species | 1087226 | 166335 | Q1750802 | 2,000 | 4 |
| sciuridae | Sciuridae | family | 9456 | 55153 | Q9482 | 3,155,518 | 8 |
| serpentes | Serpentes | suborder | 11205692 | 8570 | Q25537662 | 5,490 | 5 |
| simiiformes | Simiiformes | infraorder | — | 314293 | Q5452918 | — | 3 |
| sitta | Sitta | genus | 2484878 | 50248 | Q858577 | 25,747,101 | 7 |
| spheniscidae | Spheniscidae | family | 5284 | 9231 | Q9147 | 1,334,762 | 7 |
| struthio-camelus | Struthio camelus | species | 2495150 | 8801 | Q17592 | 141,937 | 9 |
| tachyeres | Tachyeres | genus | 2498232 | 75880 | Q933654 | 50,968 | 5 |
| talpidae | Talpidae | family | 9469 | 9373 | Q104825 | 523,726 | 8 |
| turdidae | Turdidae | family | 5290 | 9183 | Q26050 | 81,595,391 | 7 |
| ursus-americanus | Ursus americanus | species | 2433407 | 9643 | Q122783 | 66,182 | 10 |
| vertebrata | Vertebrata | subphylum | — | 7742 | Q25241 | — | 3 |
| vespidae | Vespidae | family | 4490 | 7438 | Q7037230 | 1,592,162 | 5 |
| vipera-berus | Vipera berus | species | 5960862 | 31155 | Q192056 | 142,489 | 8 |
