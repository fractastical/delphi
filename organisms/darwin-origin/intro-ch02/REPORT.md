# Slice report: darwin-origin / intro-ch02

Introduction and Chapters I–II of *On the Origin of Species* (Project Gutenberg #1228,
`darwin-origin/inputs/pg1228.txt` lines 313–2063). Claims in scope: the 37 claims whose id
starts with `darwin1859-intro-`, `darwin1859-ch01-` or `darwin1859-ch02-`.

Built by a cloud agent (`claude-fable-5.1`, branch `cursor/organisms-darwin-intro-ch02-e496`)
on 2026-10-31. All identifiers, counts, sizes and checksums come from live API responses or
downloaded files; nothing was typed from memory. Raw responses were kept outside the repo.

## Counts

| what | n |
|---|---|
| mentions (`mentions.json`) | 133 |
| – sourced from a claim quote | 8 (claims intro-01, ch01-04, ch01-09, ch01-10, ch01-13, ch02-11) |
| – sourced from text lines | 125 |
| distinct animal taxa | 35 |
| – species / subspecies | 18 / 3 |
| – genus / family / order / class / phylum | 3 / 5 / 2 / 2 / 2 |
| taxa resolved to GBIF backbone usageKey | 35 / 35 |
| taxa resolved to NCBI Taxonomy taxid | 35 / 35 |
| taxa resolved to Wikidata QID | 35 / 35 |
| taxa with ITIS TSN (from Wikidata P815, verified against ITIS) | 35 / 35 |
| taxa with WoRMS AphiaID (from Wikidata P850, verified against WoRMS) | 20 / 35 |
| dataset records | 61 |
| – GBIF occurrence counts (one per taxon) | 35 |
| – NCBI genome assemblies (one per taxon with an assembly) | 20 |
| – shared databases | 6 (GBIF backbone match responses, AnAge build 15, PanTHERIA 1.0, EltonTraits 1.0, Amniote Life-History DB Aug 2015, PBDB occurrence counts) |
| taxa with at least one dataset | 35 / 35 |

Shared-database coverage (taxa listed on the record): AnAge 30, PanTHERIA 17, EltonTraits 26,
Amniote DB 27, PBDB 29, GBIF backbone 35.

Validator: `node organisms/validate.mjs darwin-origin/intro-ch02` → 0 errors, 29 warnings
(all "mentioned_in is empty", see below).

## How taxa were resolved

- GBIF: `api.gbif.org/v1/species/match?name=…&verbose=true`. 31 names matched EXACT/ACCEPTED
  or HIGHERRANK (Camelus). Three matched a **synonym** and are recorded under the accepted
  usage looked up by key: Canis familiaris → *Canis lupus familiaris* 6164210; Bos indicus →
  *Bos taurus indicus* 4262587; Mustela furo → *Mustela putorius furo* 5218913. `Coccus`
  returned no match (homonyms); the genus usage 2049629 (Coccus Linnaeus, 1758, Coccidae) was
  taken from Wikidata P846 and verified with `species/2049629`.
- NCBI: eutils `esearch` + `esummary`, rank and name checked. NCBI ranks Bos indicus as a
  species (9915) where GBIF has a subspecies; recorded as is.
- Wikidata: `wbsearchentities` then `wbgetentities`; the item whose P225 (taxon name) or
  P846 (GBIF id) matches the GBIF usage was chosen (e.g. Q26972265 *Canis lupus familiaris*,
  not Q144 "dog").
- ITIS / WoRMS ids were taken from the chosen Wikidata item and re-checked with
  `getScientificNameFromTSN` / `AphiaRecordByAphiaID`; all ITIS names matched. WoRMS AphiaID
  196065 for Columbidae returned an empty body and is left null; 14 other taxa have no WoRMS
  statement on Wikidata (terrestrial mammals, silkworm).

## Datasets and provenance

- GBIF occurrence counts: `occurrence/count?taxonKey=<usageKey>`; the one-line body was saved
  and checksummed. Counts include all descendant taxa in the backbone.
- Genomes: NCBI Datasets v2 `genome/taxon/<taxid>/dataset_report?filters.reference_only=true&
  filters.assembly_source=refseq`. 18 taxa have a RefSeq reference assembly. *Rangifer
  tarandus* and *Pavo cristatus* have no RefSeq assembly; a GenBank chromosome-level assembly
  flagged "reference genome" in the GenBank report is recorded for each and the record `notes`
  says so. *Lagopus lagopus* (taxid 52650) has **no assembly at all** in NCBI Datasets at
  retrieval (empty report for any level). The JSON report that was actually read is the
  inspected distribution; the FASTA download URL is listed `inspected: false`.
- AnAge build 15: `dataset.zip` (169,150 bytes) downloaded and unzipped; 4,645 data rows in
  `anage_data.txt` (release notes say 4,671 entries). Cited with the 2013 NAR paper named in
  the bundled `release.html`.
- PanTHERIA 1.0, EltonTraits 1.0, Amniote DB: downloaded from the Ecological Archives files on
  esapubs.org (2.36 MB, 2.20 MB + 0.58 MB, 4.73 MB). Row counts for our taxa were computed by
  exact binomial (species) or by the genus / family / order / class column (higher taxa) and
  are listed per taxon under `coverage`. Trait databases carry the **wild** form for several
  domesticates: ferret only as *Mustela putorius*; dog mostly as *Canis lupus* (AnAge also has
  *Canis familiaris*); cat as both *Felis catus* and *Felis silvestris*; no row anywhere for
  *Bos indicus*. Both wild and domestic rows are listed where present. The Amniote DB DOI is
  `10.1890/15-0846R.1` (the `…-0846.1` form does not resolve).
- PBDB: `data1.2/occs/list.json?base_name=<name>&limit=1&rowcount`; `records_found` per
  taxon. Names absent from the PBDB taxonomy table (*Bombyx mori*, *Mustela putorius furo*,
  *Bos taurus indicus*, *Canis lupus familiaris*, *Coccus*) and *Pavo cristatus* (0
  occurrences) are not listed. Each saved response carries a varying `elapsed_time` field, so
  checksums are of the saved body only.
- Identifiers: GBIF backbone and the three ESA data papers use the DOI URL as identifier; the
  Handle API confirmed each DOI resolves (`responseCode 1`), but www.gbif.org, esapubs.org
  HTML pages and the Wiley/OUP targets return HTTP 403 to this host's non-browser client, so
  `integrity.method` says exactly what was checked. GBIF occurrence records use the API search
  URL (HTTP 200) as identifier and give the www.gbif.org page as `landing_page`.
- Nothing over 1 MB was committed; no data file was vendored, only sizes and SHA-256.

## Databases tried but not used

- **BOLD**: v4 API (`v4.boldsystems.org/index.php/API_Public/stats`) returns HTTP 403 and the
  new portal API is behind a Cloudflare challenge from this host. No BOLD record.
- **IUCN Red List**: API v4 requires a token; no unauthenticated endpoint exists. No record.
- **TimeTree, MorphoSource, Phenome10K, Open Tree of Life**: not queried in this pass (no
  public count API without a key, or no time); candidates for a later pass.
- **FishBase**: no fish in the slice. **AVONET**: Figshare download did not return a direct
  file in the time available; EltonTraits and the Amniote DB cover the same birds.

## Taxa with weak or indirect dataset coverage

- *Lagopus lagopus*: no genome assembly in NCBI; covered by GBIF, AnAge, EltonTraits, Amniote
  DB, PBDB at species level. The red grouse itself is subspecies *L. l. scotica* (GBIF
  5227742, NCBI 359986, Wikidata Q1077472, ITIS 677740), noted on the taxon record.
- *Bos taurus indicus*: only GBIF (1,737 occurrences) and the NCBI genome; no trait-database
  row.
- *Coccus*: only GBIF (8,261 occurrences); not in AnAge/PBDB. Lubbock's organism was *Coccus
  hesperidum* (GBIF 5712981, NCBI 538890).
- *Bombyx mori*: GBIF, NCBI genome and backbone only (not in PBDB or the vertebrate trait DBs).
- Higher taxa (Insecta, Coleoptera, Mollusca, Brachiopoda, Gastropoda): GBIF and PBDB counts
  plus AnAge rows for the few species AnAge has; these are placeholders until a later pass
  names species.

## Non-animal taxa seen (not built)

Misseltoe (*Viscum album*) and the trees it grows on; wheat; hyacinth, potato, dahlia; cabbage;
pears and apples (Ribston-pippin, Codlin); fuller's teazle and wild *Dipsacus*; gooseberry;
heartsease; rose, pelargonium; strawberry; *Rubus*, *Rosa*, *Hieracium* (polymorphic genera);
primrose and cowslip (*Primula veris* and *elatior*); common oak (sessile and pedunculated
oaks); 182 British plants of Watson, London Catalogue plants, floras of twelve countries;
"fresh-water and salt-loving plants"; the plant poisons affecting white sheep and pigs. No fungi
or microbes are named in this slice.

## Ambiguities and decisions

- **"the plantigrades or bear family"** → Ursidae; "carnivorous animals" → Carnivora.
  "Carnivorous birds" (line 545) was **not** built: raptors span Accipitriformes,
  Falconiformes and Strigiformes and Darwin gives no further clue.
- **"the many foxes"** → genus *Vulpes*; some foxes (grey and South American foxes) fall
  outside *Vulpes*, which is why Canidae is also a taxon.
- **"common camel" / "camel"** (as opposed to "dromedary") → genus *Camelus*; almost certainly
  the Bactrian camel but Darwin does not say.
- **"finch(es)"** → Fringillidae. The Galapagos birds he compared (line 1730) are not called
  finches in this slice and are not built.
- **"shells in the brackish waters of the Baltic"** → Mollusca (phylum); **"fossil land-shells
  in Madeira"** → Gastropoda (class). Both could be narrowed with Wollaston's monographs.
- **"Gallus bankiva"** → *Gallus gallus* (now *G. g. bankiva*). **"C. intermedia of
  Strickland"** → *Columba livia* (now *C. l. intermedia*). **"Thoulouse"** goose → *Anser
  anser*.
- "pigs" → *Sus scrofa* at species rank (domestic form is *S. s. domesticus*, GBIF 9104700).
- Generic words ("animals", "birds", "mammal", "insects" where used only as a class word,
  "domestic animals", "poultry" only when it stands for breeds of fowl) were recorded only
  where Darwin makes a substantive statement; "birds of the Galapagos", "a few animals in
  Ireland" and "Britain has hardly one peculiar mammal" were left out as unresolvable.

## Warnings left in place

29 taxa have `mentioned_in: []` because no claim *quote* in this slice names them (the claim
quotes are short). Their text locations are in `text_mentions` on the taxon record and in
`mentions.json` with file + line numbers, as the README specifies for non-claim mentions.
