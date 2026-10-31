# Organisms slice report: thompson-growth-form / ch12-14

Source: D'Arcy Thompson, *On Growth and Form* (1917), Chapters XII–XIV (The Spiral Shells of the
Foraminifera; The Shapes of Horns, and of Teeth or Tusks; On Leaf-arrangement, or Phyllotaxis),
`claim-sources/thompson-growth-form/inputs/pg55264.txt` lines 19561–21574, plus the 41 claims
`thompson1917-ch12-*`, `thompson1917-ch13-*`, `thompson1917-ch14-*` in `claim-sources/thompson-growth-form/claims.json`.
Built on 2026-10-31 by a Cursor cloud agent (model `claude-fable-5.1`, branch
`cursor/organisms-thompson-ch12-14-5199`). Only files inside `test-data/organisms/thompson-growth-form/ch12-14/` were written.

## Counts

| Item | Count |
|---|---|
| Mentions (`mentions.json`) | 189 (25 in claims, 164 located in the book text by file/line) |
| Distinct animal taxa (`taxa/`) | 62 (32 species, 2 subspecies, 13 genera, 1 tribe, 8 families, 1 suborder, 3 orders, 1 subclass, 1 class) |
| Taxa resolved to GBIF backbone `usageKey` | 59 / 62 |
| Taxa resolved to NCBI Taxonomy id | 57 / 62 |
| Taxa resolved to Wikidata QID (P225 verified) | 62 / 62 |
| Taxa with ITIS TSN (from Wikidata P815, verified against the ITIS web service) | 52 |
| Taxa with WoRMS AphiaID (from Wikidata P850, verified against the WoRMS REST API) | 23 |
| Taxa with a Paleobiology Database taxon number | 57 |
| Taxa with an IUCN Red List taxon id (from Wikidata P627, not verified against IUCN) | 24 |
| Dataset records (`datasets/`) | 96 |
| – GBIF occurrence-count records (one per taxon with a GBIF key) | 59 |
| – NCBI reference genome assemblies (one per accession) | 30 (covering 32 taxa; two accessions are shared by a genus and its species) |
| – Shared databases (one record each for the slice) | 7: AnAge build 15 (41 taxa), PanTHERIA 1.0 (37), Amniote Life-History DB Aug 2015 (42), EltonTraits 1.0 (39), Paleobiology Database (51), MorphoSource media (29), IUCN Red List ids (24) |
| Taxa with no dataset at all | 0 |
| Taxa with `mentioned_in` non-empty (named in a claim's quote, text or label) | 20 |

Validator: `node test-data/organisms/validate.mjs thompson-growth-form/ch12-14` → 0 errors, 42 warnings.
All warnings are `mentioned_in is empty` for the 42 taxa that occur only in the running text of the
chapters and not in any extracted claim (each has file/line mentions in `mentions.json`).

## Where the animals are

Chapter XII is about Foraminifera (protists) and contains only five animal taxa, used as comparisons:
*Nautilus*, the Ammonites (Ammonoidea), the tube-worms *Serpula* and *Spirorbis*, and generic
"univalve molluscan shells" (Gastropoda). Chapter XIII supplies the other 57 taxa (horned ruminants,
rhinoceroses, deer, rodents, carnivores, proboscideans, birds). Chapter XIV (phyllotaxis) contains no
animal taxon except a back-reference to "our turbinate shells" (recorded under Gastropoda).

## Resolution decisions and ambiguities

- **Generic vernaculars resolved above species**: "sheep" → *Ovis* (genus), "goat(s)" / "wild goats"
  → *Capra* (genus); "the ram" / "Highland ram" → *Ovis aries*; "the domestic … goats" → *Capra hircus*;
  "antelopes", "hollow-horned ruminants", "horned quadrupeds" → Bovidae ("antelope" is not a taxon);
  "ruminants" → Ruminantia; "the ox / oxen" → *Bos taurus*; "buffaloes" → tribe Bovini (both *Bubalus*
  and *Syncerus* fit); "the rhinoceros" → Rhinocerotidae; "the deer / the stag" → Cervidae; "eagle" →
  Accipitridae; "parrot" → Psittaciformes; "dolphin" → Delphinidae; "hedgehog" → Erinaceidae;
  "a rat" → *Rattus*; "the beaver" → *Castor*; "the elephant / existing species of elephant" →
  Elephantidae; "the mammoth" → *Mammuthus*; "the Babirussa" → *Babyrousa*; "the snail", "univalves",
  "turbinate shells" → Gastropoda; "the apple-snail" → Ampullariidae; "the carnivore" → Carnivora;
  "rodents" → Rodentia.
- **"the great white rhinoceros (Ceratorhinus)"**: the white rhinoceros is *Ceratotherium simum*, but
  *Ceratorhinus* Gray 1867 is a synonym of *Dicerorhinus* (Sumatran rhinoceros). Thompson's parenthetical
  genus is an error; resolved by the vernacular to *C. simum* and noted in the taxon file.
- **"the Leucoryx"**: resolved to *Oryx leucoryx* (Arabian oryx); in 1917 the name was sometimes also
  applied to the scimitar oryx (*O. dammah*), so this is a best match.
- **"Capra sinaitica"** (Arabian wild goat) → *Capra nubiana*; **"Ovis Poli"** → *Ovis ammon polii*;
  **"O. hodgsoni"** → *Ovis ammon hodgsoni* (GBIF spells it *hodgsonii*; match type FUZZY);
  **"Cervus Duvauceli"** → *Rucervus duvaucelii*; **"sambur"** → *Rusa unicolor*; **"koodoo"** →
  *Tragelaphus strepsiceros*; **"Scinde wild goat"** → *Capra aegagrus* (ssp. *blythi*);
  **"moufflon"** → *Ovis gmelini* (GBIF accepts this name; MSW3-based databases use *O. orientalis*,
  so trait-database rows were matched under both names, and none were found in PanTHERIA/AnAge).
- **"Mastodon angustidens"** → *Gomphotherium angustidens*; **"M. arvernensis"** → *Anancus
  arvernensis* (GBIF still lists it as a synonym of *Mastodon arvernensis*); **"American mastodons"** →
  *Mammut americanum*; **"Machairodus … that great extinct tiger"** → *Machairodus* (the "tiger" is not
  a separate mention).
- **GBIF synonyms**: *Capra aegagrus*, *Cervus canadensis* and *Canis familiaris* are synonyms in the
  GBIF backbone (of *Capra hircus aegagrus*, *Cervus elaphus canadensis*, *Canis lupus familiaris*).
  `gbif_usage_key` holds the matched name's key, `gbif_accepted_usage_key` the accepted one, and the
  GBIF occurrence count was taken under the accepted key (stated in each dataset's count description).
- **No GBIF key** (the backbone has no taxa at these ranks): Ammonoidea (subclass), Ruminantia
  (suborder), Bovini (tribe). **No NCBI taxid**: Ammonoidea, Bovini, *Machairodus*, *Gomphotherium
  angustidens*, *Anancus arvernensis* (extinct taxa are not in NCBI Taxonomy). Each is stated in the
  taxon's `notes`. Ammonoidea's WoRMS id 737043 resolves to the spelling "Ammonoida".
- `mentioned_in` lists a claim when the taxon name occurs in the claim's `quote`, `claim` or `label`
  text; the 164 text mentions carry 3-line windows (`line_start`–`line_end`) around the matched line.
  Footnotes to these chapters sit outside the assigned line range and were not scanned.
- Skipped as too generic to be a taxon: "mammals in general", "quadrupeds", "the animal",
  "carnivore" (kept only as order Carnivora), "little worms" (covered by *Serpula*/*Spirorbis*).

## Datasets: provenance notes

- **GBIF occurrence counts**: `https://api.gbif.org/v1/occurrence/count?taxonKey=<key>`; response body
  (a bare integer) saved and hashed, `inspected: true`. `www.gbif.org` landing pages return HTTP 403 to
  non-browser clients, so `integrity.identifier_resolves` is `false` with `landing_page_http_status: 403`
  and `api_url_http_status: 200`, as instructed.
- **NCBI genomes**: `https://api.ncbi.nlm.nih.gov/datasets/v2/genome/taxon/<taxid>/dataset_report?filters.reference_only=true`
  for species, subspecies and genera; the first report is recorded. Landing pages
  `https://www.ncbi.nlm.nih.gov/datasets/genome/<accession>/` were checked with HEAD (all 200). For
  genus-level taxa the assembly is of a member species (e.g. *Nautilus pompilius* for *Nautilus*, *Oryx
  dammah* for *Oryx*, *Rattus norvegicus* for *Rattus*); the role field says so. Two accessions are
  shared (GCF_016772045.2 *Ovis aries* for Ovis + Ovis aries; GCF_001704415.2 *Capra hircus* for
  Capra + Capra hircus; GCA_028583565.1 *Ovis ammon polii* for Ovis ammon + O. a. polii). The FASTA
  archives were not downloaded (`inspected: false`).
- **AnAge build 15, PanTHERIA 1.0, Amniote Life-History DB, EltonTraits 1.0**: full files downloaded to
  `/tmp`, parsed, `byte_size`/`sha256` recorded (`inspected: true`); not committed (169 KB zip,
  2.4 MB, 4.7 MB, 0.6 + 2.2 MB). Row matches are exact at the taxon's rank (binomial for species,
  genus/family/order column for higher taxa); subspecies, the class Gastropoda, suborder Ruminantia and
  tribe Bovini were not matched. The AnAge release notes (release.html in the zip) say 4,671 entries;
  the distributed `anage_data.txt` has 4,645 data rows, which is the count recorded.
- **Paleobiology Database**: `taxa/single.json?name=<name>&show=parent,class` for every taxon;
  taxa with a record under the queried name and `noc` > 0 are listed (51), with the occurrence count.
- **MorphoSource**: public media API full-text query (`q="<name>"&per_page=1`), `pages.total_count`
  recorded for species/subspecies/genera with ≥ 1 hit (29 taxa). Full-text hits may include records
  whose text merely contains the name; the dataset record says so.
- **IUCN Red List**: ids come from Wikidata P627 (24 taxa). IUCN pages and the token-less
  `apiv3.iucnredlist.org/api/v3/taxonredirect/<id>` endpoint return HTTP 403 to non-browser clients, so
  the distributions are `inspected: false` and `integrity.identifier_resolves: false` with the status.
- **Not built**: BOLD (API returned HTTP 403), TimeTree (no machine-readable per-taxon endpoint),
  Open Tree of Life, Phenome10K, FishBase (no fishes in the slice).

## Taxa with few datasets

- Ammonoidea, Ruminantia, Bovini: Paleobiology Database only (no GBIF key at their ranks; no
  species-level trait rows).
- *Ovis ammon hodgsoni*: GBIF occurrence count only (88 records); subspecies are not in trait
  databases, no reference genome, no PBDB record.
- *Heteralocha acutirostris* (huia, extinct 1907): GBIF (250 records), Amniote DB and IUCN only; not
  in AnAge or EltonTraits as distributed; no genome.
- *Oryx beisa*, *Oryx leucoryx*, *Rusa unicolor*, *Rucervus duvaucelii*, *Ovis gmelini*, *Dentalium*,
  *Spirorbis*, *Mammuthus*, *Mammut americanum*: NCBI returned no reference-only assembly.

## Non-animal taxa seen (not built)

- **Foraminifera (Rhizaria), chapter XII**: Orbulina (*O. universa*), Lagena, Astrorhiza,
  *Hastigerina*, *Rhabdammina linearis*, *R. discreta*, Globigerina, *Nummulina antiquior*, Fusulina
  (*F. cylindrica*, *F. Böcki*), *Cornuspira foliacea*, *Operculina complanata*, Miliolinidae/Miliolidae,
  *Triloculina rotunda*, Biloculina, *Pulvinulina menardi*, *Miliolina pulchella*, *M. linnaeana*,
  *Cyclammina cancellata*, *Cristellaria reniformis*, Rotalia, *Discorbina bertheloti*, *Textularia
  trochus*, *T. concava*, Nodosaria/Nodosariae, Orbitolitidae, Acervularidae, Peneroplis, Trochammina.
- **Other protists**: Radiolaria; *Amoeba proteus*, *A. radiosa*, *A. limax*.
- **Plants, chapters XIII–XIV**: hop, honeysuckle, field-convolvulus, woody nightshade (*Solanum
  Dulcamara*), fumitory, tulip, poppy, generic leaf-climbers and tendril-bearers; teasel, thistle,
  sunflower, fir-cones, Norway spruce, larch, palm.
