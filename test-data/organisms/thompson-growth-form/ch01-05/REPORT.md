# Thompson, *On Growth and Form* (1917), chapters I–V: animal organism data

Slice `ch01-05` of project `thompson-growth-form`. Built on branch
`cursor/thompson-organisms-ch01-05-7745` on 2026-10-31 by a cloud agent (claude-fable-5.1).

Sources:

- claims: `claim-sources/thompson-growth-form/claims.json`, the 106 rows with `chapter` I–V (fields `claim` and `quote`);
- text: `claim-sources/thompson-growth-form/inputs/pg55264.txt`, lines 980–9881 (CHAPTER I heading to the line
  before CHAPTER VI), with Gutenberg italics markers `_…_`, page markers `{n}` and footnote markers
  `[n]` stripped from quotes.

Scripts (all re-runnable, caching API responses under `/tmp/organisms-cache` and downloads under
`/tmp/organisms-data`; no data file is committed):

| script | purpose |
| --- | --- |
| `scripts/taxa_table.py` | hand-curated table of 141 taxa: slug, name, rank, regex patterns and exclusions, identifier overrides, notes |
| `scripts/build_mentions.py` | scans claims then text, writes `mentions.json` |
| `scripts/resolve_taxa.py` | GBIF backbone (match + search fallback with rank/kingdom hints), NCBI E-utilities (lineage-checked), Wikidata (P225/P31-checked), WoRMS, ITIS; writes `taxa/<slug>.json` |
| `scripts/build_datasets.py` | downloads and checks datasets, writes `datasets/<id>.json`, appends ids to taxa; sections `gbif anage pantheria amniote elton avonet fishbase ncbi worms pbdb` |

## Counts

| what | count |
| --- | --- |
| mentions (`mentions.json`) | 653 |
| mentions sourced from claims (`claim` or `quote` field) | 75, across 45 of the 106 ch. I–V claims |
| mentions sourced from the book text (file/line) | 578 |
| distinct animal taxa (`taxa/*.json`) | 141 |
| taxa named in at least one claim (all have a mention, a taxon file and ≥1 dataset) | 44 |
| taxa that are protists treated as animals by Thompson | 39 |
| taxa resolved above genus (family … kingdom, informal groups) | 53 |

Ranks: 28 species, 1 subspecies, 59 genera, 15 families, 1 superfamily, 11 orders, 1 superorder,
11 classes, 2 subphyla, 1 infraphylum, 7 phyla, 1 kingdom (Protozoa), 3 informal groups
(Pisces, Rhizopoda, Ungulata).

Most-mentioned taxa: Homo sapiens 124, Aves 37, Pisces 24, Anura (tadpoles) 19, Amoeba 16,
Pleuronectes platessa 15, Lagena 15, Artemia 14, Foraminifera 14, Ciliophora (Infusoria) 14,
Trypanosoma 14, Rana 11, Crustacea 10.

### Resolution to authorities (of 141 taxa)

| authority | taxa with an identifier | notes |
| --- | --- | --- |
| GBIF backbone (`gbif_usage_key`) | 129 | 12 without: Crustacea (only a doubtful homonym genus), Pisces, Selachii, Reptilia, Vertebrata, Ungulata, Pterosauria, Dinornithiformes, Papilionoidea, Rhizopoda, Radiolaria and Trichomastix (both only as insect synonyms); Selachii note records Elasmobranchii (key 121) as nearest backbone taxon. Trichomonas is recorded under GBIF's doubtful, unplaced genus 8265662 (the usage its occurrences are indexed under) |
| NCBI Taxonomy (`ncbi_taxid`) | 122 | 19 without: no node for Reptilia, Turbellaria, Radiolaria, Heliozoa, Protozoa, Pisces, Rhizopoda, Ungulata, Pterosauria, Trichomastix, Meganisoptera and the fossil/benthic foram genera Nodosaria, Ramulina, Rotalia, Sagrina, Thurammina, Tintinnus; Lagena and Micromonas left null because NCBI's only homonyms are an oomycete and a green alga; Crustacea→Pancrustacea, Marsupialia→Metatheria, Callitrichidae→Callitrichinae, Choanoflagellatea→Choanoflagellata recorded as such |
| Wikidata (`wikidata_qid`) | 140 | only Micromonas (Borrel, 1902) has no item (the Wikidata genus is the alga) |
| ITIS (`itis_tsn`) | 91 | |
| WoRMS (`worms_aphia_id`) | 53 | marine taxa only; Radiolaria and Tintinnus ids are unaccepted names, the valid AphiaID is noted |

Every identifier was obtained from the authority's API and, for GBIF, Wikidata and NCBI, verified
(canonical name, rank, kingdom/lineage) before being recorded. Where a name was a synonym the
accepted taxon is recorded and the synonym kept in `names_as_written`/`notes` (Epeira→Araneus,
Inachus scorpio→I. dorsettensis, Felis minuta→Prionailurus bengalensis, Salmo fario→S. trutta,
Ascaris megalocephala→Parascaris, Globiocephalus→Globicephala, Rheophax→Reophax).

### Dataset records built (`datasets/*.json`: 186)

| record(s) | taxa covered | what was checked |
| --- | --- | --- |
| `gbif-occurrences-<slug>-2026-10-31` ×129 | one per taxon with a GBIF key | `occurrence/search?taxonKey=<key>&limit=0`; URL, `count`, sha256/bytes of the JSON, `retrieved_at`. Total 3 399 810 372 records; Micromonas = 0 |
| `anage-build-15` | 58 | AnAge build 15 `dataset.zip` (169 150 B) downloaded, `anage_data.txt` 4645 rows parsed; per-taxon row counts; DOI 10.1093/nar/gks1155 |
| `pantheria-1-0` | 22 | `PanTHERIA_1-0_WR05_Aug2008.txt` (2 359 096 B), 5416 rows; DOI 10.1890/08-1494.1 |
| `amniote-life-history-database-2015` | 33 | `Amniote_Database_Aug_2015.csv` (4 728 122 B), 21 322 rows; DOI 10.1890/15-0846R.1 |
| `eltontraits-1-0` | 26 | BirdFuncDat + MamFuncDat (figshare files 5631081, 5631084); DOI 10.1890/13-1917.1, CC0 |
| `avonet-2022` | 8 | figshare file 34480856 (21.5 MB xlsx), sheet `AVONET1_BirdLife` 11 009 rows; DOI 10.1111/ele.13898 |
| `fishbase-v25-04` | 7 | rfishbase parquet mirror (`species.parquet` 36 132 rows, `families.parquet` 664 rows) plus FishBase species pages; licence left null (not machine-readable) |
| `ncbi-genome-<accession>` ×49 | 49 (27 species-level, 22 genus-level) | NCBI Datasets v2 `dataset_report?filters.reference_only=true`; accession, assembly stats, landing page checked. Genus-level records name the species actually returned in `notes` |
| `worms-aphia-records-2026-10-31` | 53 | one `AphiaRecordByAphiaID` response per marine taxon (status, rank, valid id); DOI 10.14284/170 |
| `pbdb-taxa-2026-10-31` | 16 | PBDB `taxa/single.json?show=size,app` for fossil/fossil-rich taxa (n_occurrences, first/last appearance); 222 792 occurrences in total |

All `integrity.identifier_resolves` flags are true (doi.org identifiers judged by their redirect
status; esapubs directory pages return 403 so those records use the DOI URL as identifier). All
downloaded files have `sha256` and `byte_size`; none is committed (largest 21.5 MB, AVONET).

Coverage: 138 of 141 taxa have at least one dataset record; 106 have a GBIF count **and** at least
one trait/reference dataset.

### Taxa with no dataset at all (3, all text-only mentions, none required by a claim)

| taxon | why |
| --- | --- |
| Papilionoidea (butterflies) | not in the GBIF backbone (no superfamily rank there); not marine, not fossil-indexed; no species-level trait DB applies to a superfamily |
| Rhizopoda | obsolete informal group; only a Wikidata item exists, no GBIF/NCBI/WoRMS/PBDB taxon |
| Trichomastix | obsolete parabasalid genus (now Monocercomonas/Tetratrichomonas); GBIF's only "Trichomastix" is an insect synonym; no NCBI node |

### Taxa with a GBIF occurrence count only (23)

Acrididae, Actinophrys, Actinosphaerium, Amoeba, Arthropoda, Astacidae, Branchipus, Chilomonas,
Choanoflagellatea, Ciliophora, Codosiga, Dinenympha, Distigma, Euglypha, Heliozoa, Lucanidae,
Micromonas (count 0), Protozoa, Siphonaptera, Testudines, Trichodina, Trypanoplasma, Vorticella.
These are freshwater/terrestrial protists and arthropod groups outside the vertebrate trait
databases, WoRMS (marine) and the PBDB; genome records were only built for species and genera and
none of these genera has a reference assembly in NCBI Datasets. Of these, Actinophrys, Amoeba,
Ciliophora, Heliozoa, Protozoa and Vorticella are named in claims; each still meets the
"at least one dataset record" requirement via its GBIF count.

### Taxa with a trait/reference dataset but no GBIF count (9)

Crustacea, Dinornithiformes, Pisces, Pterosauria, Radiolaria, Reptilia, Selachii, Ungulata,
Vertebrata — no GBIF backbone key (see above); covered by AnAge/PanTHERIA/Amniote
(class/group filters), WoRMS, PBDB or NCBI genomes instead.

## Non-animal taxa seen (not built)

Plants, fungi, bacteria and viruses named in chapters I–V, with first line in `pg55264.txt`:
Spirogyra (1331; 10 mentions), Protococcus (1389), Achlya (8865), *Lupinus albus* (4512),
Equisetum (4019), Tradescantia (8550), maize (4422), bean root (3970), pea (3496, Mendel's/Galton's
peas), pumpkins and melons (1549), a British Columbian pine-tree (1585), trees generally;
yeast/Saccharomyces (2777; 10 mentions), moulds (1191); bacteria generally (2203; 12 mentions),
*Bacillus anthracis* (2216), Micrococcus / *M. progrediens* (2199, 2278), Spirillum (2475),
*Spirochaete pallida* (2484), the tobacco-mosaic "filter-passer" (2208); diatoms (2430) and desmids
(7781). Pollen grains (2442, Brownian motion) and seeds (9294) are plant parts.

Borderline cases included as animals (Thompson's usage), with modern placement in `lineage`/`notes`:
Foraminifera and the foram genera (Rhizaria), Radiolaria, Gromia and Euglypha (Cercozoa), Amoeba
(Amoebozoa), Heliozoa/Actinophrys/Actinosphaerium (Stramenopiles), Ciliophora, Noctiluca
(dinoflagellate), Chilomonas (cryptomonad), Distigma (euglenid), trypanosomatids and bodonids,
parabasalids and oxymonads, choanoflagellates. Micromonas mesnili (a flagellate) is included;
the green alga Micromonas is not what Thompson means.

## Ambiguities and judgement calls

- **Homo sapiens**: "man", "men", "boy(s)", "girl(s)", "child(ren)", "infant", "baby", "woman/women",
  "human", "bipedal" all counted; "man kann" (German) excluded. 124 mentions, by far the most.
- **Common-name groups** resolved to the best modern rank, often above species: "fish" → Pisces
  (informal), "birds" → Aves, "tadpoles" → Anura, "frog"/"Rana" → Rana, "worm(s)" → Annelida only
  where it means fissiparous worms (silkworm, Fezzan-worm, Ascaris, "worm or insect" excluded),
  "flies"/"gnats" → Diptera only as nouns ("dragon-flies" → Meganisoptera; the verb "to fly" excluded),
  "a sponge" → Porifera ("sponge-work" excluded), "lamb" → Ovis aries (the physicist A. B. Lamb excluded),
  "horse" → Equus caballus ("horse-power" excluded), "whale" → Cetacea, "elephant" → Elephantidae,
  "shark" → Selachii, "turtle" → Testudines, "serpents" → Serpentes, "saurians"/"reptiles" → Reptilia,
  "moa" → Dinornithiformes, "pterodactyl" → Pterosauria, "crayfish" → Astacidae, "marmoset" → Callitrichidae,
  "sparrow" → Passer domesticus, "pigeon" → Columba livia, "oyster" → Ostrea edulis.
- **Artemia**: Thompson's *A. salina*, *A. milhausenii* and *A. (Callaonella) jelskii* are salinity
  morphs; resolved to the genus.
- **GBIF rank oddities** kept as given by the backbone and noted: Brachyura, Marsupialia and
  Serpentes ranked FAMILY; Testudines CLASS; Cetacea ORDER; Foraminifera and Heliozoa phyla under
  Chromista; Protozoa a kingdom. GBIF DOUBTFUL flags noted for Actinosphaerium, Dinenympha, Lagena,
  Micromonas, Trichomonas (unplaced genus under Animalia; modern lineage set by hand), Trypanoplasma,
  Trypanosoma.
- **Homonyms**: Lagena (GBIF default and NCBI = oomycete) resolved by restricting the GBIF search to
  Foraminifera, NCBI left null; Micromonas (NCBI/Wikidata = green alga) left null; Crustacea,
  Radiolaria, Trichomastix GBIF homonyms rejected.
- **Wikidata Globicephala** Q459616 was set by hand: its P225 statement currently reads
  "Globicephala melas" although the item is the genus.
- **Canis familiaris**: GBIF treats it as a synonym of *C. lupus familiaris*; accepted key and
  NCBI subspecies taxid recorded.
- **Dataset filters** for groups: AnAge "Vertebrata" counts Phylum Chordata rows only; Selachii =
  shark orders, Ungulata = Perissodactyla + Artiodactyla, Pisces = fish classes, Serpentes = snake
  families, Marsupialia = marsupial orders. PanTHERIA includes the domestic cattle/cat/sheep etc.
  but not the dog.
- **Genus-level genome records** (22) describe the first reference assembly returned for the genus;
  the species is named in `notes`, and `total_count` of reference assemblies in the genus recorded.
- **Spelling in the text**: "Bonel" for Borrel (Micromonas mesnili), "Rheophax" for Reophax,
  "Globiocephalus" for Globicephala, "Trichodina pedicidus" for T. pediculus.

Nothing in `claim-sources/thompson-growth-form/claims.json`, any assessment or any nanopublication was modified,
and nothing was published. No `assessment` fields were written.
