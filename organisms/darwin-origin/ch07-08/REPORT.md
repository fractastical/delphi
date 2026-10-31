# darwin-origin / ch07-08 (Chapters VII Instinct, VIII Hybridism; pg1228.txt lines 6370–8460)

Vendored by a cloud agent (`claude-fable-5.1`, branch `cursor/organisms-darwin-ch07-08-a7e1`) on
2026-10-31. All identifiers, counts and checksums below were retrieved live from the named APIs
on that date; nothing was typed from memory except vernacular names and the resolution notes.

## Counts

| what | n |
|---|---|
| mentions (`mentions.json`) | 325 |
| … sourced to a claim (`source.claim_id`) | 19, across 12 claims (ch07-03, -04, -05, -07, -08, -09, -10, -11, -12, -13, -14; ch08-09) |
| … sourced to text lines (`source.file` + lines) | 306 |
| distinct animal taxa (`taxa/`) | 58 (31 species, 15 genera, 7 families, 1 superfamily, 2 orders, 2 classes) |
| resolved to GBIF backbone `usageKey` | 58 / 58 |
| resolved to NCBI Taxonomy id | 58 / 58 |
| resolved to Wikidata QID (verified via P225 taxon name) | 58 / 58 |
| resolved to ITIS TSN (from Wikidata P815, verified against ITIS `getScientificNameFromTSN`) | 58 / 58 |
| resolved to WoRMS AphiaID (from Wikidata P850, verified against WoRMS REST) | 27 / 58 |
| resolved to Open Tree Taxonomy `ott_id` (TNRS, exact non-approximate match) | 58 / 58 |
| dataset records (`datasets/`) | 93 |
| … GBIF occurrence-count records (one per taxon) | 58 |
| … NCBI reference-genome records | 28 (27 species-level taxa; the dog/wolf share one RefSeq assembly) |
| … shared databases (one record per database for the slice) | 7: AnAge build 15 (38 taxa), Amniote Life-History DB Aug 2015 (33), EltonTraits 1.0 (31), PanTHERIA 1.0 (14), AVONET v7 (17), Paleobiology Database occurrence counts (46), Open Tree of Life TNRS (58) |

Every taxon has at least a GBIF count and an Open Tree id; 53 of 58 have at least one further dataset.

## Validator

`node organisms/validate.mjs darwin-origin/ch07-08` → 0 errors, 49 warnings. All 49 warnings are
`mentioned_in is empty`: those taxa are named in the chapter text but not inside any claim's
quote/claim text or quoted line span, so `mentioned_in` (which lists claim ids) is correctly empty.
Their text positions are in `mentioned_at_lines` in each taxon file and in `mentions.json`.

## Method

1. Text lines 6370–8460 were read in full; every animal name (scientific, vernacular, breed) was
   listed and mapped to a taxon. Mentions were then located mechanically (longest-name-first match
   with letter boundaries) over the text and over the `label`, `claim` and `quote` of the 30 slice
   claims. A text line that falls inside a claim's `lineStart–lineEnd` is sourced to that claim.
   A handful of generic words were excluded where they do not denote the mapped taxon (e.g. "bees"
   in the parasitic-bee passage, "hen ostriches", "this bee" = Melipona, "domestic cattle as they
   may be called" = aphides). `names_as_written` keeps Darwin's spelling (Sphegidæ, ichneumonidæ,
   Cervulus vaginalis, Formica (Polyerges) rufescens, F. flava, Cryptocerus, Anomma …).
2. Resolution: GBIF `species/match?name=…&kingdom=Animalia&verbose=true`, NCBI `esearch` +
   `esummary` (taxonomy), Wikidata `wbsearchentities` + `wbgetentities` (P225 checked against the
   query name; P815/P850 then verified at ITIS/WoRMS). Raw responses were saved outside the repo.
   Six GBIF matches had to be overridden manually from a backbone search (see "Ambiguous").
3. Datasets: GBIF `occurrence/count?taxonKey=`; NCBI Datasets v2
   `genome/taxon/<taxid>/dataset_report?filters.reference_only=true` for species-level taxa;
   AnAge, PanTHERIA, EltonTraits, Amniote DB and AVONET were downloaded to `/tmp`, hashed
   (`sha256`, `byte_size` recorded) and parsed to count rows for our taxa by rank-appropriate
   column; PBDB `occs/list?base_name=…&rowcount=true` and Open Tree `tnrs/match_names` were
   queried once per taxon / once for all taxa. No file over 1 MB is committed (the slice is ~0.8 MB
   of JSON; the downloaded sources, 0.17–21.5 MB, stay out of the repo). `inspected: true` is set
   only where the body was saved and hashed; the NCBI assembly download packages are listed with
   `inspected: false`.

## Non-animal taxa seen (not built)

Plants: dock-plant (Rumex), cabbage, Scotch fir, heath, Leguminosae, primrose and cowslip,
red and blue pimpernels (Anagallis arvensis, A. coerulea), Crinum capense, C. revolutum, Lobelia,
Hippeastrum (incl. H. aulicum), Passiflora, Verbascum (nine species; yellow/white varieties),
Pelargonium, Fuchsia, Calceolaria (C. integrifolia, C. plantaginea), Petunia, Rhododendron
(R. ponticum, R. catawbiense), Dianthus, Silene, Nicotiana (N. acuminata, N. glutinosa, common
tobacco), Mirabilis jalapa and M. longiflora, Matthiola annua and M. glabra, pear, quince, apple,
apricot, peach, plum, gooseberry, currant, Robinia (three species), Sorbus, maize (dwarf yellow and
tall red varieties), gourd (three varieties), hollyhock. Algae: "sea-weeds or Fuci" (Fucus,
Thuret's experiments). No fungi or microbes are named in these chapters. Humans (Mozart, "man",
"savages") were not recorded.

## Taxa with no usable dataset beyond the GBIF count and Open Tree id

- `coccoidea` (scale insects, "cocci"): GBIF indexes occurrences only at standard Linnaean ranks,
  so the superfamily key returns 0 occurrences (recorded as such, flagged in the count description);
  PBDB does have 100 occurrences for Coccoidea, so the PBDB record covers it.
- Only a GBIF count and an OTT id (5 taxa): `eciton`, `melipona`, `myrmecocystus`,
  `polyergus-rufescens`, `tachytes`. The trait databases used are vertebrate-only, PBDB has no
  occurrences for them, genus-level taxa were not queried for genomes, and NCBI lists no
  reference assembly for Polyergus rufescens.
- No PBDB fossil occurrences (count 0, so not listed on the PBDB record; 12 taxa): the five
  above plus `anser-cygnoides`, `corvus-cornix`, `formica-sanguinea`, `lasius-flavus`,
  `phasianus-versicolor`, `salmo-salar`, `serinus-canaria`.
- Species without a reference genome: `polyergus-rufescens`, `phasianus-versicolor` (NCBI
  `reference_only` report empty).

## Databases not used, and why

- IUCN Red List: the v4 API requires a personal token; no record built rather than guess.
- BOLD: the v4 public API returned HTTP 403 for this client and v5 requires an API key.
- TimeTree: no programmatic API; nothing was downloaded so nothing is recorded.
- MorphoSource, Phenome10K: require API keys / manual search; skipped.
- FishBase (for Salmo salar): the rOpenSci mirror returned an empty body; skipped.

## Ambiguous or judgement calls

- GBIF match API returned the wrong rank/kingdom for six bare names; keys were taken instead from
  a backbone search restricted to the right higher taxon and recorded with
  `gbif_match_type: "backbone search (manual override)"`: Cephalotes (match gave Animalia),
  Troglodytes (gave Chordata), Coccoidea (gave a fungal genus; superfamily key 1632 used), Pieris
  (two backbone genera; accepted Pieris Hübner 1819 used, Wikidata links the doubtful duplicate
  7236092), Bombus (NCBI returned genus and subgenus; genus 28641 used), Aves (match OK, NCBI/
  Wikidata disambiguated).
- "Cryptocerus" → Cephalotes (junior synonym); "Anomma" → Dorylus (now a subgenus);
  "Formica (Polyerges) rufescens" → Polyergus rufescens; "F. flava" → Lasius flavus;
  "Cervulus vaginalis / Reevesii" → Muntiacus muntjak / M. reevesi; "P. torquatus" is recorded
  under Phasianus colchicus (now a subspecies); "Melipona domestica" → genus Melipona;
  "Tachytes nigra" (Fabre) → genus Tachytes; "Sphegidæ"/"sphex" → family Sphecidae s.l.
- Vernacular groups resolved above species: "aphides" → Aphididae; "cocci" → Coccoidea;
  "caterpillar(s)" → Lepidoptera; "wasp-combs"/"queen-wasp" → Vespidae; "foxes" → Vulpes;
  "jackals" → Canis aureus (Darwin names no species; recorded with a note); "the cat genus"/"cat"
  → Felis; "deer" → Cervidae; "hares" → Lepus; "finches" → Fringillidae; "thrush" (South American
  and British) → Turdus; "wrens (Troglodytes)" → genus, "Kitty-wrens" → T. troglodytes;
  "American cuckoo" → Coccyzus; "ostrich"/"American ostrich" → Rhea americana (Darwin's own
  Beagle observations; the header's generic "ostrich" is mapped here too); "Gallinaceæ"/
  "gallinaceous birds" → Galliformes; generic "birds" → Aves; "neuter/sterile/social insects" →
  Insecta (only those phrases, not every "insect").
- Domestic forms: all dog breeds → Canis familiaris (GBIF species; NCBI 9615 = Canis lupus
  familiaris; Open Tree matches the subspecies ott 247333); tumbler pigeons → Columba livia;
  fowls/chickens/hens/poultry → Gallus gallus; cattle/oxen/bulls/cows → Bos taurus; "humped Indian
  cattle" → Bos indicus; domestic rabbits → Oryctolagus cuniculus; the "common goose" → Anser anser.
- The NCBI reference assembly for taxid 9612 (Canis lupus) is the dog assembly
  GCF_011100685.1; one record lists both `canis-familiaris` and `canis-lupus`.
- Not recorded as taxa: "parasitic bees" (cuckoo bees span several Apidae genera; lines
  6716–6721), the generic "bee(s)" outside the hive-bee passages, "mule"/"hinny" (hybrids; noted
  on the Equus records), "ground-birds", "articulate animals", "animals", "insects" in the
  pollination sense.
- AnAge `release.html` states 4,671 entries for build 15; the distributed `anage_data.txt` has
  4,645 rows, and the release notes ask for the 2013 HAGR paper to be cited, so that DOI is used.
- AVONET was checked by presence of species names among the workbook's shared strings (the xlsx
  was not parsed sheet by sheet); genus counts there are counts of distinct binomials.
- Trait-database row counts for genus/family/order/class taxa (e.g. 10,011 EltonTraits rows for
  Aves) describe coverage of the group, not of a single Darwin taxon.
