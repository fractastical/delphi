# Organisms: Thompson, *On Growth and Form* (1917), Chapters VI–VII

Slice `ch06-07`: Chapter VI (A Note on Adsorption) and Chapter VII (The Forms of Tissues, or
Cell-aggregates), lines 9882–12091 of `books/thompson-growth-form/inputs/pg55264.txt`, plus the 25 claims
`thompson1917-ch06-*` and `thompson1917-ch07-*` in `books/thompson-growth-form/claims.json`.

Built 2026-10-31 by a cloud agent (`vendored_by.run` = `cursor/thompson-ch06-07-organisms-6681`).
No `assessment` fields were written.

## Counts

| | |
|---|---|
| Mentions (`mentions.json`) | 84 (69 located in the book text by line range, 15 in claim text/scope) |
| Claims with an animal mention | 6: ch06-02, ch07-09, ch07-10, ch07-11, ch07-12, ch07-15 |
| Distinct animal taxa (`taxa/`) | 44 (7 species, 22 genera, 2 families, 3 orders, 1 suborder, 3 classes, 1 subphylum, 4 phyla, 1 clade) |
| Resolved to GBIF backbone `usageKey` | 40 / 44 |
| Resolved to NCBI Taxonomy id | 30 / 44 (the 14 misses are all extinct corals/bryozoan absent from NCBI) |
| Resolved to Wikidata QID (P225 checked) | 38 / 44 |
| Resolved to WoRMS AphiaID | 17 / 44 (marine extant taxa only; fossil genera are not in WoRMS) |
| Resolved to Paleobiology Database taxon id | 21 / 44 (recorded as `identifiers.pbdb_taxon_id`) |
| Taxa with at least one identifier | 44 / 44 |
| Datasets (`datasets/`) | 56: 41 GBIF occurrence-count records, 11 NCBI genome assemblies, and 4 shared records (GBIF Backbone Taxonomy, NCBI Taxonomy, Paleobiology Database, AnAge build 15) plus 1 FishBase species page |
| Taxa with no dataset | 0 |

Validator: `node organisms/validate.mjs thompson-growth-form/ch06-07` → 0 errors, 0 warnings.

## How taxa were resolved

- GBIF `species/match?verbose=true`; where the plain match returned `NONE` because of homonyms
  (Anura, Diptera, Arachnophyllum, Crepidula, Asterina, Trochus) the query was repeated with
  `kingdom=Animalia&rank=…` or the accepted animal usage was taken from the verbose alternatives
  and confirmed with `species/{key}`. Lineage comes from `species/{key}` (phylum/class/order/
  family), supplemented by PBDB classification for fossil genera.
- NCBI E-utilities `esearch` + `esummary`; homonyms (Anthophila the moth genus, Asterina the
  fungus, Vertebrata the alga, Bombus the subgenus, Rugosa the frog genus) were separated by
  rank/division in the esummary.
- Wikidata `wbsearchentities` + `wbgetentities` (P225 taxon name, P846 GBIF id, P685 NCBI id)
  to confirm each QID is the taxon, not a homonym (e.g. Q4810669 fungus vs Q2868401 starfish
  Asterina). Wikidata rate-limited the first pass; it was re-run at one request per 2 s.
- WoRMS `AphiaIDByName` (and `AphiaRecordsByName` where it returned −999) for marine taxa.
- All raw API responses were saved and checksummed outside the repo; only the small
  occurrence-count, dataset-report and esummary bodies are referenced (by URL, size and sha256)
  in the dataset records. Nothing over 1 MB was downloaded; the only bulk file inspected was the
  AnAge zip (169,150 bytes), not committed.

## Datasets

- **GBIF occurrence counts** (`gbif-occurrences-<slug>-2026-10-31`): one per taxon with a GBIF
  key; the count is the `/occurrence/count?taxonKey=` response at retrieval time and includes
  descendant taxa. Landing pages on `www.gbif.org` returned **HTTP 403** to the non-browser client,
  recorded in `integrity.http_status`; the API URL returned 200 and is checksummed.
- **NCBI genome assemblies** (`ncbi-genome-<accession>`): the NCBI Datasets reference assembly
  for *Apis mellifera* (GCF_003254395.2), and for genus/family-level taxa a reference assembly of a
  representative species, stated in `role`: *Scyliorhinus canicula*, *Hydractinia
  symbiolongicarpus*, *Podocoryna americana*, *Heliopora coerulea*, *Asterina phylactica*,
  *Melipona quadrifasciata*, *Vespa crabro*, *Unio pictorum*, *Bombus terrestris*, *Oculina
  patagonica*. No genome exists in NCBI Datasets for *Crepidula* (any species, including
  *C. fornicata*), *Trochus* or *Branchipus* (checked without the reference-only filter). No genome
  record was made for phylum/class/order-level taxa (Porifera, Mollusca, Anura, …) because a single
  species' assembly would not represent them; the NCBI Datasets totals for those taxa are in the
  saved responses but not vendored.
- **Paleobiology Database** (`pbdb-taxa-2026-10-31`): one shared record with the `taxa/single`
  response for each of 21 taxa (all fossil corals, *Monticulipora*, Rugosa, Oculinidae, Heliopora
  and the higher taxa Porifera, Mollusca, Annelida, Cnidaria, Anthozoa); occurrence counts and
  first/last appearance are in `counts`. PBDB flags Rugosa `ext=1`, which is wrong for an extinct
  order but is recorded as returned.
- **AnAge build 15** (`anage-build-15`): zip downloaded and inspected; rows found for *Apis
  mellifera* (HAGRID 00015), *Bombus terrestris* (00016), *Scyliorhinus canicula* (01772) and
  *S. stellaris* (01773). `anage_data.txt` has 4,646 data rows; the release notes say 4,671
  entries.
- **FishBase** (`fishbase-scyliorhinus-canicula-2026-10-31`): species summary page for the
  small-spotted catshark, retrieved with a browser-like user agent (the ropensci FishBase API did
  not respond). The page is dynamic so the checksum documents only the copy retrieved.
- **GBIF Backbone Taxonomy** and **NCBI Taxonomy**: one shared record each listing every taxon
  matched, with the dataset metadata / combined esummary response as the checksummed distribution.
- Not used: **BOLD** (v4 public API returned HTTP 403), **IUCN Red List** (API requires a token;
  *Heliopora coerulea* and *Scyliorhinus canicula* are assessed there), **TimeTree**, **MorphoSource**,
  **Open Tree of Life** (not attempted for lack of time), **PanTHERIA / AVONET / Amniote LHD /
  EltonTraits** (no mammal, bird or reptile is named below suborder level in this slice).

## Taxa with weak or indirect data

- `anthophila` (bees in general), `ruminantia`, `vertebrata`: not in the GBIF backbone (no clade /
  suborder / subphylum ranks), so no GBIF occurrence count; covered only by the NCBI Taxonomy
  shared record. GBIF's exact match for "Anthophila" (5123443) is a choreutid **moth** genus and
  was deliberately not used.
- `rugosa`: no GBIF, NCBI or WoRMS record (all three "Rugosa" hits are a leafhopper or a frog
  genus); resolved by Wikidata Q133091 and PBDB txn:5113 only.
- Extinct corals (`favosites-gothlandicus`, `lithostrotion`, `lithostrotion-martini`,
  `cyathophyllum`, `thecosmilia`, `arachnophyllum`, `arachnophyllum-pentagonum`, `heliolites`,
  `synhelia`, `phillipsastrea`, `thamnasteria`, `comoseris`) and the bryozoan `monticulipora`: no
  NCBI or WoRMS ids; data are GBIF fossil occurrence counts and PBDB.
- `cyathophyllum`: Thompson's *Cyathophyllum hexagonum* has no species record in GBIF or PBDB, so
  the binomial is recorded at genus level.
- No Wikidata item found for *Favosites gothlandicus*, *Siphonodendron martini*, *Strombodes
  pentagonus*, *Arachnophyllum* Dana (only the alga homonym exists), *Phillipsastrea* (either
  spelling) or *Comoseris*.

## Ambiguities and decisions

- **"frog"** (Fig. 97 C, Fig. 117, "frog's egg"): resolved to order Anura. Rauber's and Mathews'
  material was *Rana*, but Thompson does not say so.
- **"Ascidians"**, **"Mollusca"**, **"molluscs"**, **"annelids"**, **"coelenterates"**,
  **"vertebrates"**: resolved to class/phylum/subphylum. "Worms" (line 12006) was mapped to
  Annelida because the preceding Wilson quotation pairs molluscs with annelids; strictly it is vaguer.
  "Coelenterates" in 1917 could include ctenophores; mapped to Cnidaria.
- **Honey-comb / bee's cell / hive-bee / "the bees" (Pappus)**: *Apis mellifera*. **"humble-bees"**:
  *Bombus*. **"solitary wasps and bees"**, **"many bees"**, Buffon's **"abeilles"**: bee clade
  Anthophila. **"social wasps"**, **"the wasp"**, Buffon's **"guêpes"**: family Vespidae (the
  comb-building paper wasps); "solitary wasps" is broader than Vespidae and is listed there with a
  caveat. Buffon's **"frélons"** (hornets): *Vespa*. Buffon's **"mouches"** ("on donne plus d'esprit
  aux mouches dont les ouvrages sont les plus réguliers") is 18th-century generic usage for
  insects, not Diptera, and was not recorded as a separate mention.
- **"Melipona domestica"** (Huber via Darwin): not an available name in any authority; resolved
  to genus *Melipona*.
- **Buffon's "roussette"** (hexagonal skin scales): the French name of the catsharks; resolved to
  genus *Scyliorhinus*. **"animaux ruminans"** (hexagonal cells of the second stomach, i.e. the
  reticulum): Ruminantia.
- **Thompson's coral names**: *Favosites gothlandica* → *Favosites gothlandicus* Lamarck, 1816;
  *Lithostrotion Martini* → GBIF-accepted *Siphonodendron martini*; *Arachnophyllum pentagonum* →
  GBIF-accepted *Strombodes pentagonus*; *Thamnastraea* → *Thamnasteria* Le Sauvage, 1823;
  *Phillipsastraea* → *Phillipsastrea* d'Orbigny, 1849; *Podocoryne* → *Podocoryna*. The genus
  *Favosites* itself is not recorded as a separate taxon because the text names only the species.
- **"Monticuliporae"**: Thompson lists them among corals; *Monticulipora* is now a trepostome
  bryozoan. Kept (it is an animal) with a note.
- **"(Fungida)"**: Thompson's order for *Thamnastraea*. There is no GBIF, NCBI or Wikidata taxon
  "Fungiida" (Wikidata only has the family Fungiidae, which is not the same), and *Thamnasteria*
  is now placed in Thamnasteriidae, so Fungiida was **not** recorded as a taxon; it is noted on
  `thamnasteria`.
- **"Oculinidae"** and **"Rugosa"** are recorded as taxa in their own right because Thompson names
  them explicitly (as the groups of *Synhelia* and *Phillipsastraea*).
- **"polypes", "polypite", "zooids"**: generic coral-polyp terms, folded into `anthozoa`.
- **"Girardia"** (Fig. 124, "Epidermis of Girardia (After Goebel)"): the figure comes from the
  botanist K. Goebel and the passage concerns plant epidermis, so this is almost certainly a plant
  name (the planarian genus *Girardia* Ball, 1974 did not exist in 1917). Listed under non-animals
  below; not resolved.
- **"white of egg"** (Melsens's artificial tissue, line 11844) is a material, not an organism
  mention; not recorded.
- Claim-scoped mentions use the claim's `claim` or `scope` text as the quote (prefixed "scope:"
  where it is the scope field), since the verbatim `quote` fields of those claims do not name the
  taxon.

## Non-animal taxa seen (not built)

Protists: protozoan/"ectosarc" (10044), Foraminifer (10056), Radiolaria (10058; also claim
ch06-02 scope), Amoeba (10249), Vorticella (10335), "ciliate or flagellate cells" (10328),
Heliozoan (10429), diatoms (11369, 11390), Arcella (11370).
Bacteria: "zoogloea around a group of bacteria" (10051–10052).
Fungi: yeast-cell (10229), Mucor (10763).
Algae / cyanobacteria: Spirogyra (10230, 10339), Pleurocarpus (10289), Mesocarpus (10296),
Protococcus (10671), Nostoc (10669, 10673, 11063), Anabaena (10669), Rivularia (10669),
Oscillatoria (10670, 10674), Florideae (10743), *Dictyota dichotoma* (10744), Chara (10750–10762),
Laminaria (11114).
Plants: Equisetum (10314–10316), *Pellia* / Liverworts (10721–10723), Maize (10610), Girardia
(11293, 11320; see above), *Elodea canadensis* (11336), hyacinth / Monocotyledon (11343),
dicotyledonous leaf (11339), *Juncus effusus* (11762), banana (11763), pomegranate (11536), peas
and cylindrical seeds in Buffon's quotation (11736–11737), pollen-grains (11031), "higher plants"
parenchyma.
Claims ch06-03, ch06-04, ch06-07, ch06-08, ch07-02, ch07-03, ch07-07 and ch07-13 have only
protist/plant/algal scopes and therefore contribute no animal mention.
