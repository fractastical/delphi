# thompson-growth-form / ch09-10 — organism reference data

Slice: *On Growth and Form* (1917) Chapters IX (On Concretions, Spicules, and Spicular Skeletons)
and X (A Parenthetic Note on Geodetics), `books/thompson-growth-form/inputs/pg55264.txt` lines
14082–16506; claims `thompson1917-ch09-01` … `thompson1917-ch09-19`, `thompson1917-ch10-01` …
`thompson1917-ch10-06` (25 claims). The chapter footnotes [406]–[494] sit outside the slice's
line range and were not mined for taxa.

Built 2026-10-31 by a cloud agent (`claude-fable-5.1`, branch
`cursor/organisms-thompson-ch09-10-be42`). All identifiers and counts come from live API
responses retrieved on 2026-10-31 (UTC); the response bodies were saved outside the repository
and their byte sizes and SHA-256 checksums are recorded in each dataset distribution.

## Counts

| what | count |
|---|---|
| mentions (`mentions.json`) | 93 (87 located by text line, 6 by claim quote) |
| distinct animal taxa (`taxa/`) | 50 |
| taxa with GBIF backbone `usageKey` | 45 |
| taxa with NCBI Taxonomy id | 49 |
| taxa with Wikidata QID (P225 verified) | 50 |
| taxa with WoRMS AphiaID | 45 |
| taxa with ITIS TSN | 0 (ITIS not queried) |
| dataset records (`datasets/`) | 67 |
| – GBIF occurrence-count records (one per taxon with a GBIF key) | 45 |
| – NCBI reference genome assemblies | 15 |
| – shared authority/database records | 7 (GBIF backbone matches, NCBI Taxonomy, Wikidata, WoRMS, OBIS counts, Paleobiology Database sizes, AnAge build 15) |

Ranks of the 50 taxa: 10 species, 13 genera, 2 families, 1 infraorder, 3 orders, 2 subclasses,
12 classes, 3 subphyla, 4 phyla.

## Taxa not resolved by every authority

- **Vertebrata** (vertebrate animals): no GBIF key. The only GBIF "Vertebrata" is a red-algal
  genus (key 2660342). Resolved to NCBI 7742, Wikidata Q25241, WoRMS 146419. No GBIF count.
- **Octocorallia** (Thompson's "Alcyonaria"): no GBIF key; the backbone hangs octocoral orders
  directly under Anthozoa. NCBI 6132, Wikidata Q132680, WoRMS 1341.
- **Actinopterygii** (Thompson's "bony fish" and generic "fishes"): no GBIF key; the current
  backbone has no class node between Chordata and the ray-finned orders (e.g. `Gadus morhua`
  carries no `class`). NCBI 7898, Wikidata Q127282, WoRMS 10194.
- **Reptilia** ("reptiles"): no GBIF key (pro-parte synonym split among Crocodylia, Squamata,
  Sphenodontia, Testudines) and no NCBI node (NCBI uses Sauropsida 8457, which includes birds).
  Wikidata Q10811, WoRMS 1838 only.
- **Crustacea** ("crustacean shell"): no GBIF key (only a doubtful insect genus of that name).
  NCBI 197562, Wikidata Q25364, WoRMS 1066.
- **Brachyura** ("a crab"): GBIF key 11132538 exists but is a placeholder ranked FAMILY under
  Decapoda with no descendants; its occurrence count (30,320) covers only records identified no
  further than "Brachyura". Noted in the taxon and dataset records.
- Five terrestrial Lepidoptera/birds (*Iphiclides podalirius*, *Cossus cossus*, *Synanthedon
  spheciformis*, *Saturnia pavonia*, *Argusianus argus*) have no WoRMS record (HTTP 204), as
  expected.

## Taxa with no usable dataset

None: every taxon has at least a GBIF occurrence count or OBIS/PBDB rows plus the authority
records. Weakest coverage:

- **Reptilia**: no GBIF or NCBI id, so only OBIS (41.6 M records under AphiaID 1838) and PBDB
  (72,822 fossil occurrences) counts.
- **Vertebrata, Octocorallia, Actinopterygii, Crustacea**: no GBIF count; OBIS and PBDB rows
  only.
- Genome assemblies exist for all 11 species-level taxa except *Argusianus argus* (no assembly in
  NCBI Datasets). For genera (*Mya*, *Rattus*, *Apis*, *Eunicea*, *Alcyonium*, *Farrea*) the
  reference genome of one member species is recorded and the choice is stated in `notes`; no
  assembly exists for *Turritella*, *Hyalonema*, *Euplectella*, *Astrosclera*, *Grantia*,
  *Siphonogorgia*, *Anthogorgia*.
- AnAge build 15 covers 8 taxa (12 rows: Homo sapiens, Gadus morhua, Pleuronectes platessa,
  Felis catus, Oryctolagus cuniculus, Apis mellifera, Mya ×2, Rattus ×4). The distributed
  `anage_data.txt` has 4,646 data rows although the release notes state 4,671 entries; the file
  count is what is recorded.
- Not built: BOLD (v4 API returns HTTP 403 to non-browser clients), MorphoSource (API returned no
  usable body without a key), IUCN Red List (requires an API token not available in this
  environment), TimeTree (no queryable API). These remain candidates for the sponge spicule and
  gastropod shell claims (ch09-08, -09, -10, ch10-02) in a later pass.

## Non-animal taxa seen (no records built)

Protists (Thompson's "Radiolaria", "Foraminifera", "Rhizopods", "Infusoria", Heliozoa):
Radiolaria generally; *Globigerina*, *Hastigerina*, *Entosolenia aspera*, *Astrorhiza limicola*,
*A. arenaria*, arenaceous Foraminifera; *Difflugia*, *Quadrula*, *Amoeba*; *Acanthocystis*,
*Actinosphaerium*, *Clathrulina*, *Raphidiophrys*; *Aulacantha scolymantha*, *Aulonia hexagona*,
*Actinomma arcadophorum*, *Ethmosphaera conosiphonia*, *Cenosphaera favosa*, *C. vesparia*,
*Aulastrum triceros*, *Callimitra carolotae*, *Circoporus sexfurcus*, *C. octahedrus*,
*Circogonia icosahedra*, *Circospathis novena*, *Circorrhegma dodecahedra*, *Dorataspis*,
*Phatnaspis cristata*, *Phractaspis prototypus*, *Collosphaera*, Acantharia, Acanthometridae,
Phaeodaria, Nassellaria; *Dictyocha* (silicoflagellate); Diatoms; ciliate and flagellate
Infusoria; "swarm-spores of various Protists".

Plants and algae: rhubarb, *Begonia*, Urticaceae, Acanthaceae, *Melobesia* and other calcareous
algae, Cacti, *Eulalia japonica*, *Equisetum* (spore elaters), plant vessels/tracheids and
starch-grains generally.

## Ambiguities and decisions

- **Actinomyxidia** (l. 15330–15332) is called "parasitic protozoa" by Thompson, but the
  actinosporean stage belongs to Myxozoa, now placed in Cnidaria. It is therefore kept as an
  animal and resolved to Myxozoa (GBIF 11146120, NCBI 35581, Q134882, WoRMS 146271).
- "corals" → Scleractinia (stony corals), since the passage is about massive skeletons; "coral"
  is otherwise polyphyletic.
- "Monaxonid sponges" → Demospongiae (Monaxonida is an abandoned order).
- "Tetractinellidae" → order Tetractinellida; "Alcyonaria" → Octocorallia; *Papilio podalirius*
  → *Iphiclides podalirius*; *Cossus ligniperda* → *Cossus cossus*; *Sesia spheciformis* →
  *Synanthedon spheciformis*; "Emperor moth" → *Saturnia pavonia*; "Argus Pheasant" →
  *Argusianus argus*; "rabbit" → *Oryctolagus cuniculus*; "rat" → genus *Rattus*; "cat" →
  *Felis catus*; "earthworm" → Lumbricidae; "bee's cell" → genus *Apis*; "our own skeleton" and
  "the human stomach" → *Homo sapiens*; "mammalian tissue/bone/heart" → Mammalia.
- "bony fish", "fishes", "the fish's eye", "otoliths of a fish" → Actinopterygii (all the fishes
  named in the chapter — cod, plaice, Chaetodonts — are teleosts; elasmobranchs are named
  separately).
- "the body-wall of a cylindrical worm" (l. 16437) is too vague to resolve (annelid or nematode)
  and has no record. "a man astray on the prairie" (l. 16490) is a figure of speech, not a
  biological mention. "pearl" is a product, not a taxon (no pearl oyster is named).
- Wikidata has duplicate items with the same P225 for Echinoidea (Q83483 / Q119788843),
  Holothuroidea (Q127470 / Q119788766), Hyalonema, Grantia and Apis; the long-standing item was
  chosen and the alternative is noted in each taxon file.
- `mentioned_in` lists only claim ids (per the README) and includes claims whose claim text,
  label or scope names the taxon even when the verbatim quote does not; 37 taxa are mentioned
  only in the running text, which the validator reports as warnings ("mentioned_in is empty").
  Their locations are in `mentions.json` with file and line numbers.
- Landing pages that refuse non-browser clients are recorded as such in `integrity`
  (`identifier_resolves: false`, HTTP 403): www.gbif.org and paleobiodb.org classic pages. The
  API distributions for the same records resolved with HTTP 200.
- Wikidata rate-limited the first batch of searches (HTTP 429); they were repeated at 2.5 s
  intervals and only successful responses are recorded.
- No `assessment` fields were written anywhere.

## Validator

`node organisms/validate.mjs thompson-growth-form/ch09-10`: 93 mentions, 50 taxa, 67 datasets,
0 errors, 37 warnings (all "mentioned_in is empty", explained above).
