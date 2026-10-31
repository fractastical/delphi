# docs/research — Frontier substrate research

Implementation-focused research supporting **Root's normative `spec005`** (the multiscale agentic
engineering substrate). This directory **supports** that spec; it does not write it, and it does not
touch `main`, top-level `specs/`, or `site/`.

**Reviewer status:** every file here is **single-reader (fable-lead), NOT Codex-reviewed.**

**Read-level convention** (shared with `morphoswarm/docs/research`): `full-text` | `abstract` |
`listing` | `search-summary` | `could-not-access`. Pages read through `WebFetch` are marked
**via fetch tool** (that tool answers against the page with a separate small model — a weaker grade).

| File | Subject |
|---|---|
| [frontier-multiscale-substrate.md](frontier-multiscale-substrate.md) | The note: the flying-fish molecule→…→evolution coupling map with every unsolved coupling marked; the five substrate layers (connectors/indexes, tools+skills, parameters+units, epistemic/evidence, coordination) mapped to real sources and store primitives; constraint-solver + Lean P0 (where it bites, where it is decoration); BioModels that retrieve/replay and why parameters do not transfer; the connector table with actual access/replay status |
| [source-cards/README.md](source-cards/README.md) | One card per source and connector, grouped by scale (organism/organ, evolution, molecule, tissue/cell) plus method/epistemics/coordination and a dead/blocked-connector table; each with read-level, primary URL, access & replay status, and caveat |

**Core finding:** flying fish is actionable at organism/organ/evolution (measured biomechanics +
a downloadable time-tree → executable constraints C1–C6) and **unsolved below the organ** (one
scaffold genome for the family; no fin material, cell, or developmental data). spec005's executable
constraints are the organism-scale arithmetic; everything subcellular is an empirical assumption or
a cross-scale gap, and must stay visible as a gap.
