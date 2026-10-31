# Organisms in *On Growth and Form* (1917), Chapter VIII (The Forms of Tissues, or Cell-aggregates, continued)

Slice `thompson-growth-form/ch08`: lines 12092–14081 of `books/thompson-growth-form/inputs/pg55264.txt`
and claims `thompson1917-ch08-01` … `thompson1917-ch08-17` (17 claims) in `books/thompson-growth-form/claims.json`.
Built 2026-10-31 by a cloud agent (branch `cursor/organisms-thompson-ch08-621e`); every identifier
and count was retrieved live from the APIs named below on that date. Nothing here is scored.

**Chapter title.** The task brief described this slice as "concretions, spicules and spicular
skeletons"; in the Project Gutenberg text that is Chapter IX (starting at line 14082). Lines
12092–14081 are Chapter VIII, *The Forms of Tissues or Cell-aggregates (continued)* — minimal-area
partitions, Errera's rule, eight-cell topology, coral septa, stomata, pollen tetrads — and the
`thompson1917-ch08-*` claims (lines 12129–13806) all fall inside that range, so the line range and the
claims were followed. Sponges and spicules are not mentioned in this slice.

## Counts

| | |
|---|---|
| Mentions (`mentions.json`) | 69 (4 attributed to a claim, 65 to text lines) |
| Distinct animal taxa (`taxa/`) | 32 |
| Resolved to GBIF backbone `usageKey` | 30 / 32 (missing: Octocorallia, Rugosa — no backbone usage for those ranks) |
| Resolved to NCBI Taxonomy id | 26 / 32 (missing: the six extinct coral taxa) |
| Resolved to Wikidata QID (P225 taxon name checked on the entity) | 30 / 32 (missing: *Heterophyllia*, *H. angulata*) |
| Resolved to ITIS TSN (verified with `getFullRecordFromTSN`) | 25 / 32 |
| Resolved to WoRMS AphiaID (verified with `AphiaRecordByAphiaID`) | 26 / 32 (missing: Anura, Apoidea, Papilionoidea, *Heterophyllia*, *H. angulata*, *Streptelasma*) |
| Dataset records (`datasets/`) | 40 |
| of which GBIF occurrence-count queries (one per taxon) | 28 |
| of which NCBI genome assemblies (one per taxon) | 7 |
| of which shared databases (one record per slice) | 5: WoRMS, OBIS occurrence counts, Paleobiology Database, GBIF Backbone Taxonomy, AnAge build 15 |
| Distributions with saved response body, byte size and sha256 (`inspected: true`) | 151 |
| Distributions recorded by URL only (`inspected: false`) | 7 (NCBI genomic FASTA packages, not downloaded) |
| Claims with at least one taxon mention | 2: ch08-08 (frog), ch08-12 (coral, *Heterophyllia*, *Zaphrentis*) |
| Taxa with no dataset | 0 |

Rank distribution of the 32 taxa: 3 species, 12 genera, 1 family, 2 superfamilies, 4 orders,
1 subclass, 6 classes, 3 phyla.

Files vendored: whole slice ≈ 0.2 MB; nothing over 1 MB. The AnAge zip (169,150 bytes) was downloaded
to `/tmp`, inspected with `awk`/`grep`, checksummed, and not committed. API response bodies were saved to
`/tmp` only; their size and sha256 are recorded in each distribution.

## How names were resolved

- GBIF `species/match?name=…&verbose=true` (with `kingdom=Animalia` for homonym-prone names). For
  Anura, *Echinus*, *Nautilus*, *Trochus*, *Pyrosoma*, *Nereis*, *Alcyonium*, Ctenophora and
  *Leucothea* the API returned `HIGHERRANK` (kingdom) because of homonyms; the accepted animal usage was
  taken from `alternatives` and confirmed with `species/<key>`. The match API does not match
  superfamilies, so Apoidea (1602) and Papilionoidea (1875) were confirmed via `species/<key>` (bodies
  vendored in the backbone dataset record).
- NCBI `esearch.fcgi?db=taxonomy` followed by `esummary` to confirm scientific name, rank and division;
  calls throttled to ≤2/s after an initial burst was rate-limited.
- Wikidata `wbsearchentities` then `wbgetentities` (`P225`, `P105`, `P846`, `P685`, `P850`, `P815`);
  only hits with a `P225` taxon name were accepted (e.g. Q128257 *Cephalopoda*, not a concept item).
  The first pass hit the Wikimedia rate limit and was re-run at one request per 1.5 s.
- ITIS: TSNs from Wikidata `P815` were each verified with `getFullRecordFromTSN` (all 25 valid).
- WoRMS `AphiaIDByName/<name>?marine_only=false`; where that returned `-999`/204 (Alcyonium,
  Ctenophora, Zaphrentis, Cyathophyllidae, Rugosa) the AphiaID from Wikidata `P850` was verified with
  `AphiaRecordByAphiaID`. Every AphiaID recorded is status `accepted` and equals its `valid_AphiaID`.

## Vernacular, archaic and problematic names

| As written | Resolved to | Rank | Comment |
|---|---|---|---|
| frog, frog's egg, frogs' eggs | Anura | order | Roux's and Rauber's material; species not named |
| *Rana esculenta* | *Pelophylax esculentus* | species | Hybridogenetic klepton. GBIF backbone, NCBI (8401 merged → 45623) and ITIS (665307 invalid) all sink it into *P. lessonae*; WoRMS and Wikidata keep it. `gbif_usage_key` 5784980 is the *P. esculentus* usage (SYNONYM of 2426654), `ncbi_taxid` 45623 is the merged target, `itis_tsn` null. The genome and AnAge rows are *P. lessonae* |
| sea-urchin (l. 12486), Echinids (l. 13540) | Echinoidea | class | "Bipinnaria larvae of Echinids" is Thompson's slip: bipinnaria are asteroid larvae |
| *Echinus*; "sea-urchin egg … figured by Driesch" (l. 13119) | *Echinus* | genus | Driesch's species was *E. microtuberculatus* (now *Psammechinus*), but the name as written is *Echinus* |
| nautilus | *Nautilus* | genus | |
| *Cynthia partita*, *Cynthia* | *Styela canopus* | species | GBIF (5711948 → 2331936) and WoRMS (252361 → 103926) agree; often cited as *Styela partita* |
| ascidian / Ascidian | Ascidiacea | class | the second use ("the Ascidian *Pyrosoma*") is a misattribution — *Pyrosoma* is a thaliacean |
| Cephalopod; cuttlefish (same Watase figure) | Cephalopoda | class | Watase's material was the squid *Loligo pealii*; not guessed |
| insects / dragon-flies / flies / bees / butterflies | Insecta / Odonata / Diptera / Apoidea / Papilionoidea | class / order / order / superfamily / superfamily | "bees" → Apoidea because the backbone lacks Anthophila (its *Anthophila* is a moth genus) |
| bee's cell | *Apis* | genus | honeycomb problem; hive-bee implied, as in slice ch01-02 |
| Alcyonarian polype | Octocorallia | subclass | Alcyonaria = Octocorallia; no GBIF backbone usage |
| corals, coral | Anthozoa | class | WoRMS/Wikidata rank it as a subphylum |
| Coelenterata | Cnidaria | phylum | historically Cnidaria + Ctenophora; context is corals |
| *Heterophyllia*, Heterophylliae, *H. angulata* | *Heterophyllia* M'Coy, 1849 / *H. angulata* Duncan | genus / species | extinct Carboniferous heterocorals; GBIF + PBDB only |
| *Zaphrentis* | *Zaphrentis* Rafinesque & Clifford, 1820 | genus | GBIF/Wikidata spell it *Zaphrenthis* (5430158); WoRMS/PBDB *Zaphrentis*; PBDB treats the Haime 1850 usage as a synonym of *Zaphrenthis* |
| Cyathophyllidae | Cyathophyllidae | family | extinct rugose family |
| Tetracoralla | Rugosa | order | no GBIF backbone usage; WoRMS ranks it as a class, ITIS as an order; NCBI only has an unrelated frog genus *Rugosa* |
| Streptoplasma | *Streptelasma* Hall, 1847 | genus | Thompson's spelling; no taxon "Streptoplasma" exists in GBIF, PBDB or WoRMS |
| Ctenophore(s) | Ctenophora | phylum | |
| *Eucharis* | *Leucothea* Mertens, 1833 | genus | *Eucharis* Eschscholtz, 1829 is a preoccupied name replaced by *Leucothea*; WoRMS does not index "Eucharis" |
| larval Echinoderm | Echinodermata | phylum | |
| *Ophiura*; Ophiurid (Pluteus) larva | *Ophiura* / Ophiuroidea | genus / class | |

## Datasets

- **GBIF occurrence counts** (28): `occurrence/count?taxonKey=<usageKey>`; body saved and checksummed.
  `www.gbif.org` landing pages returned HTTP 403 to the non-browser client; recorded in `integrity`
  (`identifier_resolves: false`, `identifier_http_status: 403`) with the API URL resolving 200. Not
  built for Apoidea and Papilionoidea because the occurrence index returns 0 for superfamily keys
  (counts retrieved and discarded as uninformative), nor for Octocorallia and Rugosa (no key).
- **NCBI genome assemblies** (7): *Pelophylax lessonae* GCF_965119305.1, *Echinus esculentus*
  GCA_976925275.1, *Nautilus pompilius* GCA_047652355.1, *Nereis zonata* GCA_982660795.1, *Apis
  mellifera* GCF_003254395.2, *Alcyonium digitatum* GCA_988586015.1, *Ophiura ophiura*
  GCA_035610815.1. Each record has the per-accession and per-taxon `dataset_report` bodies (inspected)
  and the FASTA package URL (not downloaded). Landing pages all returned HTTP 200. No reference
  assembly exists for *Trochus*, *Styela canopus*, *Pyrosoma* or *Leucothea*; higher taxa (class and
  above) were not given genome records because no single assembly represents them.
- **WoRMS** (1 record, 26 taxa): `AphiaRecordByAphiaID` bodies for every AphiaID used.
- **OBIS** (1 record, 23 taxa): `occurrence?taxonid=<AphiaID>&size=0` for the 26 WoRMS taxa; the three
  with 0 records (*Pelophylax esculentus*, *Zaphrentis*, Cyathophyllidae) are listed in `notes` and
  excluded from `taxa`.
- **Paleobiology Database** (1 record, 25 taxa): `taxa/single.json?name=…&show=attr,size,class`,
  `noc` field as the occurrence count. Covers all six extinct coral taxa. Not covered: *Nereis*,
  *Pyrosoma*, *Leucothea* (404); *Echinus* (PBDB resolves the name to Echinoidea by rank change);
  *Alcyonium* (PBDB's *Alcyonium* Hisinger 1823 is an unclassified homonym with 0 occurrences);
  *Pelophylax esculentus*, *Styela canopus* (not queried).
- **GBIF Backbone Taxonomy** (1 record, 30 taxa): dataset metadata plus the `species/match` (or
  `species/<key>`) body used for each resolution.
- **AnAge build 15** (1 record, 2 taxa): *Apis mellifera* (HAGRID 00015) and *Pelophylax lessonae*
  (HAGRID 00116); no rows for the other genus/species-level taxa.

Not used: BOLD, TimeTree, MorphoSource, IUCN (no time to inspect; MorphoSource would be the natural
source for the fossil coral specimens named in claim ch08-12's `candidate_data`).

## Taxa with no usable dataset

None. The weakest coverage is *Heterophyllia angulata* (GBIF count 2, PBDB 1 occurrence, GBIF backbone)
and *Streptelasma* (GBIF count, PBDB, backbone); the extinct corals have no NCBI/OBIS data by nature.

## Non-animal taxa seen (not built)

Plants and algae: *Sphacelaria*, Fuci / *Fucus*, *Taonia atomaria* (Dictyotaceae), mosses, moss rhizoids
and paraphyses, *Polytrichum*, *Spirogyra*, *Erythrotrichia discigera* (Bangiaceae), Liverwort / *Riccia*,
*Salvinia*, hyacinth, *Sedum*, *Epilobium*, *Passiflora* (Passion-flower), *Neottia*, *Periploca graeca*,
*Apocynum*, *Erica*, *Osmunda*, *Callithamnion* and the Florideae (red seaweeds), *Anthoceros*,
Monocotyledons, Dicotyledons, ferns, *Sphagnum*, *Selaginella*, *Jungermannia*, *Phascum*, *Adiantum*,
*Girardia sphacelaria*, *Pteris*, *Protococcus*, cryptogams generally, cambium cells and pollen-tubes.
Protists: the diatoms *Asterolampra marylandica*, *A. variabilis* and *Arachnoidiscus*.
Footnote 393 (outside the line range) mentions the protist *Euglena viridis*.

## Ambiguities and warnings

- The validator reports 28 warnings `mentioned_in is empty`: those taxa occur in the chapter text but in
  none of the 17 claims, which are almost all about plant cell division; only ch08-08 and ch08-12 name
  animals. Mentions for them are attributed to file lines, as the README specifies.
- Claim-sourced mentions use the claim's `claim` text as the quote where the taxon name appears there but
  not in the `quote` field (ch08-08 "frog"; ch08-12 *Heterophyllia*, *Zaphrentis*).
- Two generic uses of "animals" (ll. 13146, 13302: "plants as well as animals") were not recorded as
  mentions since kingdom Animalia is not a useful taxon record; "Pluteus"/"Bipinnaria" are larval
  forms, not taxa; "Thiere" in Schwann's title (l. 13151) is a book title.
- `lineage.order` for the extinct corals (Stauriida, Heterocorallia) and for *Ophiura* (Ophiurida) is
  taken from PBDB/WoRMS because the GBIF backbone leaves it blank.
- Dates in `retrieved_at` for bodies saved by `curl` are the file modification times (UTC) of the saved
  responses; those saved by the Node scripts are the response times.
