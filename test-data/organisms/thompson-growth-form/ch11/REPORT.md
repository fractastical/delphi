# thompson-growth-form / ch11 — Chapter XI, The Logarithmic Spiral

Source text: `claim-sources/thompson-growth-form/inputs/pg55264.txt` lines 16507–19560 (Project Gutenberg #55264,
*On Growth and Form*, 1917). Claims: the 23 `thompson1917-ch11-*` entries in
`claim-sources/thompson-growth-form/claims.json`. Built 2026-10-31 by a cloud agent (`vendored_by` in every dataset
record); no record carries an `assessment`.

In this edition Chapter XI covers shells (univalves, bivalves, brachiopods, pteropods, septa and
sutures) plus the introductory list of organic spirals (ruminant horns, elephant trunk and tusk,
snake, monkey and chameleon tails, cuttle-fish arm). Horns, teeth and claws proper are Chapter XII–XIII
material and appear here only as passing words ("horn", "tusk", "claw") without a taxon.

## Counts

| what | count |
|---|---|
| mentions (`mentions.json`) | 609 (525 located in the text by file+line, 84 in claim texts) |
| distinct animal taxa (`taxa/`) | 194 (64 species, 103 genera, 10 families, 17 higher ranks) |
| extinct (fossil-only) taxa | 38 by definition; 41 of the 161 PBDB-resolved taxa are flagged extinct in PBDB |
| resolved to GBIF backbone `usageKey` | 187 / 194 |
| resolved to NCBI Taxonomy taxid | 144 / 194 |
| resolved to Wikidata QID (P225 verified) | 186 / 194 |
| resolved to WoRMS AphiaID | 154 / 194 |
| resolved to PBDB `taxon_no` (`identifiers.pbdb_taxon_no`) | 161 / 194 |
| resolved to Open Tree OTT id (`identifiers.ott_id`, extra field) | 178 / 194 |
| ITIS TSN | 0 (ITIS was not queried; `itis_tsn` is null everywhere) |
| datasets (`datasets/`) | 405 |
| — GBIF occurrence-count records (one per GBIF-resolved taxon) | 187 |
| — PBDB fossil occurrence-count records (one per PBDB taxon with ≥1 occurrence) | 159 |
| — NCBI genome assemblies (species/genus/family-rank extant taxa with assemblies) | 52 |
| — shared-database records (one per database for the slice) | 7: GBIF backbone, NCBI Taxonomy, Wikidata, WoRMS, PBDB taxonomy, OBIS statistics, Open Tree TNRS |
| taxa with no dataset | 0 |
| taxa covered only by shared records | 1 (`decapodiformes`: no GBIF rank, no PBDB record) |

Validator: `node test-data/organisms/validate.mjs thompson-growth-form/ch11` → 0 errors, 165 warnings. All
165 warnings are `mentioned_in is empty`: those taxa occur in the chapter text but in none of the
23 claims (the claims name only ~29 taxa). Three claims (`ch11-03`, `ch11-04`, `ch11-07`) name no
animal taxon at all (generic "shells and horns"; the botanical scorpioid cyme; "shell, tusk, horn
and claw" versus "a fish" and "a leaf").

## Method

1. Every line of the slice (italic underscores stripped) was scanned for an explicit list of
   names-as-written (longest match first, word boundaries, each match consumed once), including names
   split across a line break. Claim `quote`, `claim`, `scope` and `label` texts were scanned the
   same way; claim mentions quote the claim field in which the name appears.
2. Each name was mapped to a query name (the current accepted name where the written name is a
   known synonym, e.g. Dolium → Tonna, Scalaria pretiosa → Epitonium scalare) and resolved live on
   2026-10-31 against: GBIF `species/match` (kingdom Animalia, phylum and rank hints, `strict=true`;
   for 14 homonymous genus names the match API returns only the kingdom, so the key was taken from the
   backbone `species/search` restricted to the accepted genus — noted in each taxon), NCBI
   `esearch`+`esummary` (`[Scientific Name]`, single hit required), Wikidata `wbsearchentities` with
   the hit's P225 checked against the name (Turbo via a SPARQL P225 lookup), WoRMS
   `AphiaRecordsByName` (`marine_only=false`), PBDB `taxa/single`, and Open Tree `tnrs/match_names`
   (exact matches only). Nothing was guessed: an authority that did not return the name is null and
   the taxon `notes` say so.
3. Datasets were recorded from the exact API URL with `retrieved_at`, `byte_size` and `sha256` of the
   saved response body (`inspected: true`). Landing pages were HEAD/GET-checked: `www.gbif.org` and
   `paleobiodb.org/classic` return HTTP 403 to non-browser clients, recorded in `integrity` with the
   note that the API query resolved. No file over 1 MB; the largest vendored response is the PBDB
   taxon list (33 kB) and no response body is committed, only its checksum.

## Non-animal taxa seen (not built)

- Foraminifera (protists): "the Foraminifera", "Foraminiferal shell", *Globigerina* (Fig. 238),
  "the Nummulite(s)", *Pulvinulina* (Fig. 259), *Cristellaria* (Fig. 260), *Rotalia*, *Nodosaria*.
- Plants: sunflower florets/disc, "cordate leaf", Borage and the scorpioid/helicoid cymes
  (Schimper, Bravais), "woody plant-cell", "climbing stem", "margin of a leaf".
- Not taxa: "landscape marble" (Bristol Rhaetic), the paraffin "artificial shells" of Kappers.

## Animal references not turned into taxa

- "the contour of a fish" (ch11-07): no taxon above vernacular "fish"; skipped.
- Generic "horn", "tusk", "claw", "shell", "operculum": structures, not taxa.
- Zittel's shell-form terms *orthoceracone, bactriticone, gyroceracone, mimoceracone, nautilicone,
  ammoniticone* are morphotype names derived from genera and were not counted as mentions of those
  genera (Orthoceras is separately mentioned and built).
- Line 16525 "cylindrical Helix" is the curve, not the snail, and is excluded from `helix`.

## Taxa resolved above the rank written, or with notable ambiguity

| written | recorded as | why |
|---|---|---|
| Pupa, Pupae | family Pupillidae | GBIF/WoRMS *Pupa* Röding is a marine acteonid; Thompson's chrysalis snails are Pupillidae |
| Bulimi, Bulimus | order Stylommatophora | *Bulimus* Scopoli is now the freshwater *Bithynia* (WoRMS); "Bulimi" auctorum are assorted land snails |
| Argiope (brachiopod) | genus *Megathiris* | *Argiope* Deslongchamps is a junior homonym (spider genus); WoRMS gives Megathiris |
| Cyclostoma | genus *Pomatias* | WoRMS synonymy |
| Estheria | suborder Spinicaudata | *Estheria* is preoccupied/abandoned; clam shrimps = Spinicaudata |
| cuttle-fish | superorder Decapodiformes | covers Sepia and the "decapod cuttle-fishes" Todarodes, Illex |
| monkey | infraorder Simiiformes | text does not specify |
| worm(s) | phylum Annelida | the examples given (Spirorbis, Spirographis, Ditrupa) are polychaetes |
| Sigaretus haliotoides | *Sinum haliotoideum* | the literal name in GBIF/WoRMS is a homonym synonymised with the slug *Testacella maugei*; Woodward's figure is the ear moon-snail |
| Turbo phasianus | genus *Turbo* | not in GBIF/WoRMS (GBIF only fuzzy-matches) |
| Natica glaucina | genus *Natica* | same |
| Phasianella bulloides | genus *Phasianella* | same (GBIF fuzzy → *P. australis*, not confirmed) |
| Solarium magnificum | genus *Architectonica* | not in GBIF/WoRMS |
| Melanopsis terebralis | genus *Melanopsis* | not in GBIF/WoRMS/PBDB |
| Turritella imbricata (Naumann) | genus *Turritella* | GBIF's "T. imbricata" is a synonym of the Caribbean *T. variegata*; Naumann's fossil is more likely *T. imbricataria* Lamarck — unverifiable |
| Cleodora chierchiae, C. australis, C. pygmaea | genus *Clio* | not carried as species by GBIF/WoRMS/NCBI/Wikidata |
| Caprinella, Caprinella adversa | genus *Ichthyosarcolites* | GBIF: Caprinella = Ichthyosarcolites; the epithet *adversa* not found anywhere |
| Ammonites (Sonninia) Sowerbyi | genus *Sonninia* | species is in PBDB (txn:439317, 0 occurrences) but not in GBIF/Wikidata; recorded at genus rank with the PBDB species noted |
| Thecidium | genus *Thecidea* | WoRMS synonymy |
| Eburnea (= Eburna) | genus *Eburna* | WoRMS and GBIF still carry Eburna as accepted |
| Fusus | genus *Fusinus* | WoRMS synonymy |

Synonym resolutions taken from GBIF/WoRMS and recorded under the accepted name (written name kept in
`names_as_written`): Haliotis excavatus → *H. cyclobates*; H. rugoso-plicata → *H. australis*;
H. viridis → *H. varia*; Fusus antiquus → *Neptunea antiqua*; Fusus longissimus → *Fusinus
longissimus*; Fusus colosseus → *Hemifusus colosseus*; Helix nemoralis → *Cepaea nemoralis*;
Terebra/Acus dimidiata, maculata, crenulata → *Oxymeris*; Cerithium palustre/sulcatum/lignitarum →
*Terebralia*; Mitra episcopalis → *Mitra mitra*; Delphinula atrata → *Angaria delphinus*; Dolium →
*Tonna*; Solarium → *Architectonica*; Helicostyla polychroa → *Cochlodryas viridostriata*;
Solaropsis pellis-serpentis → *S. undata*; Pleurotomaria conoidea → *Pyrgotrochus elongatus*;
Ammonites tornatus → *Cladiscites tornatus*; Trochus niloticus → *Rochia nilotica*; T. zizyphinus →
*Calliostoma zizyphinum*; Triton corrugatus → *Monoplex corrugatus*; Lamellaria perspicua →
*Marsenia perspicua* (WoRMS: *Marseniotta*); Hyalaea → *Cavolinia*; H. trispinosa → *Diacria
trispinosa*; Cleodora → *Clio*; C. balantium → *Clio recurva*; Isocardia (cor) → *Glossus
(humanus)*; Cyclas → *Sphaerium*; Artemis → *Dosinia*; Avicula → *Pteria*; Modiola → *Modiolus*;
Psammobia → *Gari*; Solen pellucidus → *Phaxas pellucidus*; Lima subauriculata → *Limatula
subauriculata*; Spirographis → *Sabella*; Pileopsis → *Capulus*; Cymba → *Cymbium*; Anodon →
*Anodonta*; Gervillea → *Gervillia*; Athyridae → Athyrididae; Oekotraustes → *Oecotraustes*.

Other flags carried in taxon `notes`: *Natica aperta* is accepted in GBIF but a synonym of *Bulbus
smithii* in WoRMS; *Cavolinia longirostris* is *Diacavolinia longirostris* in WoRMS; *Lithocardium*
is "doubtful" in GBIF and has no PBDB occurrences; WoRMS hits for *Gryphaea* (misapplied to
*Crassostrea*) and *Diceras* (homonym) were discarded; GBIF files Serpentes with rank "family".

## Taxa with weak or no per-taxon data

- No GBIF key (not a backbone rank): Nautiloidea, Ammonoidea, Crustacea, Spinicaudata, Ruminantia,
  Decapodiformes, Simiiformes — covered by PBDB counts (except Decapodiformes) and the NCBI/Wikidata/WoRMS
  shared records.
- No NCBI taxid (50 taxa): essentially all extinct genera/species (ammonoids, Palaeozoic brachiopods,
  rudists, fossil turritellids) plus a few extant species without sequence data (*Nautilus
  umbilicatus*, *Melo aethiopicus*, *Tonna zonata*, *Eburna*, *Architectonica trochlearis*, *Natica
  aperta*, *Marsenia perspicua*, *Cochlodryas viridostriata*, *Solaropsis undata*, *Limatula
  subauriculata*, *Terebratula*, *Thecidea*, *Cavolinia longirostris*, *Rhynchonella*).
- No Wikidata item: *Nautilus umbilicatus*, *Bellerophon expansus*, *Natica aperta*, *Marsenia
  perspicua*, *Pyrgotrochus elongatus*, *Cochlodryas viridostriata*, *Solaropsis undata*, *Koninckina*.
- No WoRMS record (40): the extinct taxa above plus Ruminantia, Simiiformes, *Potamides*.
- No PBDB record (33): mostly extant species with no fossil entries, plus Decapodiformes, *Todarodes*,
  *Illex*, *Sabella*.
- PBDB occurrence counts were only built where the taxon has ≥1 occurrence (159 of 161).
- Genome assemblies: for genus- and family-rank taxa the record is the highest-level assembly of
  *some* member species (named in `label` and `role`); where the same assembly was selected for a
  genus and its species (*Cerithium* / *C. nodulosum*) one record lists both.

## Databases considered but not recorded

- **MorphoSource**: the public media API ignores taxonomic facet parameters and its `q` full-text search
  returned implausible totals (2 media for *Homo sapiens*), so no counts could be vouched for; dropped.
- **BOLD** v4 public API returns HTTP 403 from this environment; **IUCN Red List** API needs a token;
  **TimeTree** has no API. **AnAge / PanTHERIA**: the only amniotes here (sheep, horse, human,
  elephants, snakes, chameleons, monkeys) are incidental asides, so these were not pulled.
- **ITIS** was not queried (time); `itis_tsn` is null throughout.
- OBIS statistics were recorded for 130 marine taxa with an AphiaID (3 of them have 0 OBIS records);
  land snails, freshwater bivalves and terrestrial vertebrates were excluded.
