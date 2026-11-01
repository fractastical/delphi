# aristotle-biology / ga01-05: animal taxa in *Generation of Animals*, Books I–V

Slice: `claim-sources/aristotle-biology/inputs/ga.txt` lines 6–505 (Aristotle, *De Generatione
Animalium*, tr. Arthur Platt, 1912) and the 155 claims `aristotle-ga01-*` to `aristotle-ga05-*` in
`claim-sources/aristotle-biology/claims.json`. Built 2026-10-31 by a Cursor agent
(`claude-opus-5.5`). No `assessment` fields were written; nothing was signed or published.

## Counts

| what | count |
|---|---|
| mentions in `mentions.json` | 995 (139 sourced to claim ids, 856 to text lines) |
| claims naming at least one animal in their quote | 83 of 155 (the other 72 are about semen, heat, soul, nature, etc. and name no kind) |
| distinct animal taxa (`taxa/`) | 93 (45 of them named in a claim quote) |
| taxa resolved to GBIF backbone `usageKey` | 92 |
| taxa resolved to NCBI Taxonomy taxid | 91 |
| taxa resolved to Wikidata QID | 93 |
| taxa resolved to GBIF + NCBI + Wikidata | 91 |
| taxa resolved to ITIS TSN / WoRMS AphiaID | 90 / 85 |
| dataset records (`datasets/`) | 158 |
| GBIF occurrence-count records | 93 (one per taxon; every taxon has one) |
| NCBI genome assembly records | 52 (46 chromosome-level, 5 scaffold, 1 contig) |
| shared trait / fossil / status databases | 8 (AnAge, PanTHERIA, Amniote Life-History Database, AVONET, FishBase, SeaLifeBase, PBDB, IUCN via GBIF) |
| taxonomy authority records | 5 (GBIF backbone, NCBI Taxonomy, Wikidata, WoRMS, ITIS) |
| unresolved animal names | 2 (`thrattai`, `trochus`; see below) |

Taxa by rank: species 55, genus 7, family 13, order 5, suborder 1, infraorder 1, class 8,
subclass 1, subphylum 1, phylum 1.

Most-mentioned taxa: *Homo sapiens* 229, Aves 122, Actinopterygii ("fish") 88, *Apis mellifera*
77 (bees, drones, "kings"), *Equus caballus* 41, Insecta 31, *Gallus gallus* 29.

## How mentions were collected

A lexicon of the translation's animal words (one regular expression set per taxon) was run over
every line 6–505 and over each claim's `quote`. A name inside a claim's quote is recorded once per
claim with `source.claim_id` and the quote; every other occurrence is recorded with the file and
line (one entry per taxon per sentence, the quote being that sentence, cut to ≤300 characters on
word boundaries). Lines are whole paragraphs in this text, so `line_start == line_end`. All 995
quotes were checked to be verbatim substrings of the cited line or claim quote. A longer match
wins over a shorter one inside it ("cartilaginous fishes" → Elasmobranchii, not Actinopterygii;
"smooth hound" → *Mustelus*, not dog; "frog-fish" → *Lophius*). Context-checked exclusions:
"bear(s)" as a verb (only "partridges, ravens, sparrows, and bears" counts), "flies" as a verb,
"mola" (a uterine mole), "chick" as any bird embryo (counted under Aves, not the fowl).

## Identifications of Aristotle's kinds

Standard identifications (Platt's notes, D'Arcy Thompson's *Glossary of Greek Fishes*/*Birds*,
Peck's Loeb edition) were used. Where they are not certain the taxon was resolved to a higher rank
or the doubt is written in the taxon's `notes`:

| as written | resolved to | certainty |
|---|---|---|
| erythrinus ("no male has ever been seen") | *Pagellus erythrinus* | uncertain: the Linnaean name derives from it and it is a protogynous hermaphrodite, but a simultaneously hermaphroditic *Serranus* (e.g. *S. scriba*) is also proposed |
| channa | *Serranus cabrilla* | standard |
| belone (bursts to release its young) | genus *Syngnathus* (pipefish) | standard; not the garfish *Belone belone* despite the name |
| "the so-called frog", frog-fish | *Lophius piscatorius* | standard |
| smooth hound | *Mustelus mustelus* | standard (*M. asterias* sometimes preferred) |
| rhini / batus / rhinobates | *Squatina squatina* / Rajidae / *Rhinobatos rhinobatos* | batus resolved only to family |
| a kind of mullet (kestreus) | Mugilidae | species uncertain |
| eel | *Anguilla anguilla* | standard |
| carabi | *Palinurus elephas* | standard |
| poulp / sepia / calamary, squid | *Octopus vulgaris* / *Sepia officinalis* / *Loligo vulgaris* | standard |
| whelks (kêrux) | Buccinidae | uncertain: often the trumpet shell *Charonia* |
| purple-fish | Muricidae | *Bolinus brandaris* / *Hexaplex trunculus*, resolved to family |
| pinnae / pectens / mussels / oysters, limnostrea | *Pinna nobilis* / *Pecten* / *Mytilus* / *Ostrea edulis* | genus-level where Mediterranean species are not fixed |
| testacea | Mollusca | Aristotle's group also includes sea-urchins and ascidians |
| gnats, conopes | Culicidae | uncertain; *empides* may be other Nematocera |
| cantharides | Meloidae | family |
| kings / drones / bees | *Apis mellifera* | "kings" are queens |
| partridge | *Alectoris graeca* | or *A. chukar* in the eastern Aegean |
| hawks | Accipitridae | "hawks of different form" |
| kestrel, raven, crows, rooks, jackdaws, jays | *Falco tinnunculus*, *Corvus corax*, *C. cornix*, *C. frugilegus*, *Coloeus monedula*, *Garrulus glandarius* | jays (kitta) sometimes read as magpie |
| ibis | *Threskiornis aethiopicus* | or the glossy ibis *Plegadis falcinellus* |
| hyena (two-pudenda story) | *Hyaena hyaena* | the story fits the spotted hyena's pseudo-penis better |
| weasel | *Mustela nivalis* | some prefer the beech marten |
| hedgehog | genus *Erinaceus* | Greek hedgehog is *E. roumanicus* |
| elephant | Elephantidae | species not fixed |
| seal | *Monachus monachus* | the only Aegean seal |
| dolphin | *Delphinus delphis* | bottlenose also possible |
| mule, ginnus (dwarf mule) | genus *Equus* | hybrids have no taxon |
| lizards / tortoises / serpents, snakes / vipers | Squamata / Testudinidae / Serpentes / *Vipera* | "lizard" is not a clade |
| scaly reptiles, oviparous quadrupeds | Reptilia | paraphyletic |
| fish | Actinopterygii | Aristotle's "fish" includes selachians unless he says "cartilaginous" |
| man, women, children, Aethiopians, Scythians, Thracians, eunuchs | *Homo sapiens* | |

**Unresolved animal names** (no taxon file):

- `thrattai` (line 479, a vari-coloured fish): no agreed identification (perhaps a shad,
  *Alosa*); left out.
- `trochus` (line 309, said by Herodorus of Heraclea to have two pudenda and impregnate itself):
  a legendary or unidentified animal (the badger has been suggested); left out.

Not taxa and not recorded: Aristotle's grouping words (vivipara, ovipara, sanguinea, bloodless
animals, quadrupeds, bipeds, fissipeds, many-toed, solid-hoofed, cloven-footed, ungulates, footless
animals, birds of prey, scolex, grubs), "satyr"/"satyrism" (a disease named after the mythical
satyr), "metachoera" (runt piglets, counted under *Sus scrofa*), "tragaenae" (intersex goats,
counted under *Capra hircus*), "laiai" (loom weights) and "uria" (rotten eggs).

## Shared datasets and coverage

| dataset id | taxa covered | what was inspected |
|---|---|---|
| `anage-build-15` | 71 | `dataset.zip` (169,150 B) → `anage_data.txt`, 4,645 rows |
| `pantheria-1-0-wr05-aug2008` | 24 | `PanTHERIA_1-0_WR05_Aug2008.txt` |
| `amniote-life-history-database-2015` | 50 | `Amniote_Database_Aug_2015.csv` |
| `avonet-figshare-16586228-v7` | 20 | `AVONET Supplementary dataset 1.xlsx`, sheet AVONET1_BirdLife (11,009 rows) |
| `fishbase-v25-04` | 11 | rfishbase parquet `species` + `families` (v25.04) |
| `sealifebase-v25-04` | 8 | rfishbase parquet `species` (v25.04), species and genera only |
| `pbdb-occurrence-counts-2026-10-31` | 83 | one `occs/list.json?base_name=…&rowcount=true` per taxon |
| `iucn-red-list-via-gbif-2026-10-31` | 43 | GBIF `species/{key}/iucnRedListCategory` per species |
| `gbif-backbone-taxonomy-2026-10-31` | 92 | `species/match` and `species/{key}` per taxon |
| `ncbi-taxonomy-2026-10-31` | 91 | `esearch` per taxon + Datasets taxonomy reports |
| `wikidata-taxon-items-2026-10-31` | 93 | SPARQL on P225 per taxon + `wbgetentities` |
| `worms-aphia-records-2026-10-31` | 85 | `AphiaRecordsByName` per taxon |
| `itis-tsn-lookups-2026-10-31` | 90 | `searchByScientificName` per taxon |

Every downloaded file and API response was checksummed (sha256, byte size) as retrieved; the file
checksums for AnAge, PanTHERIA, Amniote, AVONET and FishBase equal those already recorded by the
Darwin slices. Nothing was vendored into the repo; only the JSON records are committed. Trait rows
are matched on the files' own columns (species by binomial, higher taxa by the Genus/Family/Order/
Class columns), so ranks a file does not carry are not matched, and per-taxon row counts are in each
record's `counts` (`n_rows:<slug>`). Synonyms used for matching: *Corvus monedula* (AVONET's name for
the jackdaw), *Canis lupus familiaris*, *Equus africanus asinus*, *Equus ferus caballus*.

Not used, and why: BOLD, OBIS, Open Tree of Life, TimeTree, MorphoSource and EltonTraits were not
queried in this pass; the IUCN Red List API needs a token, so categories come from the IUCN
checklist as indexed by GBIF (DOI 10.15468/0qnb58).

## Gaps

- **GBIF occurrence counts.** Every taxon has one, but three are not plain backbone counts:
  Reptilia (backbone key 358 is a pro-parte synonym with no records) is the sum of four records for
  Squamata, Testudines, Crocodylia and Rhynchocephalia in one dataset; Actinopterygii (backbone class
  204 has no records attached) and Crustacea (no backbone node; the match returns a DOUBTFUL bee
  genus, rejected) are counted under the Catalogue of Life checklist GBIF offers alongside the
  backbone (`checklistKey=7ddf754f-…`, COL taxa `8VR36` and `KZX8B`). Serpentes' GBIF key 11205692
  is a backbone placeholder, so its 5,490 records are only those matched to the bare name.
  *Canis familiaris* is a GBIF synonym; occurrences are counted under the accepted *Canis lupus
  familiaris* (6164210).
- **Genomes.** Only species-level taxa were queried. No assembly in NCBI for *Mustelus
  mustelus*, *Rhinobatos rhinobatos* or *Loligo vulgaris*. *Canis lupus* has no reference genome
  of its own (the reference for taxid 9612 is the dog), so its record is the best wolf assembly
  among the first 50 reports. *Corvus cornix* uses the reference of the nominate subspecies *C.
  cornix cornix*.
- **Traits.** No trait table for most insects (Acrididae, Cicadidae, Culicidae, Meloidae,
  Siphonaptera, Vespidae, *Vespa crabro*), Buccinidae, Muricidae, Serpentes and Crustacea; these have
  only taxonomy, occurrence and (where present) fossil and genome records. *Corvus cornix* is not
  in AVONET's BirdLife sheet; *Canis familiaris* has no PanTHERIA or Amniote row of its own.
- **Fossils.** PBDB returned 0 for *Corvus cornix*, *Coloeus monedula*, *Pavo cristatus*,
  *Mustelus mustelus*, *Squatina squatina*, *Rhinobatos rhinobatos*, *Vespa crabro*, *Loligo
  vulgaris*, *Octopus vulgaris* and *Palinurus elephas*.
- **IUCN.** Not evaluated: domestic forms, *Homo sapiens*, *Corvus cornix*, *Coloeus monedula*,
  *Apis mellifera*, *Vespa crabro*, *Ostrea edulis*; no record for *Canis familiaris*.

## Identifier caveats

- Wikidata Q536444 (*Pinna nobilis*) currently has P225 "Pinna rudis" but carries this taxon's
  GBIF (4374731) and NCBI (111169) identifiers; the QID is kept.
- Where SPARQL found several Wikidata items with the same P225, the item with a taxon rank was
  kept (Testudinidae Q46360, Elephantidae Q2372824, *Equus* Q27022, *Pecten* Q2704723,
  Echinoidea Q83483), matching the merged taxa from the Darwin and Thompson slices.
- Lineage is from the GBIF backbone with gaps filled from NCBI. The backbone gives fish no class
  (filled as Actinopterygii) and ranks Squamata, Testudines and Crocodylia as classes, so
  *Crocodylus niloticus* has class "Crocodylia" and the snake/lizard taxa "Squamata" or NCBI's
  "Lepidosauria".
- ITIS TSNs are recorded only when exactly one Animalia name record matched; Cicadidae and
  Siphonaptera returned two each and have none.

## Non-animal taxa seen

Plants only, no records built: plants and trees in general, fig and caprifig (*Ficus carica*),
olive and oleaster (*Olea europaea*), vine and the 'capneos' vine (*Vitis vinifera*), mistletoe,
willow, poplar, wheat, corn, beans and leguminous plants, onions, evergreens. Yeast is mentioned
only as a fermenting substance.
