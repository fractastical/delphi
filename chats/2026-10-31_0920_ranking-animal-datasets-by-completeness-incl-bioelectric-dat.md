# Ranking animal datasets by completeness (incl. bioelectric data)

- **Started:** 2026-10-31 09:20 UTC-4 (EDT)
- **Last activity:** 2026-10-31 10:04 UTC-4 (EDT)
- **User messages:** 4
- **Subagents:** 0
- **Transcript ID:** `3af5b1b0-11d8-4ed7-a9a6-cbf60c36c714`

## Conversation

### 2026-10-31 09:20 — Turn 1 (User)

> i wonder if we can go through all animal datasets and then rank by completenes including esp. when it comes to dna sequencing, bioelectric data,e tc

**Assistant:**

I'll start by looking at what the `organisms/` data actually contains so the ranking reflects real fields.

I need to rank animal datasets by completeness, looking at DNA sequencing and bioelectric data coverage, so I'll start by exploring the organisms directory to see what's available.

This feels like a soft request rather than a pure question, so rather than just giving an assessment, I think it's worth actually computing a completeness ranking across the animal datasets since that's cheap and safe to do in a scratch location.

I should check the ontology for any existing completeness or reliability assessment convention before building my own. Then I want to construct a per-taxon coverage matrix across occurrence records, fossils, genomes, barcodes, traits, morphology, phylogeny, IUCN status, and note that "bioelectric data" essentially doesn't exist for animals broadly — the closest real-world analogs would be things like NeuroElectro or Allen Cell Types, but coverage there is sparse and not organized by taxon the way the other datasets are.

Yes, and most of the pieces are already there. Here's what I found from `organisms/merged/` (782 taxa, 1,372 dataset records) and a quick prototype ranking I ran in a scratch script (nothing written to the repo).

**What coverage exists today, by data category**

| category | dataset records | taxa covered | species-rank taxa covered (of 273) |
|---|---|---|---|
| occurrence (GBIF/OBIS) | 701 | 667 | 246 |
| fossil (PBDB) | 388 | 625 | 182 |
| genome (NCBI assemblies) | 239 | 232 | 154 |
| phylogeny (TimeTree/OTL) | 5 | 331 | 116 |
| traits (AnAge, PanTHERIA, AVONET, EltonTraits, FishBase…) | 20 | 257 | 141 |
| IUCN status | 2 | 65 | 65 |
| 3D morphology (MorphoSource) | 3 | 62 | 38 |
| barcodes (BOLD) | 0 | 0 | 0 |
| bioelectric / electrophysiology | 0 | 0 | 0 |

Genome assemblies break down as 174 chromosome-level, 44 scaffold, 19 contig, 2 "complete". So sequencing depth is already rankable: the `measurement_technique` string carries assembly level, and the `counts` carry `n_assemblies_for_taxon` plus (on some records) N50/size.

**Prototype ranking** (species only, category presence weighted genome 3, traits 2, others 1):

- Top (10/10): *Columba livia*, *Gallus gallus*, *Oryctolagus cuniculus*, *Panthera leo*, *Sus scrofa*; then *Homo sapiens*, *Equus caballus*, *Bos taurus*, *Canis familiaris*, *Felis catus* at 9 (missing only IUCN, which is expected for domesticates).
- Bottom (1/10, occurrence count only): *Crepidula* spp., *Helix pomatia*, *Galathea squamifera*, *Inachus dorsettensis*, *Scarabaeus sacer*, *Orthopyxis integra*; *Diplodocus carnegii* has a fossil record only.
- Distribution is bimodal: 72 species at ≤2, 82 at ≥8. Darwin's domesticates and Thompson's marine invertebrates sit at opposite ends.

**Two caveats on your "especially" list**

- DNA sequencing: easy to deepen. Beyond assembly level, we can add BOLD barcode counts, SRA run counts, RefSeq annotation presence, and ENA/NCBI assembly stats (N50, BUSCO where reported) via public APIs. All fit the existing `datasets/<id>.json` convention.
- Bioelectric data: nothing in the repo, and there's no cross-taxon public database comparable to GBIF or NCBI. The real sources are narrow: NeuroElectro (neuron-type electrophysiology, mostly rodent), Allen Cell Types (mouse/human), ModelDB, Channelpedia, PhysioNet (human ECG/EEG), and scattered planarian/*Xenopus* Vmem datasets from the Levin lab. Most of Darwin's and Thompson's taxa will legitimately score zero here, and that absence is itself informative. I'd treat it as a sparse axis rather than fold it into a single score.

**How I'd build it, if you want to go ahead**

1. A `organisms/coverage.mjs` that reads `merged/taxa.json` + `merged/datasets.json`, classifies each dataset into categories (as above, but from `id`/`measurement_technique` plus an explicit `category` field we add to the convention), and emits a per-taxon coverage matrix plus a weighted score to `organisms/merged/coverage.json` and a ranked `COVERAGE.md`.
2. A vendoring pass (cloud agents per slice, same as before) to add BOLD, SRA, RefSeq, and a bioelectric/electrophysiology category where sources exist.
3. Expose it as a `delphi_rank_taxa` MCP tool (or a `coverage` mode on `delphi_graph`) so you can ask "species with chromosome-level genome but no trait data".

Per the ontology rule this is coverage/completeness of *our* records, not a reliability assessment of the datasets themselves; that scoring pass stays separate. Say the word and I'll build step 1.

I should give my assessment now, presenting findings plus a proposed design, while flagging that bioelectric data is essentially absent from public sources—keeping it concise.

_Tools used: Grep, Read ×2, Shell ×5_

### 2026-10-31 09:24 — Turn 2 (User)

> yeah i know that there's almost no bioelectric data anywehre but it's something we care about so , when it comes to ehtse organisms

**Assistant:**

Understood: bioelectric stays a first-class axis even where it's empty, so the ranking shows the gap per organism. I'll build the coverage script now.

With confirmation to proceed, I'll build a coverage script that generates merged coverage data and a markdown report, including bioelectric as a tracked category even though it's sparse right now, plus a list of sources to pursue there. First I need to check merge.mjs for style conventions and see how datasets are structured in the merged output before writing the script.

I'm sketching out the coverage script's axes — starting with genome sequencing quality graded from none to chromosome-level, plus assembly counts, and I'm noting barcode and bioelectric data as additional axes still to define.

Beyond that I'm laying out the remaining axes (traits, morphology3d, phylogeny, occurrence, fossil, conservation, taxonomy) with specific source datasets for each, then designing a weighted scoring formula that normalizes to 0-100, giving genome and bioelectric data the highest weights. The output will be a JSON file and a markdown report summarizing axis coverage, top species, and assembly-level breakdowns.

I also want to flag which model organisms in our taxa list are strong candidates for bioelectric/electrophysiology data — classics like Homo sapiens, Mus musculus, Xenopus, Danio, Drosophila, C. elegans, Aplysia, squid giant axon, Hydra, planaria, Electrophorus, Torpedo — so I should check which of these exist in our current taxa list to prioritize vendoring targets.

Now I'll write the coverage script.

I'm puzzling over why 91 genome levels show as "unknown" and why the genome taxa count jumped to 323 from 232 — likely my updated regex now catches terms like "assembly" and "refseq" that weren't matched before, so I should check which datasets are newly classified as genome.

The NCBI Taxonomy record's `measurement_technique` mentions "genome"; I'll test taxonomy before genome and tighten the genome regex.

Occurrence records mention "GBIF Backbone" in their labels, so the head test misfires. I'll switch to id-prefix rules first with the keyword scan as a fallback.

The occurrence count dropped because GBIF records are being misclassified as taxonomy due to "backbone" appearing in the label text — I need to switch to id-based classification using known prefixes instead of matching on label content.

So I'm restructuring the classifier: check explicit category first, then match against an id-prefix table (gbif-occ/obis-occ to occurrence, ncbi-genome to genome, pbdb/paleobiology to fossil, gbif-backbone/ncbi-taxonomy/open-tree/wikidata/worms to taxonomy, anage/pantheria/avonet/fishbase to traits, morphosource to morphology3d, timetree to phylogeny, iucn to conservation), and only fall back to keyword matching on text if no prefix matches.

I'm checking the phylogeny data—the open-tree TNRS result matches taxonomy as expected, while timetree only returned a handful of taxa, which seems legitimate. Now I'm trying to reconcile the fossil count discrepancy, since the number dropped from 388 to 243, likely because the earlier count was inflated by including other occurrence-type records alongside the paleobiology database entries.

Now I'm examining whether GBIF occurrence datasets could also contain fossil specimens, since GBIF labels sometimes include "basisOfRecord=FOSSIL_SPECIMEN" classifications that might explain the gap between the two occurrence totals.

These were ordinary GBIF counts mentioning "fossil specimens" as a basis-of-record type, confirming the prefix rule fixed a real misclassification. I'll now run the validator, check lints, and add a short pointer in the README.

Built. `node organisms/coverage.mjs` now ranks all 782 taxa and writes `organisms/merged/coverage.json` plus a readable `organisms/merged/COVERAGE.md`.

**How it scores**

Ten axes, each counted if the taxon has at least one vendored dataset on it, weighted and normalised to 0–100 (max weight 14):

- genome sequencing (w=3, graded: chromosome/complete = full, scaffold = 2/3, contig = 1/3)
- bioelectric / electrophysiology (w=3)
- DNA barcodes (w=1), trait tables (w=2), 3D morphology, phylogeny, occurrences, fossils (w=1 each), conservation and taxonomic resolution (w=0.5 each)

Bioelectric carries the same weight as genome, so no organism can currently score above ~79, and the top species sit at 64. That's deliberate: the number says "incomplete for what we care about", not "done".

**What the ranking shows now**

- Top: *Columba livia*, *Gallus gallus*, *Oryctolagus cuniculus*, *Struthio camelus*, *Panthera leo*, *Sus scrofa* (64.3), then *Homo sapiens*, *Equus caballus*, *Bos taurus*, dog, cat, mouse, rat (60.7). All chromosome-level genomes plus traits, 3D morphology, occurrences and fossils.
- Bottom: Thompson's shell-coiling gastropods (*Crepidula*, *Haliotis*, *Tonna*, *Conus gloriamaris*) and hydrozoans, with an occurrence count only (7–11).
- Genome depth across the set: 2 complete, 171 chromosome, 43 scaffold, 16 contig; 550 taxa have no assembly record at all. Only 9 records carry BUSCO scores, so sequencing *quality* is thinly captured even where sequencing *exists*.
- 26 species have a chromosome-level genome but no trait table (*Bombyx mori*, *Nautilus pompilius*, three *Schistosoma*, several ants and moths).
- Phylogeny is weaker than my first estimate: only one TimeTree record covering 8 species. The Open Tree records are name resolution, not divergence data, and are now counted as taxonomy.

**Bioelectric**

Zero records, as expected. The report ends with a lead table of the 35 taxa in our set that do have electrophysiology literature or databases, ordered by how often Darwin/Thompson mention them: *Homo sapiens* and *Mus/Rattus* (Allen Cell Types, NeuroElectro, DANDI), *Apis mellifera* (Kenyon cell recordings), the domestic mammals (cardiac ephys, PhysioNet), *Anura*/*Salamandridae* (Levin-lab Vmem patterning), *Cephalopoda*/*Loligo*/*Sepia* (squid giant axon), *Hydra*, *Hirudo*, *Helix*, *Homarus* (STG), *Scyliorhinus* (ampullae of Lorenzini), *Echinus* embryos. That table is the worklist for a vendoring pass; records should set `"category": "bioelectric"` explicitly.

Also added a `category` override to the dataset convention (documented in `organisms/README.md`) so future records don't rely on keyword matching.

Natural next steps, when you want them: a vendoring pass for the bioelectric leads (NeuroElectro and Allen have APIs; most of the rest will be per-paper DOIs with `measurement_technique` set to the recording method), a BOLD barcode pass (API, cheap, covers most species-rank taxa), and exposing `coverage.json` through the MCP server as a rankable view.

_Tools used: Read, ReadLints, Shell ×8, StrReplace ×3, Write_

### 2026-10-31 09:32 — Turn 3 (User)

> is this all accessible in the MCP server now?

**Assistant:**

I should check whether the MCP server exposes coverage.json, but it's probably not there—let me look in the mcp/ directory instead.

No. The MCP server has no reference to `organisms/` at all; it only serves claims, assessments, and the claim graph. I'll add an `organisms` tool. Let me see how the existing tools are wired.

I'll add an `organisms` module following the `graph.mjs` pattern, with two tools: rank/filter taxa by coverage, and fetch one taxon with its datasets.

I should add a new organisms module exposing functions to browse taxa ranked by coverage and fetch a single taxon's details with datasets and mentions, wiring them up as both MCP tools and CLI commands, then update the README and AGENTS docs to reflect this.

I'll have `coverage.mjs` persist the per-axis dataset counts so the overview doesn't recompute classification.

The dataset count by category is mostly undefined since category isn't set, so I should compute it from coverage data instead. I'll add dataset_axes counts into coverage.json via coverage.mjs so the overview can pull from that directly.

Now register the tools in the server and CLI.

CLI works. Now the server path itself via a stdio JSON-RPC handshake:

That works. Next I want to test the MCP server itself over stdio, then update mcp/README.md and AGENTS.md — since the running server likely needs a restart to pick up new tools, I'll verify with a quick JSON-RPC handshake via a small stdio client.

ESM ignores `NODE_PATH`; I'll pipe the script through stdin from the repo directory instead so resolution works.

Both tools work end-to-end. Now the docs: `mcp/README.md` and `AGENTS.md`.

It wasn't, but it is now. The MCP server previously had no knowledge of `organisms/` at all (claims, assessments and the claim graph only). I added two tools, both verified over a real stdio MCP handshake and via the CLI.

**`delphi_organisms`**: rank/filter all 782 taxa by coverage.

- Filters: `text`, `taxonClass`, `rank`, `project`, `hasAxis`, `missingAxis`, `genomeLevel` (`complete|chromosome|scaffold|contig|none`), `minScore`/`maxScore`, `minMentions`.
- Sort: `score`, `score-asc`, `mentions`, `datasets`, `name`. `groupBy`: class, rank, project, genomeLevel (returns mean score and per-axis counts per group). `overview: true` returns axis totals for the whole set.
- Example checked: `hasAxis: ["genome"], genomeLevel: "chromosome", taxonClass: "Gastropoda"` → 16 taxa (*Haliotis*, *Turbo*, *Patella*, …).

**`delphi_get_organism`**: one taxon by key (`gbif:2495414`), slug, accepted name, or vernacular/as-written name (`"rock-pigeon"` resolves to *Columba livia*). Returns identifiers, lineage, coverage score and missing axes, every dataset record with counts/distributions/integrity, and every located mention.

CLI equivalents: `node mcp/cli.mjs organisms --overview`, `organisms --has-axis genome --missing-axis traits --rank species`, `organisms --group-by class`, `organism hydra`.

Files touched: new `mcp/organisms.mjs`; registrations in `mcp/server.mjs` and `mcp/cli.mjs`; `coverage.mjs` now also persists `dataset_axes` into `coverage.json`; docs in `mcp/README.md` and `AGENTS.md`.

One thing to note: the `project-0-delphisci-delphisci` MCP instance Cursor already has running was started from the old `server.mjs`, so it won't list the new tools until it's restarted (toggle it in MCP settings, or reload the window). The stdio test above launched a fresh process, which is why it saw all eight tools.

_Tools used: Read ×3, ReadLints, Shell ×6, StrReplace ×9, Write_

### 2026-10-31 10:04 — Turn 4 (User)

> ok but if people are using the fly instance it iwll be up to date?

**Assistant:**

I should check how the Fly instance is deployed by looking for fly.toml, a Dockerfile, or a deploy workflow.

_Tools used: Shell_
