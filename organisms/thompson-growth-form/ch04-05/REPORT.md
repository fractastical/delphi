# thompson-growth-form/ch04-05 — organism reference data

Slice: D'Arcy Thompson, *On Growth and Form* (1917), Chapters IV ("On the Internal Form and
Structure of the Cell") and V ("The Forms of Cells"); `books/thompson-growth-form/inputs/pg55264.txt`
lines 5907–9881; claims `thompson1917-ch04-*` and `thompson1917-ch05-*` (44 claims).

Built 2026-10-31 by a cloud agent (Claude Fable 5.1, branch `cursor/thompson-ch04-05-organisms-85d7`).
All identifiers, counts and checksums were taken from live API responses on 2026-10-31; nothing was
guessed. Raw API bodies were saved and hashed outside the repo; no data files are vendored (the only
downloaded files, AnAge `dataset.zip` 169,150 B and PanTHERIA 2,359,096 B, are recorded by size and
sha256 only).

## Counts

| what | n |
|---|---|
| mentions (`mentions.json`) | 73 (6 from claims, 67 from the book text) |
| distinct animal taxa (`taxa/`) | 45 |
| taxa with GBIF `usageKey` | 44 (missing: Vertebrata — no backbone usage) |
| taxa with NCBI taxid | 41 (missing: Turbellaria, *Campanularia groenlandica*, *Campanularia gracilis*, *Bonneviella grandis*) |
| taxa with Wikidata QID | 45 |
| taxa with ITIS TSN | 43 (missing: *Parascaris equorum*, *Campanularia gracilis*) |
| taxa with WoRMS AphiaID | 38 (terrestrial/freshwater taxa without WoRMS entries: *Salamandra*, *Parascaris equorum*, *Gryllotalpa*, *Araneus*, *A. diadematus*, *Equus caballus*, *Panthera leo*) |
| datasets (`datasets/`) | 71 = 44 GBIF occurrence counts + 24 NCBI genome assemblies + AnAge build 15 + PanTHERIA 1.0 + PBDB occurrence counts |

Validator: `node organisms/validate.mjs thompson-growth-form/ch04-05` → 0 errors, 41 warnings
(all "mentioned_in is empty", see below).

## How taxa were resolved

- GBIF: `/v1/species/match?name=…&kingdom=Animalia`; when the match fell back to a higher rank
  (HIGHERRANK for *Hydra*, *Fundulus*, *Chaetopterus*, *Galathea*) the accepted genus key was taken
  from the `alternatives` list and verified with `/v1/species/<key>`.
- NCBI Taxonomy: eutils `esearch` (db=taxonomy) on the accepted name, cross-checked against the
  Wikidata P685 value where present.
- Wikidata: `wbsearchentities` then `wbgetentities`, accepted only when P225 (taxon name) matched
  the accepted name; P846/P685/P850/P815 were used as cross-checks for GBIF/NCBI/WoRMS/ITIS.
- WoRMS: `AphiaRecordsByName` / `AphiaRecordByAphiaID` for marine taxa; ITIS: every TSN was
  verified with `getScientificNameFromTSN` (combinedName matched the accepted name).

Vernacular / archaic names and the rank chosen:

| as written | resolved to | rank | note |
|---|---|---|---|
| trout('s egg) | *Salmo trutta* | species | Ransom's waves and Prenant/Bouin material are brown trout |
| Hydra, fresh-water polype | *Hydra* | genus | |
| bird('s egg), birds | Aves | class | |
| sea-urchin | Echinoidea | class | no species given |
| salamander | *Salamandra* | genus | Flemming's classical material |
| newt | Salamandridae | family | no genus given |
| *Ascaris megalocephala* | *Parascaris equorum* | species | current name of the horse roundworm |
| Mole-cricket | *Gryllotalpa* | genus | |
| toad | Bufonidae | family | |
| turtle | Testudines | order | see GBIF note below |
| frog('s egg), blood of the frog | Ranidae | family | |
| Copepods | Copepoda | class | GBIF/WoRMS rank |
| insect | Insecta | class | |
| Turbellarian | Turbellaria | class | paraphyletic; GBIF/WoRMS/ITIS still carry the usage, NCBI does not |
| spider, spider's web | Araneae | order | |
| *Epeira* | *Araneus* | genus | *Epeira* is a synonym of *Araneus* |
| garden-spider | *Araneus diadematus* | species | the European garden spider |
| hydroids, hydroid calycle/cups, hydrozoon | Hydrozoa | class | |
| Campanularian zoophytes / Campanularians | Campanulariidae | family | |
| *C. integra* | *Orthopyxis integra* | species | WoRMS accepted name |
| *C. groenlandica* | *Campanularia groenlandica* | species | |
| *C. bispinosa* | *Campanularia* | genus | see unresolved |
| *C. raridentata* | *Clytia hemisphaerica* | species | WoRMS synonymy |
| *C. gracilis* | *Campanularia gracilis* | species | |
| *C. grandis* | *Bonneviella grandis* | species | WoRMS synonymy |
| horse, lion, eagle | *Equus caballus*, *Panthera leo*, *Aquila* | species/species/genus | |
| (collar-cells of) a sponge | Porifera | phylum | |
| Pteropod mollusca | Pteropoda | order | |
| oysters | Ostreidae | family | |
| man | *Homo sapiens* | species | |
| vertebrates, lower vertebrates | Vertebrata | subphylum | |
| decapod crustacea | Decapoda | order | |
| mammalia, mammalian | Mammalia | class | |
| *Inachus scorpio* | *Inachus dorsettensis* | species | *I. scorpio* is a synonym |
| Crayfish | Astacidae | family | Koltzoff's European crayfish; GBIF has no usage for infraorder Astacidea |
| *Galathea squamifera*, *Galathea*, *Inachus*, *Dromia* | as named | species/genus | |

## Datasets

- `gbif-occurrences-<slug>-2026-10-31` (44): exact `occurrence/count?taxonKey=` URL, retrieved
  time, count, byte size and sha256 of the response body. Landing page is
  `https://www.gbif.org/occurrence/search?taxon_key=<key>`.
- `ncbi-genome-<accession>` (24): from NCBI Datasets v2 `genome/taxon/<taxid>/dataset_report`
  with `filters.reference_only=true`. For taxa with RefSeq (GCF_) reference assemblies only those
  were recorded; for taxa with only GenBank (GCA_) assemblies all returned assemblies were recorded.
  The inspected distribution is the dataset_report JSON (shared by all assemblies from the same
  taxon query); the genome FASTA download URL is recorded with `inspected: false`. Genus- and
  family-level taxa (Hydra, Fundulus, Araneus, Aquila, Ostreidae, Astacidae, Gryllotalpa,
  Cerebratulus, Chaetopterus) are covered by assemblies of member species named in `role`.
- `anage-build-15`: zip downloaded and parsed; 4,645 data rows; covers Salmo trutta, Equus
  caballus, Panthera leo, Homo sapiens (species rows) and Salamandra (2), Aquila (8), Fundulus (4)
  (genus rows). Release notes say 4,671 entries; the shipped file has 4,645 rows — recorded as is.
- `pantheria-1-0-wr05-aug2008`: text file downloaded and parsed; 5,416 rows; covers Equus
  caballus, Panthera leo, Homo sapiens.
- `pbdb-occurrence-counts-2026-10-31`: one record with 30 inspected `occs/list.json?base_name=…
  &limit=1&rowcount` queries; 28 taxa with ≥1 fossil occurrence listed. *Chaetopterus* is not in
  the PBDB taxonomy and *Salmo trutta* has 0 occurrences; both queries are kept as distributions
  and counts but the taxa are not listed in `taxa`.

Not done: FishBase, AVONET, Amniote LHD, EltonTraits, IUCN, MorphoSource, TimeTree were not
queried (no programmatic access inspected in this pass). BOLD's public stats API returned HTTP 403
and was dropped rather than recorded uninspected.

## Taxa with only a GBIF occurrence count (no genome, no trait DB row)

Parascaris equorum (no reference genome in NCBI Datasets; empty response), Turbellaria (no NCBI
taxid, not in PBDB query set), Araneus diadematus (no genome), Campanularia, Orthopyxis integra,
Campanularia groenlandica, Campanularia gracilis (GBIF count 2), Bonneviella grandis (GBIF count
27), Inachus, Inachus dorsettensis, Galathea squamifera (no reference genomes; genomes queried for
Inachus/I. dorsettensis/Galathea/G. squamifera/Dromia/Cuvierina/Orthopyxis/Campanularia/
Campanulariidae/Salamandra all returned empty). Vertebrata has only the PBDB count (no GBIF usage).

## Warnings explained

- 41 × "mentioned_in is empty": only six mentions come from claim texts (ch05-12, -13, -21, -24,
  -25, -26, resolving to Araneae, Hydrozoa, Mammalia, Decapoda). All other taxa are mentioned only in
  the book text (sources with `file`/`line_start`/`line_end`), so their `mentioned_in` (claim ids)
  is legitimately empty.
- `integrity.identifier_resolves: false` on 45 datasets (44 GBIF, PanTHERIA): `www.gbif.org` and
  `esapubs.org` return HTTP 403 to non-browser clients; the HTTP status is recorded in
  `identifier_http_status`. The API/download URLs in `distributions` resolved and were inspected.

## Ambiguities and decisions

- GBIF Testudines: usage 793 (order, under Reptilia) is flagged `deleted` and returns 0
  occurrences; the live match returns 11418114 (ranked CLASS directly under Chordata). 11418114 is
  recorded as `gbif_usage_key`; `rank: order` and lineage follow Wikidata/ITIS/WoRMS.
- *C. bispinosa* (Fig. 72 C) could not be resolved to any current name in GBIF, WoRMS or
  Wikidata; the mention is attached to the genus *Campanularia*.
- "Crayfish" → Astacidae: GBIF's fuzzy match for Astacidea returned the family; the text
  (Koltzoff) concerns the European crayfish, so the family is appropriate.
- Generic "fish" (line 9039, "the form of a fish"), "worm" (7138, 7146), "metazoon" (7284),
  "animal cells", "muscle", "epithelium" were not given taxa (no rank below Animalia is implied).
- Implicit hosts of protists (*Anodonta* for *Spirochaeta anodontae*, *Tinca* for *Trypanosoma
  tineae*, mouse for *Trichomonas muris*, snake for *Trichomastix serpentis*, frog for *T.
  rotatorium*) were not recorded as mentions because the text names the parasite, not the host,
  except where the host is explicitly named (Hydra, frog).
- NCBI Taxonomy: Turbellaria has no current taxid (166384 given by Wikidata is empty in esearch);
  *Cuvierina* resolved by name to taxid 2952970 (Wikidata's 356472 is empty).

## Non-animal taxa seen (not built)

Protozoa / protists: Protozoon, Rhizopods, Infusoria, *Euglypha*, *Actinophrys (sol)*,
*Actinosphaerium*, Amoeba, *Aethalium* (Mycetozoa plasmodium), *Globigerina*, *Rotalia*, *Gromia*,
*Orbulina*, *Lagena* (*L. semistriata*), *Astrorhiza* (*A. crassatina*), *Ramulina*,
*Aschemonella*, *Thurammina*, *Nodosaria* spp., *Rheophax (Lituola) distans*, *Sagrina virgata*,
Radiolaria, Heliozoa, Foraminifera, *Noctiluca miliaris*, *Vorticella*, *Salpingoeca*,
*Tintinnus*, *Dinobryon*, *Codonella*, *Vaginicola*, *Folliculina*, *Trachelophyllum*,
*Trichodina pediculus*, *Dinenympha gracilis*, *Codosiga* / Choanoflagellates, *Trypanosoma*
(*T. tineae*, *T. rotatorium*, *T. lewisii*), *Trichomonas muris*, *Trichomonas angusta*,
*Trichomastix serpentis*, *Herpetomonas*, *Trypanoplasma*, *Bodo* (*B. gracilis*), *Distigma
proteus*. Algae: diatoms, desmids, *Euastrum*, *Spirogyra*. Fungi: yeast, *Achlya*. Plants:
*Trianea*, *Hydrocharis*, *Tradescantia*, mistletoe, generic plant cells, dried peas/seeds/pollen.
Bacteria: micrococci, *Spirillum*, Spirochaetes (*S. anodontae*, *S. balbiani*).
