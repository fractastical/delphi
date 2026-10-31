# darwin-origin / ch11-12 — Chapters XI–XII (Geographical Distribution)

Text: `books/darwin-origin/inputs/pg1228.txt` lines 10412–12300. Claims: `darwin1859-ch11-01` … `ch11-17`,
`darwin1859-ch12-01` … `ch12-18` (35 claims). Built 2026-10-31 by a cloud agent
(`cursor/organisms-darwin-ch11-12-9aca`, model `claude-fable-5.1`). No `assessment` fields anywhere.

## Counts

| what | n |
|---|---|
| mentions (`mentions.json`) | 154 (141 located in the text by line range, 13 in claim text) |
| distinct animal taxa (`taxa/`) | 64 (23 species, 12 genera, 9 families, 9 orders, 7 classes, 1 superfamily, 1 infraorder, 1 subphylum, 1 phylum) |
| resolved to GBIF backbone | 61 / 64 |
| resolved to NCBI Taxonomy | 62 / 64 |
| resolved to Wikidata (P225 verified) | 64 / 64 |
| resolved to ITIS | 63 / 64 |
| resolved to WoRMS (molluscs, crustaceans, corals) | 8 / 8 attempted |
| datasets (`datasets/`) | 86 |
| — GBIF occurrence-count records (one per taxon with a GBIF key) | 61 |
| — NCBI genome assemblies (species rank only) | 18 |
| — shared databases (one record each, listing covered taxa) | 7: AnAge build 15 (17 taxa), PanTHERIA 1.0 (11), Amniote Life-History DB 2015 (21), EltonTraits 1.0 (22), AVONET 2022 (11), Paleobiology Database API (15), TimeTree 5 pairwise API (8) |
| claims with at least one taxon linked | 22 of 35 |

Validator: `node organisms/validate.mjs darwin-origin/ch11-12` → 0 errors, 8 warnings (explained below).

## How identifiers were resolved

Every taxon was matched live on 2026-10-31 against GBIF `species/match` (with `kingdom=Animalia` and a
rank hint), NCBI `esearch` with `"name"[Scientific Name]` followed by `esummary` to confirm an exact
scientific-name hit, Wikidata `wbsearchentities` followed by `wbgetentities` and acceptance only when
the entity's P225 (taxon name) equals the queried name, ITIS `searchByScientificName`, and WoRMS
`AphiaIDByName?marine_only=false` for molluscs, crustaceans and corals. The exact query URLs are kept
in each taxon file under `resolution`, together with Wikidata's own GBIF/NCBI/ITIS/WoRMS cross-references
(P846/P685/P815/P850). For all 61 taxa with a GBIF key and all 62 with an NCBI taxid, the Wikidata
cross-reference agrees with the id obtained directly from GBIF/NCBI.

Cases that needed manual handling (all stated in the taxon `notes`):

- **Actinopterygii** ("fish"): `species/match` only returned Animalia; GBIF key 204 was taken from
  Wikidata P846 and verified accepted via `species/204`. The current GBIF backbone no longer files fish
  species under a class, so its occurrence count is 0 (recorded as retrieved).
- **Papilionoidea** ("butterflies"): `species/match` does not search superfamilies; key 1875 taken from
  Wikidata P846, verified accepted. Occurrence count 0 for the same backbone reason.
- **Crustacea**: GBIF backbone has no Crustacea node, and `species/match` returned the homonymous bee
  genus *Crustacea* (Apidae, key 10996236), which was rejected; GBIF null. NCBI merged Crustacea (6657)
  into Pancrustacea (197562), which includes Hexapoda, so NCBI is null. Wikidata Q25364, ITIS 83677,
  WoRMS 1066 resolve.
- **Reptilia**: GBIF 358 is a pro-parte synonym split into Squamata / Testudines / Crocodylia; NCBI has
  no Reptilia node. GBIF and NCBI null; Wikidata Q10811 and ITIS 173747 resolve.
- **Dinornithiformes** (moa, "gigantic wingless birds"): GBIF only has the family Dinornithidae (key
  3242170), no order; GBIF null, NCBI 8808, Wikidata Q452969. ITIS has no record.
- **Brachyura** ("crab"): GBIF files it as a family-rank placeholder (key 11132538) under Decapoda.
- **Gnathodon** → **Rangia**: Darwin's "fossil Gnathodon" is the preoccupied older name of the brackish
  clam genus *Rangia* (WoRMS 156990; *G. cuneatus* = *Rangia cuneata*). Darwin's usage follows the
  older literature, so resolution is to the replacement name.

## Taxa inferred rather than named by Darwin

These are recorded with `notes` saying the identity is inferred, and can be dropped if the merge
step prefers only taxa explicitly named:

- *Rhea pennata* and *Rhea americana* for "one species of Rhea" (Straits of Magellan) and "another
  species of the same genus" (La Plata).
- *Lagidium* for the "alpine species of bizcacha".
- *Leiopelma* for the unnamed "frog ... on the mountains of the great island of New Zealand".
- *Mystacina tuberculata* and *Chalinolobus tuberculatus* for "New Zealand possesses two bats found
  nowhere else in the world".
- *Dusicyon australis* for the Falkland "wolf-like fox"; *Vulpes lagopus* for the "foxes" carried on
  arctic ice (the same mention is also attached to Canidae).
- *Mimus melanotis* and *Mimus trifasciatus* for the mocking-thrushes of Chatham (San Cristóbal) and
  Charles (Floreana) islands; the third unnamed species is left at genus *Mimus*.
- *Perdix perdix* for "partridge" (England; *Alectoris rufa* cannot be excluded), *Coturnix coturnix*
  for "quails crossing the Mediterranean", *Anas platyrhynchos* for "duck", *Columba livia* for
  "pigeon"/"carrier-pigeons", *Equus caballus* for "English racehorses".
- Vernacular groups resolved above species: fishing-eagles → Accipitriformes (sea-eagle or osprey),
  hawks → Accipitridae, owls → Strigiformes, storks → Ciconiidae, pelicans → *Pelecanus*, herons →
  Ardeidae, wading birds → Charadriiformes (Darwin's "Grallatores"; herons and storks also counted as
  waders in 1859 and have their own records), humming-birds → Trochilidae, toads → Bufonidae, newts →
  Salamandridae, "shells"/"sea-shells" → Mollusca, "land-shells"/"fresh-water shells" → Gastropoda,
  "coral" → Scleractinia, "crab" → Brachyura, "butterflies" → Papilionoidea, "beetles" → Coleoptera.

## `mentioned_in` convention

`mentioned_in` lists (a) claims whose text names the taxon (13 claim-sourced mentions), (b) claims
whose quoted lines overlap a text mention, and (c) the claim whose supporting passage contains the
mention, using a fixed passage→claim table (e.g. the Rhea/agouti/bizcacha/coypu passage at lines
10504–10534 illustrates `darwin1859-ch11-03`; the seed-transport experiments with pigeons, turkeys,
hawks, owls, storks, pelicans, partridge and quails at 10860–10977 illustrate `darwin1859-ch11-10`;
the duck/heron/Dyticus/Ancylus/Colymbetes passage illustrates `darwin1859-ch12-03`). The
`mentions.json` entries themselves always carry the exact line range or claim id.

## Validator warnings (8, all intentional)

- `mentioned_in is empty` for **coleoptera, papilionoidea, felidae, equus-caballus, homo-sapiens,
  rangia**: their passages (wide-ranging genera at 12111–12116, racehorses at 10716, "savage races of
  man" at 11483, fossil Gnathodon at 11066) do not correspond to any extracted claim. They have text
  mentions with line ranges.
- `no dataset` for **crustacea** and **reptilia**: no GBIF key (see above) so no occurrence count; both
  are higher taxa with no single genome or trait-database row. Their identifiers (Wikidata, ITIS,
  WoRMS) are still recorded.

## Datasets: what was actually inspected

- **GBIF counts**: `occurrence/count?taxonKey=<key>` response bodies saved, sha256 and byte size
  recorded, `inspected: true`; the `species/<key>` record is listed as a second, uninspected
  distribution used to confirm the key is accepted. `www.gbif.org/species/<key>` returns HTTP 403 to
  non-browser clients, so `integrity.identifier_resolves` was verified via the API record for the same
  key (stated in `checked_via`).
- **NCBI genomes**: `datasets/v2/genome/taxon/<taxid>/dataset_report?filters.reference_only=true`
  inspected for the 23 species; 18 have a reference/representative assembly (11 RefSeq GCF, 7 GenBank
  GCA). The assembly data package itself was not downloaded (`inspected: false`). Species with **no
  assembly in NCBI** (also checked without the reference-only filter): *Helix pomatia*, *Mimus
  trifasciatus*, *Lagostomus maximus*, *Chalinolobus tuberculatus*, *Dusicyon australis*.
- **AnAge build 15**: `dataset.zip` (169,150 bytes) downloaded and unzipped; 4,645 rows; 17 slice
  species present. Absent: *Rhea pennata*, *Mimus melanotis*, *M. trifasciatus*, *Chalinolobus
  tuberculatus*, *Dusicyon australis*, *Helix pomatia*.
- **PanTHERIA 1.0 (WR05)**, **Amniote Life-History DB (Aug 2015)**, **EltonTraits 1.0**: the ESA
  Ecological Archives data files downloaded (2.4 MB, 4.7 MB, 2.2 MB + 0.6 MB) and row-matched on
  binomial; counts in each record. The `esapubs.org` directory pages and Wiley DOI targets answer 403 to
  non-browser clients, so the DOI URL is used as `identifier` and `checked_via` documents the 302 from
  doi.org plus the successful file download.
- **AVONET**: the 21.5 MB figshare xlsx downloaded; sha256 recorded and md5 matches figshare's
  `supplied_md5`. Only `xl/sharedStrings.xml` was parsed (no spreadsheet library), so the record states
  presence of each of the 11 bird species' binomials, not row-level traits.
- **Paleobiology Database**: `occs/list.json?base_name=<taxon>&limit=1&rowcount` for 16 taxa; 15 with
  records_found > 0 are listed (moa 108, *Dusicyon australis* 1, *Rangia* 59, Scleractinia 38,648,
  Brachyura 5,471, Chiroptera 1,707, …). *Helix pomatia* is not in the PBDB taxonomy (0 records).
- **TimeTree 5**: pairwise API for *Rhea pennata*/*R. americana* (11.4 Ma), *Mystacina tuberculata*/
  *Chalinolobus tuberculatus* (51.4 Ma), *Dusicyon australis*/*Vulpes lagopus* (12.7 Ma), *Struthio
  camelus*/*Rhea americana* (65.5 Ma), *Dromaius*/*Rhea americana* (63.8 Ma). The *Mimus melanotis*/
  *M. trifasciatus* query was rejected by the API ("are the same").

Nothing over 1 MB is committed; the downloaded files live only in `/tmp` and are described by URL,
byte size and sha256.

## Shared databases not recorded, and why

- **IUCN Red List**: the API requires a token and `apiv3.iucnredlist.org` redirects are behind a
  Cloudflare challenge (HTTP 403), so no assessment ids could be retrieved without guessing. Wikidata
  P627 ids exist for most species and could be used by a later pass.
- **BOLD**: `v4.boldsystems.org/index.php/API_Public/stats` returned HTTP 403 (the legacy host 301s
  to it). Not recorded.
- **FishBase**: no species-rank fish in the slice (Darwin's "fish" is resolved to Actinopterygii).
- **MorphoSource / Phenome10K, Open Tree of Life**: not queried in this pass.

## Taxa with no usable dataset

- **Crustacea**, **Reptilia** — see validator warnings. Everything else has at least a GBIF occurrence
  count; *Dusicyon australis* additionally has PBDB, PanTHERIA, Amniote DB, EltonTraits and TimeTree
  rows despite having no genome.

## Non-animal taxa seen (not built)

Plants: hazel (*Corylus*), asparagus, *Helosciadium*, oak (*Quercus*, "about 50 years old"), peas,
vetches, oat, wheat, millet, canary-grass, hemp, clover, beet, vine, maize, duck-weed (*Lemna*),
yellow water-lily (*Nuphar*), *Potamogeton*, *Nelumbium* / *Nelumbium luteum* (now *Nelumbo lutea*),
flowering plants of Tierra del Fuego / New Zealand / Galapagos (Hooker), ferns, "dicotyledonous
plants", hooked-seeded endemic island plants, insular trees derived from herbaceous orders, seaweed.
Algae: "twenty-five species of Algæ common to New Zealand and Europe". No fungi or microbes are named.

## Ambiguities worth a second look

- "fish" everywhere is paraphyletic; Actinopterygii excludes sharks and rays that Darwin's marine
  faunas would include. GBIF gives 0 occurrences for the class key (backbone structure), so the GBIF
  record for Actinopterygii is provenance only, not a usable count.
- "frozen mammals" of Siberia (line 11202) are almost certainly mammoths, but Darwin does not say so;
  left at Mammalia.
- "blind animals inhabiting the caves of America and of Europe" (line 12095) are not resolved to a
  taxon (cave fauna is treated in Chapter V).
- "two North American species [of bat] ... visit Bermuda" (line 11828) are unnamed; left at Chiroptera.
- The frogs introduced to Madeira, the Azores and Mauritius (line 11789) are left at Anura.
- *Mimus trifasciatus* is extirpated from Floreana itself and survives only on Champion and Gardner
  islets, so its 1,445 GBIF occurrences are mostly from those islets.
- Darwin's "Rodents" (line 10520) include hares and rabbits, which are now Lagomorpha; the mention is
  kept under Rodentia as written, with *Lepus* and *Oryctolagus cuniculus* resolved separately.
