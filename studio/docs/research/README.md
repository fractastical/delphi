# docs/research — Frontier substrate research

Implementation-focused research supporting **Root's normative `spec005`**
(`SPEC-005-agentic-engineering-demo`, the multiscale agentic engineering substrate). This directory
**supports** that spec; it does not write it, and does not touch `main`, top-level `specs/`, or
`site/`. The machine-readable companion lives in `../../data/research/`.

**Reviewer status:** every file here is **single-reader (fable-lead), NOT Codex-reviewed**, until
root review.

**Read-level convention:** `full-text` | `full-text via r.jina.ai` | `via fetch tool` | `abstract` |
`listing` | `search-summary` | `could-not-access`. **Evidence kinds** (spec005): `measured`,
`fitted`, `assumed`, `design-selected`, plus provenance `cited source claim` / `independent rerun` /
`inference` / `missing bridge`.

| File | Subject |
|---|---|
| [frontier-multiscale-substrate.md](frontier-multiscale-substrate.md) | The note: the eleven-scale flying-fish coupling map with every unsolved coupling marked; the five substrate layers mapped to real sources and store primitives; constraint-solver + Lean P0 (bite vs decoration); BioModels + jaw-joint model-class transfer; the connector access/replay table; the bounded morphometrics search |
| [darwin-flying-fish.md](darwin-flying-fish.md) | Darwin primary: Chapter VI "imaginary illustration," edition/page locators (1859 p.182 … 1872 p.140), cross-edition wording variants (variorum), the "fluttering fins" vs modern-gliding distinction, and the three things the narrative must not claim |
| [source-cards/README.md](source-cards/README.md) | Human-readable source cards by scale; **the authoritative machine-readable set is [`../../data/research/flying-fish-source-cards.json`](../../data/research/flying-fish-source-cards.json)**; Draft records for import in [`../../data/research/frontier-drafts.json`](../../data/research/frontier-drafts.json) |
| [`../../data/research/design-primitives.json`](../../data/research/design-primitives.json) | Model/connector **index** across scales (16 primitives). Honest `capability_state` (implemented-run / implemented-unrun / external-connector / proposed / blocked) + engine + source + output + missing bridge + next action; `provenance` marks verified-by-fable vs asserted-by-project. **Not** a claim we designed one of each |
| [future-missions-comparative-finch.md](future-missions-comparative-finch.md) | **Scoping only** — a proposed future mission on Darwin's-finch beaks (distinct from zebra finch); genetic-association vs developmental-model vs mechanics; leads only, no sim; gated on root importing the fish Drafts first |

**Core finding (corrected 2026-10-31 after root review):** flying fish is best-supported at the
organism / organ / evolution scales (measured biomechanics, a downloadable time-tree → executable
arithmetic C1–C6) and thinnest at tissue and cell scales. **The molecule scale is not empty** —
Daane et al. 2021 give a `lat4a`×`kcnh2a` candidate for fin **proportion** (genome-wide across 35
species; functional phenocopy **in zebrafish**; **no flight demonstrated by the genetics**). The
couplings from that genetics up to an exocoetid fin are **unbuilt bridges / cross-organism
transfers**, labelled as such. Measured ranges are **provenance-scoped envelopes, not feasibility
laws**; absences are **bounded dated searches, not universal impossibility**. No domain impossibility
is asserted anywhere.
