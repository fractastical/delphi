# darwin-origin / ch09-10 — Chapters IX–X (geological record; geological succession)

Text: `books/darwin-origin/inputs/pg1228.txt` lines 8461–10411. Claims: `darwin1859-ch09-01` … `darwin1859-ch10-18`
(32 claims). Built 2026-10-31 by a cloud agent (`claude-fable-5.1`, branch
`cursor/organisms-darwin-ch09-10-00c8`). All identifiers and counts below were retrieved live from the
authorities' APIs on 2026-10-31; every API response used is checksummed in the dataset records.

## Counts

| item | count |
|---|---|
| mentions (`mentions.json`) | 102 (99 from the book text, 3 from claim statements) |
| distinct animal taxa (`taxa/`) | 47 |
| resolved to GBIF backbone `usageKey` | 35 |
| resolved to NCBI Taxonomy id | 42 |
| resolved to Wikidata QID (verified via P225) | 47 |
| resolved to Paleobiology Database taxon number | 45 |
| resolved to ITIS TSN | 36 |
| resolved to WoRMS AphiaID (marine taxa only queried) | 13 |
| resolved to all four of GBIF + NCBI + Wikidata + PBDB | 31 |
| datasets (`datasets/`) | 82 |
| – GBIF occurrence counts (one per taxon with a GBIF key, nonzero) | 34 |
| – PBDB occurrence queries (extinct taxa + fossil-discussed and higher taxa) | 37 |
| – NCBI genome assemblies (reference where one exists) | 9 |
| – shared trait databases (AnAge build 15; PanTHERIA 1.0) | 2 |
| taxa with no dataset | 1 (`chthamalinae`) |
| wholly extinct taxa (`"extinct": true`) | 9 |

Only three claims in this slice name an animal taxon in their statement (`darwin1859-ch10-08`
ammonites; `darwin1859-ch10-18` marsupials and edentates); the chapters are about the record itself,
so almost every mention is sourced to book lines. `mentioned_in` is therefore empty for 44 taxa
(validator warnings); the text positions are kept in the extra `mention_lines` field and in
`mentions.json`.

## How names were resolved

- GBIF: `species/match?name=…&rank=…&kingdom=Animalia&verbose=true`. Three keys were taken from the
  match API's `alternatives` list because the top match was a homonym or a `HIGHERRANK` fallback, and
  confirmed with `species/<key>`: Lingula → 2252392 (Bruguière 1791, Brachiopoda), Trigonia → 3247984
  (Bruguière 1789, Bivalvia), Reptilia → 358 (now a pro-parte synonym in the backbone). These are
  flagged `matchType: "MANUAL_FROM_ALTERNATIVES"` in the taxon's `resolution.gbif`.
- NCBI: `esearch` then `esummary` to confirm the scientific name and rank.
- Wikidata: `wbsearchentities`, then `wbgetentities` and acceptance only of an item whose P225 (taxon
  name) equals the queried name; for `Sus` the genus item (Q10798) was found with
  `haswbstatement:P225=Sus` because plain search returns only the domestic pig.
- PBDB: `taxa/single.json?name=…&show=class`; `pbdb_taxon_no` is the numeric part of `oid`.
- WoRMS (`AphiaRecordsByName`) for marine taxa; ITIS `searchByScientificName`, accepted only when
  exactly one exact-name hit existed (Tapirus had two; the valid one, 926066, was chosen after
  `getFullRecordFromTSN` showed 624930 is invalid).

## Identifier caveats (recorded in each taxon's `notes`)

- Not in the GBIF backbone (null `gbif_usage_key`): Simiiformes, Teleostei, Crustacea, Ammonoidea,
  Dinornithiformes, Ruminantia, Vertebrata, Marsupialia (GBIF has only a doubtful family-rank entry),
  Folivora, Vermilingua, Holostei, Chthamalinae (GBIF fuzzy-matches it to Chthamalidae).
- Not in NCBI Taxonomy: Trilobita, Ammonoidea, Reptilia (no node), Sessilia, Chthamalinae.
  NCBI ids recorded with a caveat: `canis-familiaris` → 9615 (*Canis lupus familiaris*, subspecies);
  `crustacea` → 197562 (Pancrustacea, under which NCBI files the name); `marsupialia` → 9263
  (Metatheria, likewise).
- GBIF status caveats: Canis familiaris 5219200 and Xenarthra 10998477 are synonyms in the backbone;
  Crocodylia 11493978 is ranked as a class there; Reptilia 358 is a pro-parte synonym and its
  occurrence count is 0, so no GBIF dataset was built for it.
- PBDB: `taxa/single?name=Chiton` returns the class Polyplacophora, so Chiton has no PBDB number and no
  PBDB occurrence dataset; Simiiformes (txn 95857) is a subjective synonym of Anthropoidea (txn 40840);
  Sessilia has a PBDB taxon but 0 occurrences under `base_name`, so no dataset was built.
- WoRMS: Chthamalinae (106076) is "unaccepted" (valid name Chthamalidae); Sessilia (106033) is
  "uncertain".

## Ambiguous or interpretive resolutions

- **"Mastodon" / "mastodons" → Mammut.** *Mastodon* Cuvier 1817 is a junior synonym of *Mammut*
  Blumenbach 1799, which is what the nomenclature resolves to; but Darwin's La Plata "Mastodon" is now
  *Notiomastodon platensis* (Gomphotheriidae) and Falconer's Siwalik mastodons are gomphotheres and
  stegodonts. Treat the Mammut datasets as nomenclatural, not biogeographic, matches.
- **"fossil horse" / "former horse" / "tooth of a horse" → genus Equus** (separate slug `equus`),
  distinct from the living horse (`equus-caballus`). Owen named the tooth *Equus curvidens*; modern
  placements vary (*Equus (Amerhippus)*, *Hippidion*).
- **"Ganoid fishes" → Holostei.** Agassiz's Ganoidei is obsolete and polyphyletic; Holostei (gars,
  bowfin) are the living freshwater "ganoids" most literally meant, but sturgeons, paddlefish and
  bichirs were also ganoids.
- **"Edentata" → Xenarthra**; **"armadillo" → Cingulata** (the "gigantic pieces of armour" are
  glyptodonts, also Cingulata); **"sloth" → Folivora**; **"anteater" → Vermilingua**.
- **"monkey" → Simiiformes**; **"Whale family" → Cetacea**; **"Batrachians" → Amphibia**;
  **"Ruminants" → Ruminantia**; **"pig" → Sus**, **"camel" → Camelus**; **"crocodile"** (Falconer's
  Siwalik crocodile) **→ Crocodylia**; **"extinct and gigantic birds of New Zealand" →
  Dinornithiformes**.
- **"Nautilus", "Lingula" among "the most ancient Silurian animals"** are resolved to the living genera
  as written, although the Palaeozoic forms are now placed in other nautiloid/lingulid genera.
- **"Trigonia"**: the surviving Australian species is now *Neotrigonia*; resolved to the fossil genus
  Darwin named. Three Wikidata items are named Trigonia; Q38335712 is the mollusc.
- **"sessile cirripedes" → order Sessilia** (WoRMS now prefers Balanomorpha).
- Darwin's **"Chthamalinæ"** is his own 1854 subfamily; it resolves only to Wikidata and WoRMS
  (unaccepted) and has no GBIF, NCBI, PBDB or ITIS record, hence no dataset.

## Mentions deliberately not made into taxa

Generic or non-taxonomic animal references in the text: "shells", "sea-shells", "land-shells"
(including Lyell's Carboniferous land shell from Nova Scotia and the land-shells of Madeira),
"brackish-water shells of the Aralo-Caspian Sea", "marine productions" clothing boulders,
"fossil-fish"/"fish"/"older Fish" (paraphyletic; the teleosts and ganoids are covered),
"Pachyderms" (Cuvier's obsolete, polyphyletic order), "Invertebrata" (not a taxon), "extinct
monsters", "anomalous monsters", "fauna". Darwin's own book title *Coral Reefs* (line 9351) names
corals only as a title and was not treated as a mention. Agassiz's embryological comparison and the
imaginary genera of the chapter IV diagram name no real taxa.

## Non-animal taxa seen

None are named at species or genus level in these chapters. Non-animal references are generic:
"vegetation" on cliffs, "great fossilised trees" and "root-bearing strata" of the Nova Scotia
Carboniferous (line 8978–8984), "plants" that propagate rapidly, dominant plants producing varieties,
"native plants" of Great Britain and New Zealand, and "flora" (Eocene flora, line 10153). The
"phosphatic nodules and bituminous matter" in azoic rocks are not organisms.

## Datasets: what was and was not done

- GBIF occurrence counts: `occurrence/count?taxonKey=<usageKey>`; the saved body is the bare integer.
- PBDB: two distributions per taxon, `occs/list.json?base_name=<name>&show=coords&limit=1` (sample
  record) and `…&limit=1&rowcount` (count from `records_found`). Built for the nine extinct taxa, for
  the fossil-discussed genera (Equus, Chthamalus, Nautilus, Lingula, Crocodylia, Cetacea, Simiiformes,
  Holostei, Teleostei) and for the higher taxa, which otherwise would have had no dataset. Vertebrata
  (273,749 records) and Trilobita (56,574) are large; only the first record was fetched.
- NCBI genomes: NCBI Datasets v2 `genome/taxon/<taxid>/dataset_report?filters.reference_only=true`
  for the six species-level extant taxa and for one representative species of three genera
  (*Lingula anatina*, *Nautilus pompilius*, *Lepidosiren paradoxa*; the dataset `role` says so).
  *Columba oenas*, *Nautilus pompilius* and *Lepidosiren paradoxa* have no RefSeq reference, so the
  current GenBank assembly was recorded. The assembly archives themselves were not downloaded
  (`inspected: false` on the FASTA download URL); only the metadata report was inspected.
- AnAge build 15 (`dataset.zip`, 169,150 bytes) and PanTHERIA 1.0 (2,359,096 bytes) were downloaded,
  row-counted and checksummed; neither file is committed (PanTHERIA exceeds 1 MB; both are
  reproducible from the recorded URL and sha256).
- Not built: AVONET (multi-MB xlsx), Amniote Life-History DB, EltonTraits, FishBase, TimeTree,
  MorphoSource (not inspected in the time available), IUCN Red List (API requires a token), BOLD
  (the v4 public API returned HTTP 403 from this environment).

## Validator

`node organisms/validate.mjs darwin-origin/ch09-10`: 0 errors. Warnings: 44 × `mentioned_in is empty`
(explained above) and 1 × `taxa/chthamalinae.json: no dataset` (explained above).
