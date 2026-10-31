# Organisms in *On Growth and Form* (1917), Chapters I–II (Introductory; On Magnitude)

Slice `thompson-growth-form/ch01-02`: lines 980–2579 of `thompson-growth-form/inputs/pg55264.txt`
and claims `thompson1917-ch01-01` … `thompson1917-ch02-18` (27 claims) in `thompson-growth-form/claims.json`.
Built 2026-10-31 by a cloud agent (branch `cursor/organisms-thompson-ch01-02-efbc`); all identifiers
and counts were retrieved live from the APIs named below on that date. Nothing here is scored.

## Counts

| | |
|---|---|
| Mentions (`mentions.json`) | 80 (32 attributed to a claim, 48 to text lines outside the claim quotes) |
| Distinct animal taxa (`taxa/`) | 37 |
| Resolved to GBIF backbone `usageKey` | 33 / 37 |
| Resolved to NCBI Taxonomy id | 35 / 37 |
| Resolved to Wikidata QID (P225 taxon name checked on the entity) | 37 / 37 |
| Resolved to ITIS TSN | 32 / 37 |
| Resolved to WoRMS AphiaID (marine or `marine_only=false`) | 10 / 37 |
| Dataset records (`datasets/`) | 53 |
| of which GBIF occurrence-count queries (one per taxon) | 33 |
| of which NCBI genome assemblies (one per taxon) | 12 |
| of which shared databases (one record per slice) | 8: AnAge build 15, PanTHERIA 1.0, Amniote Life-History DB (2015), EltonTraits 1.0, Paleobiology Database, AVONET, FishBase, GBIF Backbone Taxonomy |
| Distributions with a saved response body, byte size and sha256 (`inspected: true`) | 59 |
| Distributions recorded by URL only (`inspected: false`) | 47 (34 GBIF backbone name-usage URLs, 12 NCBI FASTA package URLs, AVONET xlsx, FishBase page) |
| Claims with at least one taxon mention | 13: ch02-01, 03, 04, 05, 06, 07, 08, 09, 11, 12, 14, 16, 17 |

Rank distribution of the 37 taxa: 9 species, 5 genera, 8 families, 8 orders (incl. one clade and two
suborders counted here), 7 classes/subclasses/phylum.

Files vendored: none over 1 MB (whole slice 0.45 MB). Trait-database files were downloaded to `/tmp`,
inspected with `awk`, checksummed with `sha256sum`, and not committed; only the checksum, size, row counts
and retrieval time are recorded.

## How names were resolved

- GBIF `species/match?name=…&verbose=true`; where the match was `NONE` because of homonyms
  (Siphonaptera, Diptera, Crepidula) the query was repeated with `kingdom=Animalia`. Where the backbone
  lacks the rank (see below) the key is `null`; `species/<key>` was used to confirm Actinopterygii (204),
  Squamata (11592253 vs the stale order-level 715) and Mus musculus (7429082; Wikidata's P846 value
  2438780 is a synonym).
- NCBI `esearch.fcgi?db=taxonomy` followed by `esummary` to confirm scientific name and rank.
- Wikidata `wbsearchentities` then `wbgetentities` (`P225`, `P105`, `P846`, `P685`) to confirm the hit is
  the taxon item, not a concept item (e.g. Q15978631 *Homo sapiens* rather than Q5 "human";
  Q19610691 *Bos taurus* rather than Q830 "cattle").
- ITIS `searchByScientificName`; for Siphonaptera the valid TSN 152732 was chosen over the invalid
  duplicate 152733 via `getFullRecordFromTSN`.
- WoRMS `AphiaIDByName/<name>?marine_only=false` for molluscs, echinoderms, fishes, cetaceans, rotifers
  and (non-marine) *Apis*.

## Vernacular and archaic names, and how they were read

| As written | Resolved to | Rank | Comment |
|---|---|---|---|
| honey-comb, bee | *Apis* | genus | hive-bee implied; species not named |
| snail | Gastropoda | class | |
| nautilus | *Nautilus* | genus | |
| fish, the larger fish | Actinopterygii | class | "fish" is paraphyletic; bony fishes intended (length–weight, Froude's law) |
| bull's | *Bos taurus* | species | |
| elephant | Elephantidae | family | African vs Asian never specified |
| whale | Cetacea | order (GBIF/ITIS) / infraorder (NCBI) | |
| giant reptiles of our secondary rocks | Dinosauria | clade | ambiguous, see below |
| ostrich | *Struthio camelus* | species | single species in 1917 (incl. the later-split Somali ostrich) |
| sparrow | *Passer domesticus* | species | British usage; a genus-level reading (*Passer*) is possible |
| swift | *Apus apus* | species | British usage, speed estimate 20–50 ft/s |
| humming-birds | Trochilidae | family | |
| moa | Dinornithiformes | order | GBIF only has family Dinornithidae (3242170), used for the occurrence count |
| giant dragon-flies (carboniferous) | Meganisoptera | order (extinct) | not true Odonata; GBIF also has *Meganeura* 4682601 |
| fossil pterodactyles | Pterosauria | order (extinct) | |
| cockchafer | *Melolontha* | genus | *M. melolontha* in Britain |
| flea | Siphonaptera | order | |
| stag-beetle | Lucanidae | family | Linnaeus's *Lucanus cervus* |
| horse | *Equus caballus* | species | |
| grasshopper | Caelifera | suborder | |
| mouse | *Mus musculus* | species | Hardesty's ganglion-cell figure; Plateau's walking comparison |
| tortoise | Testudinidae | family | |
| minute fly, flies, gnats | Diptera | order | "gnats" could be narrowed to Nematocera |
| short-legged saurians | Squamata | order (class in GBIF) | "saurians" = lizards, a paraphyletic group absent from GBIF/NCBI |
| serpents | Serpentes | suborder | GBIF key is a family-ranked stub, see below |
| the shark's gut | Elasmobranchii | subclass (class in GBIF) | |
| sea-urchin larvae | Echinoidea | class | Driesch's *Echinus*/*Sphaerechinus* |
| Crepidula, slipper-limpet | *Crepidula* | genus | Conklin's species is *C. fornicata* |
| oyster-beds | Ostreidae | family | indirect mention |
| the Rotifera | Rotifera | phylum | |
| the rabbit | *Oryctolagus cuniculus* | species | host of *Micrococcus progrediens* |
| man, human blood-corpuscle, our own bodies, our bipedal form | *Homo sapiens* | species | |
| birds, nesting bird, flying bird, larger/heavier/very small birds | Aves | class | |
| insects, the insect | Insecta | class | |
| large mammal, smaller mammals, various mammals | Mammalia | class | |
| ant-hill | Formicidae | family | indirect |
| spider's web | Araneae | order | indirect |

## Taxa not fully resolved

| Taxon | GBIF | NCBI | Wikidata | ITIS | Why |
|---|---|---|---|---|---|
| Dinosauria | null | 436486 | Q430 | null | GBIF backbone has no Dinosauria node (`match` → NONE; `search` finds only unrelated names); ITIS has no record |
| Pterosauria | null | null | Q179204 | null | not in GBIF backbone; NCBI Taxonomy has no entry for this extinct order; ITIS none. Only Wikidata and PBDB |
| Dinornithiformes | null (family Dinornithidae = 3242170) | 8808 | Q452969 | null | GBIF has the family but not the order; ITIS none |
| Meganisoptera | 9714023 | null | Q164689 | null | extinct order, no NCBI entry (no sequence data); ITIS none |
| Caelifera | null | 7001 | Q83902 | 102161 | GBIF backbone has no suborder rank; containing order Orthoptera is key 1458 |
| *Melolontha* | 4990942 | 7060 | Q1780303 | null | ITIS does not list the genus |
| Actinopterygii | 204 (0 occurrences) | 7898 | Q127282 | 161061 | GBIF `match` returns NONE, but `species/204` is an accepted CLASS record; current occurrences are indexed under fish orders, so no GBIF count record was made |
| Serpentes | 11205692 (stub) | 8570 | Q25537662 | 174118 | GBIF record is ranked FAMILY, has 0 descendants and only 5,490 attached occurrences; it is kept because it is the only "Serpentes" in the backbone, with the caveat in the notes |

## Taxa with no or weak dataset coverage

- **Caelifera** (grasshopper): no dataset. No GBIF key, no genome query made at suborder level, no rows in
  the trait databases inspected; the only trait-relevant data would be jumping-performance literature.
  Validator warning `no dataset` is expected.
- **Pterosauria** and **Dinosauria**: only the Paleobiology Database occurrence count (1,162 and 37,899
  records). No GBIF or NCBI resources exist for them.
- **Dinornithiformes**: PBDB (108 occurrences) and the GBIF count for Dinornithidae (879 occurrences).
- **Meganisoptera**: GBIF count (143) and PBDB (97); no NCBI resources.
- **Siphonaptera, Serpentes, Rotifera, Lucanidae**: GBIF count plus GBIF backbone record only; AnAge has
  no rows for these groups, and genomes were not recorded for taxa above genus rank (see below).
- **Crepidula**: GBIF, PBDB and backbone; NCBI Datasets returned no assembly for taxid 52628
  (`total_count` null) at retrieval time, so no genome record.

Genome assemblies were recorded only for taxa resolved to species or genus (12 records). For genera the
reference-genome query returns member species: *Apis mellifera* Amel_HAv3.1 for *Apis*, *Nautilus
pompilius* for *Nautilus*, *Melolontha melolontha* icMelMelo1.2 for *Melolontha*; for Elephantidae the
*Loxodonta africana* mLoxAfr1.hap2 reference was recorded (the query also returned *Elephas maximus
indicus* GCF_024166365.1, not vendored). Each such record carries a `notes` field saying so. Family- and
higher-rank taxa (Trochilidae 14 assemblies, Lucanidae 9, Testudinidae 8, Ostreidae 17, Formicidae 216
returned by the API) were not given genome records because no single assembly represents Thompson's
mention.

Datasets considered but not recorded:
- **BOLD** (`v4.boldsystems.org/index.php/API_Public/stats`) returned HTTP 403 from this environment.
- **IUCN Red List** API requires a token; no record made.
- **MorphoSource** API requires a key; the 3D bone scans relevant to claim ch02-03 could be added later.
- **TimeTree / Open Tree of Life**: not needed for these claims.
- **Metabolic-rate compilations** beyond AnAge/PanTHERIA BMR columns (e.g. AnimalTraits, White & Seymour)
  were not vendored.

## Shared-database coverage (rows inspected)

- **AnAge build 15** (`anage_data.txt`, 4,646 data rows; release notes say 4,671 entries): rows for all 9
  species-level taxa, plus Elephantidae 2, Cetacea 46, Testudinidae 22, Trochilidae 15, Echinoidea 2,
  Ostreidae 4, Formicidae 3, Araneae 1, Diptera 3, Squamata 404, Elasmobranchii 114 (Chondrichthyes minus
  3 Chimaeriformes), Actinopterygii 829 (Teleostei + Chondrostei + Holostei + Cladistei + "Actinopterygii"
  class labels), Insecta 13, Gastropoda 1. AnAge's *Apis mellifera* row has longevity but no body mass.
- **PanTHERIA 1.0** (5,416 rows): the 5 mammal species, Elephantidae 3, Cetacea 84.
- **Amniote Life-History Database** (21,322 rows): the 8 amniote species, Elephantidae 3, Cetacea 82,
  Testudinidae 52, Trochilidae 311, Squamata 6,271.
- **EltonTraits 1.0** (10,205 bird rows, 5,403 mammal rows): ostrich 111,000 g, swift 37.6 g, house sparrow
  26.51 g, Trochilidae 334 rows; the 5 mammal species, Elephantidae 3, 14 cetacean families 84 rows.
- **Paleobiology Database** (`occs/list.json?base_name=…&rowcount=true`): Dinosauria 37,899; Pterosauria
  1,162; Meganisoptera 97; Dinornithiformes 108; Elephantidae 1,599; Cetacea 6,294; *Nautilus* 110;
  *Crepidula* 1,192; Echinoidea 11,662.
- **AVONET** and **FishBase**: pointer records only (`inspected: false`); AVONET metadata (title, DOI
  10.6084/m9.figshare.16586228.v7, CC BY 4.0, file size 21,524,673 bytes) was read from the figshare API
  but the xlsx was not downloaded. FishBase has no bulk endpoint reachable here.

## Non-animal taxa seen (not built)

Protists: *Amoeba* (claims ch01-06, ch01-07; lines 1331–1389), Foraminifera (1030, 2430), Radiolaria
(1030), *Micromonas mesnili* (2197, a flagellate), *Paramoecium* / Infusoria (2511, 2520, 2523),
diatoms (2430), "protozoa" (2535), "monad" (2554).
Algae / plants: *Spirogyra* (1331), *Protococcus* (1389), the Kew-flagstaff British Columbian pine
(1585; claim ch02-02), trees generally, melons and pumpkins (1549), fruit stalks, apple (1156), grapes
(1207), tobacco plant (2208), pollen grain (2442), *Bäume* in the Goethe quotation.
Bacteria: *Micrococcus progrediens* (claim ch02-18; 2199, 2217, 2278), *Bacillus anthracis* (2216),
Micrococci, "bacteria" and their spores, *Spirillum* (2475), *Spirochaete pallida* (2484, = *Treponema
pallidum*).
Viruses (as diseases): hydrophobia, foot-and-mouth disease, tobacco mosaic (2207–2208).
Fungi: none noticed.

## Ambiguities and judgement calls

- **"giant reptiles of our secondary rocks"** (line 1638), said to have been partly immersed in water:
  resolved to Dinosauria (the large, then-thought amphibious sauropods) rather than to Mesozoic marine
  reptiles (ichthyosaurs, plesiosaurs) or Reptilia at large. Reptilia itself cannot be a GBIF taxon: the
  backbone treats it as a pro-parte synonym split across Squamata, Testudines, Crocodylia and
  Sphenodontia.
- **"quadrupeds"**, **"Herbivore"**, **"higher animals"**, **"terrestrial animals"**, **"aquatic
  animals"** are not taxa and were not recorded.
- **"sparrow"** and **"swift"** were taken to species (*Passer domesticus*, *Apus apus*) on the strength of
  British usage; **"mouse"** to *Mus musculus*. If merging later prefers genera, the genus keys were not
  verified here.
- **"fish"** → Actinopterygii: FishBase (the natural test data for claim ch02-01) also covers
  Elasmobranchii, which is why the FishBase record lists both.
- **Mentions attributed to claims**: a mention is attributed to a claim when the taxon appears in the
  claim's quoted passage or the sentence that the claim summarises (e.g. the elephant sentence at 1632
  for claim ch02-03, the Rotifera paragraph for ch02-17). Everything else is attributed to file lines.
  Taxa mentioned only in chapter I or in non-claim passages therefore have an empty `mentioned_in`, which
  the validator reports as 17 warnings.
- **Footnote and page markers** (`[42]`, `{19}`) are kept inside quotes because the quotes are verbatim
  from the Gutenberg text.
- **GBIF count for *Homo sapiens*** (24,173) is recorded for completeness; it is not a meaningful
  distribution dataset and the record's notes say so.
- Datasets carry a `notes` field (not in the README template) where a caveat was needed; `counts`
  entries for shared databases carry an extra `taxon` field tying each row count to a slug.

## Validator

`node organisms/validate.mjs thompson-growth-form/ch01-02` → 0 errors, 18 warnings: 17 `mentioned_in is
empty` (taxa mentioned only outside claim passages, see above) and 1 `no dataset` (Caelifera).
