# Organism reference data: `thompson-growth-form` / `ch15-epilogue`

Slice: D'Arcy Thompson, *On Growth and Form* (1917), Chapters XV–XVII and the Epilogue.
Text: `claim-sources/thompson-growth-form/inputs/pg55264.txt`, main text lines 21575–25434 and the
footnotes belonging to these chapters, lines 28405–28917 (footnotes [586]–[663]).
Claims: the 54 entries in `claim-sources/thompson-growth-form/claims.json` whose ids begin
`thompson1917-ch15-`, `-ch16-`, `-ch17-` or `-epilogue-`.

All records were built on 2026-10-31 from live API queries (GBIF, NCBI E-utilities, NCBI
Datasets, Wikidata, WoRMS, OBIS, PBDB, MorphoSource, figshare, FishBase) and from downloaded
copies of the shared trait databases listed below. Every count, accession, checksum and byte
size in the records was read from an actual response or file; nothing was typed in by hand.
No file in this slice exceeds 1 MB and no record carries an `assessment` field.

## Counts

| quantity | value |
| --- | ---: |
| mentions (`mentions.json`) | 692 |
| of which sourced from claims | 61 |
| of which sourced from text lines | 631 |
| distinct claim ids with at least one mention | 21 |
| distinct animal taxa (`taxa/`) | 201 |
| datasets (`datasets/`) | 375 |

Taxa by rank: species 73, subspecies 2, genus 64, subfamily 2, family 29, superfamily 1,
infraorder 4, parvorder 1, suborder 1, order 14, superorder 1, infraclass 1, subclass 1,
class 3, subphylum 1, phylum 1, clade 2.

### Resolution to authorities (of 201 taxa)

| authority | resolved | null |
| --- | ---: | ---: |
| GBIF backbone `usageKey` | 186 | 15 |
| NCBI Taxonomy id | 155 | 46 |
| Wikidata QID (P225 verified) | 196 | 5 |
| WoRMS AphiaID (marine taxa only) | 81 | — |
| PBDB `taxon_no` (extinct taxa only) | 55 of 55 | 0 |
| ITIS TSN | 0 | not queried |

Every taxon has at least one of GBIF / NCBI / Wikidata / WoRMS; five (`acanthopterygii`,
`creodonta`, `pterosauria`, `sauropoda`, `sterninae`) are held only by Wikidata (plus PBDB for
the three fossil clades).

GBIF null (15): `acanthopterygii`, `antilopinae`, `creodonta`, `crustacea`, `dinosauria`,
`majoidea`, `nautiloidea`, `odontoceti`, `pinnipedia`, `plesiosauria`, `pterosauria`,
`sauropoda`, `selachii`, `sterninae`, `vermilingua`. The current GBIF backbone has no usage
for these supra-generic names (or only a fuzzy match to an unrelated genus, which was
rejected: Dinosauria → *Cyrtodactylus*, Antilopinae → Bovidae, Sterninae → Laridae,
Pinnipedia → Phocidae, Crustacea → an insect genus). The exact match-service response is
quoted in each taxon's `notes`.

Wikidata null (5): `calippus-placidus`, `diceratherium-tridactylum`, `ellipsolithes`,
`hyrachyus-agrarius`, `macrorhynchia-ramulosa` — no item whose P225 equals the accepted name.

NCBI null (46): mostly extinct taxa with no NCBI Taxonomy record, plus three cases where
esearch returned only an unrelated homonym (`Gonothyraea hyalina` → *Hyalina*,
`Harpinia plumosa` → *Plumosa*, `Psiloceras planorbis` → *Planorbis*); those ids were
rejected rather than recorded.

### Datasets by kind (375)

| kind | records | notes |
| --- | ---: | --- |
| GBIF occurrence count (`gbif-occurrences-*`) | 185 | one per taxon with a GBIF key and a non-zero count; `www.gbif.org` landing page returned HTTP 403 to the non-browser client, recorded in `integrity` |
| OBIS occurrence count (`obis-occurrences-*`) | 79 | marine taxa with a WoRMS AphiaID and a non-zero OBIS count |
| PBDB occurrence count (`pbdb-occurrences-*`) | 55 | all extinct taxa; identifier is the data-service URL, classic landing page gave HTTP 403 (recorded) |
| NCBI Datasets reference genome (`ncbi-genome-*`) | 50 | extant species/subspecies with a reference assembly; the `dataset_report` JSON was saved and hashed, the genome download URL is recorded with `inspected: false` |
| shared trait databases | 6 | one record per database per slice, see below |

Shared records and the number of slice taxa each covers (membership was checked by name in
the downloaded file or the live API, never assumed):

| record | taxa | file inspected |
| --- | ---: | --- |
| `anage-build-15` | 40 | `anage-dataset.zip`, 169150 B, sha256 recorded |
| `amniote-life-history-database-2015` | 35 | `Amniote_Database_Aug_2015.csv`, 4728122 B |
| `pantheria-1-0-wr05-2008` | 19 | `PanTHERIA_1-0_WR05_Aug2008.txt`, 2359096 B |
| `avonet-2022-figshare-v7` | 11 | `AVONET_Supplementary_dataset_1.xlsx`, 21524673 B (md5 matches figshare) |
| `fishbase-2026-10` | 10 | species summary pages fetched and title-checked; FishBase has no versioned bulk file, so the record is dated by month |
| `morphosource-physical-objects-2026-10-31` | 13 | MorphoSource public API, `taxonomy_name` facet exact hits |

None of the large downloaded files is committed; only their size, checksum, URL and
retrieval time are recorded in the dataset `distributions`.

Not used: BOLD (public API returned HTTP 403 to every request), TimeTree and IUCN Red List
(require API tokens that are not available in this environment), ITIS (not queried).

## Taxa with no dataset (4)

`acanthopterygii`, `antilopinae`, `sterninae`, `vermilingua`: no GBIF key (so no occurrence
count), above species level (so no genome or trait-database entry), not marine and not
extinct. They are kept as taxon records because the text names them explicitly.

Zero-count queries that were therefore *not* written as dataset records:

- `gbif-occurrences-ellipsolithes`: GBIF reports 0 occurrences for taxonKey 7712376.
- `obis-occurrences-cladocarpus-crenatus`: OBIS reports 0 occurrences for AphiaID 284071.
- `obis-occurrences-plesiosauria`: OBIS reports 0 occurrences for AphiaID 380398.

## Unresolvable / not built

- **Aglaophenia cornuta** (Kirchenpauer), named among the hydroid examples in Chapter XVII:
  no record in GBIF, NCBI, Wikidata or WoRMS under this name or any obvious variant. Rather
  than guess an identifier the taxon was omitted; the mention is noted here only.
- "Ungulates" is used informally and is not a taxon in any authority; not built.
- *Crepidula* appears only in footnote 7, which belongs to an earlier chapter; footnotes
  [1]–[585] (lines 25435–28404) belong to Chapters I–XIV and were not mined.

## Non-animal taxa seen (not built)

All plants; no fungi or protists were noticed in this slice.
*Secale cereale* (rye), *Lilium auratum*, *Phormium tenax*, *Papyrus antiquorum*,
*Molinia coerulea*, *Pincenectia recurvata*, *Begonia daedalea*, *Dionaea*, daisy,
gourd / pumpkin / melon, apple, cherry, bean, hyacinth, grass, palm-tree, reed, wheat-straw,
rush, sunflower, pear, hazel, oak, walnut.

## Ambiguities and judgement calls

Archaic names were resolved to the current accepted taxon; the name as written is preserved
in `names_as_written` and the reasoning in `notes`. Principal cases:

- *Orthagoriscus* → *Mola mola*; *Eohippus* → *Hyracotherium* (Thompson treats them as
  one; Froehlich 2002 resurrected *Eohippus* for *H. angustidens*); *Zeuglodon* →
  *Basilosaurus*; *Titanotherium* → *Megacerops*; *Pithecanthropus erectus* → *Homo erectus*;
  *Lupa* → *Portunus*; *Gonothyraea hyalina* → *G. loveni*; *Clytia johnstoni* →
  *C. hemisphaerica*; *Phormosoma luculenter* → *Hygrosoma petersii*; *Echinus acutus* →
  *Gracilechinus acutus*; *Cryptocleidus* (sic) → *Cryptoclidus*.
- Vernacular names: "zebra" → *Equus quagga*; "dogfish" → *Scyliorhinus canicula* (British
  usage is ambiguous with *Squalus acanthias*); "lobster" → *Homarus*; "antelopes" →
  Antilopinae; "coral" (as a mechanical material) → *Corallium rubrum*; "a shark" → Selachii;
  generic "crocodile" → Crocodylia, with *C. porosus* and *C. americanus* as separate records.
- Authority disagreements: PBDB vs GBIF for *Hyrachyus agrarius* (PBDB: subjective synonym of
  *H. modestus*), *Diceratherium tridactylum* (GBIF keeps *Aceratherium tridactylus*) and
  *Calippus placidus* (GBIF keeps *Protohippus placidus*); in each case the accepted name
  follows PBDB and both PBDB numbers (`pbdb_taxon_no`, `pbdb_accepted_no`) are recorded.
  *Belodon* is a nomen dubium referred to Phytosauria in PBDB; *Ellipsolithes* is placed in
  Ammonoidea by PBDB. Creodonta is recorded as Thompson wrote it although it is now regarded
  as polyphyletic.
- Crustacea: NCBI Taxonomy has only Pancrustacea (taxid 197562), accepted as the equivalent
  modern taxon and noted. *Homo neanderthalensis*: NCBI holds it as *Homo sapiens
  neanderthalensis*; accepted and noted.
- Lineages for taxa that no authority classified (Acanthopterygii, Antilopinae,
  *Brontops robustus*, Creodonta, Dinosauria, Nautiloidea, Pterosauria, Sauropoda, Sterninae,
  Vermilingua, *Ellipsolithes*) were supplied from standard classification and flagged in
  `notes`. GBIF's new backbone gives no class for ray-finned fishes, so those lineages lack a
  `class` entry.

## Validator

`node test-data/organisms/validate.mjs thompson-growth-form/ch15-epilogue`: 0 errors, 152 warnings.

- 148 × `mentioned_in is empty`: taxa named only in the running text, not in any claim.
  Their mentions are all in `mentions.json` with `file`/`line_start`/`line_end` sources; the
  README defines `mentioned_in` as a list of claim ids, so it is correctly empty for them.
- 4 × `no dataset`: the four supra-specific taxa listed above.
