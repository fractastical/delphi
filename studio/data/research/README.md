# data/research — machine-readable Frontier research artifacts

Companion to `docs/research/`. **Owner:** fable-lead · **supports** Root's `spec005`
(does not write it). **Single-reader (fable-lead), NOT Codex-reviewed**, until root review.

## Files

- **`flying-fish-source-cards.json`** (`schema: frontier-source-cards-0.1`) — the authoritative
  curated source cards for the website. Finite JSON with stable ids. Top-level keys:
  - `meta` — provenance, what it supports, `do_not_duplicate` (the checker + guilds solver),
    `claims_no_flight`, `no_domain_impossibility`, `framing` (envelopes are not feasibility laws;
    not a binary gate), and `ar_reconciliation` (the pectoral-fin vs whole-wing AR fix).
  - `vocabularies` — `read_level`, `evidence_kind` (`measured|fitted|assumed|design_selected` +
    `cited_source_claim|independent_rerun|inference|missing_bridge`), `connector_state`
    (`discovered|accessible|retrieved|replayed|validated|dead`), `approach`
    (`design_goal|theory_fit|literature_gap|challenge|measurement`).
  - `scales` — the **eleven** SPEC-026/spec005 levels, each with the flying-fish occupancy
    (`executable_today|claim|data_missing|not_occupied`).
  - `sources` — 19 cards: id, citation, url, locator, read_level, license, verification,
    evidence_kind, note.
  - `parameters` — 13 measurable quantities: variable, symbol, unit, value/range, organism_context,
    source + locator, evidence_kind, assumption_scope, transfer_limits, and `contradiction` where
    one exists (e.g. the AR 16.9/19.9 band).
  - `constraints_ref` — the 8 checker constraints **referenced, not duplicated**
    (`implemented_in: messages/flying-fish-checker.md + guilds 6612af6`), each with
    `executable_today`, `envelope_not_law`, and `semantics`.
  - `models_and_bridges`, `connectors` (with access state + date), `bounded_searches`, and
    `curated_questions` (the WHITEBOARD structure, below).

## Curated questions (the "whiteboard")

14 questions joining **top-down design goals** and **bottom-up theory-fit**. Each carries:
`approach`, `scales`, `context_tags`, `dependencies{claims, parameters}`, `success_criterion`,
`rejection_criterion`, `needed_data`, `needed_tool`, `group` (`executable_today|data_missing`), and
`links{models, data, design_outcomes}`. One (`FF-Q04`) is discrepancy-driven: *does the zebrafish
`lat4a`×`kcnh2a` fin-proportion mechanism predict the observed exocoetid pectoral allometry?* —
predicted-vs-observed fin proportions, which generates new questions when they disagree.

## Bounded morphometrics search (recorded, dated)

**2026-10-31 UTC.** Goal: a **downloadable per-specimen paired pectoral-fin-area + body-mass** dataset
for exocoetids (would move the organ→organism coupling from fitted to measured).

| Repository | Query | Result |
|---|---|---|
| Dryad | `Exocoetidae` | **0** |
| Dryad | `flying fish morphometrics` | 1 (a bird-blowfly parasitism dataset — irrelevant) |
| Zenodo | `Exocoetidae` | 353, **all taxonomic treatments** (Plazi/Pensoft), no per-specimen morphometrics |
| Zenodo | `"flying fish" wing loading` | empty |
| Figshare | `search_for=Exocoetidae` | unrelated results — **inconclusive, not a clean negative** (the endpoint did not filter) |
| MorphoBank | API `searchterm=Exocoetidae` | **HTTP 403 — not accessed** |

**Result:** no downloadable per-specimen paired fin-area × mass dataset found **on those four
repositories on that date**. This is **searched-not-found, NOT universal absence**; Figshare was
inconclusive and MorphoBank was not accessed. Tracked as `curated_questions` `FF-Q06`.

## Access note — Daane 2021 exact Figure-4 ratios (not an absence)

The exact fin/body ratio numbers (Fig 4: wild-type, single, double mutant, flying-fish) are **not
extracted**: `daanelab.org` is **DNS-unresolvable from this environment** (Jina 422), Europe PMC
`fullTextXML` returns **HTTP 500** for this non-OA record, and `supplementaryFiles` is empty. The
paper's prose and abstract were read (`full-text via r.jina.ai` + Europe PMC `core`). This is an
**access failure recorded as an open problem** (`FF-Q07`), **not** evidence the data do not exist.
