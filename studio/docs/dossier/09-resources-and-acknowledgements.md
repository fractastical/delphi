# Resources we are thankful for

The people, code, data and institutions that made this work possible. Every item below
was actually used in the build; versions and identifiers are taken from the repository's
own pins and receipts, not from memory.

## People and partners

- **The team.** Kris Ganjam (Allen Institute) and collaborators across the Delphi and
  MorphoSwarm work, with Kavita Koolkarni's Delphi portal and Joel Dietz's Delphi claim
  work as sibling efforts we draw on and link to.
- **Hackathon sponsors and hosts** — the ScienceClaw hackathon organisers and judges, and:
  - **Nebius** — H100 GPUs and the Nebius Scientific AI workbench (69 hosted scientific
    tools: AlphaFold3, OpenFold2/3, ESMFold2, Boltz-2, BioEmu2, RFdiffusion, ProteinMPNN,
    GROMACS, OpenMM, DiffDock and more).
  - **Google** — Gemini models (`gemini-embedding-001` for the live semantic index;
    `gemini-3.8-flash` and `gemini-4-argon` for review and extraction) and Google Cloud
    compute.
  - **NVIDIA** — BioNeMo and Brev, and the CUDA stack every GPU run depends on.
- **Upstream scientific communities** whose records we import with their provenance
  preserved: the nanopublication network, BioModels, UniProt, Ensembl, NCBI, ZFIN,
  Europe PMC and FishBase.

## Open-source code

**This project's own repositories (public):**
`github.com/kganjam/delphi-frontier` — site, record store, MCP server, Lean proofs,
simulation harnesses. Related: MorphoLib and MorphoEval.

**Built on:**

| Area | Tools |
|---|---|
| Proof | **Lean 4.35.0**, **Mathlib** (rev `56a0058`) |
| Solving | **Z3** 5.3.3 |
| Store and search | **PostgreSQL 16**, **pgvector**, psycopg 3.3 |
| Agent interface | **Model Context Protocol** SDK 1.27 |
| Systems biology | **libRoadRunner** 2.10 (SBML), **BETSE** 1.5.0 (bioelectric), **Morpheus** 2.3.9 (multicell / cellular Potts) |
| Molecular | **OpenMM** 8.4 (ff14SB, TIP3P, CUDA), **OpenFold2**, **Evo 2** |
| Fluids and solids | **WaterLily.jl** 1.10 (3-D Navier–Stokes), a D2Q9 lattice-Boltzmann solver, a steady thin-surface vortex-lattice method, **Voxelyze** |
| Scientific Python | NumPy 2.4, SciPy 1.17, Matplotlib 3.11, RDFLib 7.6 |
| Geometry and print | **manifold3d** 3.5.4, **trimesh** 5.2 |
| Web | **KaTeX** 0.16.47 (MIT), **three.js** 0.170.0 (MIT) — both vendored with licence files and verified tarball digests |
| Test and tooling | pytest 9, Playwright |

## Mathematics and source texts

**Formal mathematics.** Lean 4 (version 4.35.0, commit `eb6cafb7`) with Mathlib, used for
five bounded proof families: geometric similarity, unit algebra, a cantilever guard,
steady oxygen transport, and scaled threshold intervals.

**Primary literature, each recorded with its read-level:**

| Source | Used for | Read level |
|---|---|---|
| Fish, F. E. (1990), *J. Zool.* 221 — wing design and scaling of flying fish | wing loading, glide scaling | full text |
| Park, H. & Choi, H. (2010), *J. Exp. Biol.* 213 — aerodynamics of flying fish in gliding flight | lift and drag behaviour | full text |
| Davenport, J. (1992) — wing-loading, stability and morphometrics in Exocoetidae | mass and area envelopes | abstract |
| Davenport, J. (2003) — allometric constraints on stability and maximum size | size limits | listing |
| Lovejoy, Iranpour & Collette (2004) — phylogeny of beloniform fishes | ancestry and reachability | abstract |
| Xu, Zhao, Gao & Wu (2013) — a stem-neopterygian fish, Middle Triassic | deep context | search summary |
| **Darwin, C. (1859)**, *On the Origin of Species*, ch. VI (Project Gutenberg #1228) | the original flying-fish passage | full text |
| Daane, J. M. et al. (2021), *Curr. Biol.* — a *lat4a* × *kcnh2a* interaction phenocopying flying-fish fin proportion | the molecular-scale lead | full text |
| Collier et al. (1996), replayed from published SBML (BIOMD0000001047) | Delta–Notch lateral inhibition | model file |
| Hayden et al. (2021) — ERK trigger waves with growth | tissue patterning | model |
| Alben et al. (2007), eqs. 3.14 / 5.2 — two-hemitrich planar ray | fin-ray mechanics | equations |
| Wang et al. (2021), *PNAS* — Zebrafish-GEM (CC-BY-4.0) | metabolic model | model |

A read-level is part of the record: listing a source is not reading it, and a search
summary is a lead rather than evidence.

## Data and compute

**Data.**
- **BioModels** — curated SBML models, replayed rather than reimplemented.
- **UniProt**, **Ensembl**, **NCBI Datasets and E-utilities**, **ZFIN** — sequence,
  gene and annotation lookups. NCBI lists exactly one Exocoetidae genome assembly,
  *Hirundichthys speculiger* **GCA_018398805.1**; Ensembl has none, so medaka is the
  nearest annotated proxy.
- **Europe PMC / PubMed** — literature retrieval with read-levels recorded.
- **FishBase** — Exocoetidae size ranges.
- **Delphi claims and the nanopublication network** — imported with original record,
  licence and creator preserved.

**Compute.**
- **Nebius H100 (SXM)** — 1 GPU per job. Sampled 1 Hz telemetry on three tasks recorded
  96.6%, 98.6% and 51.6% mean GPU utilisation, peaking at 100%.
- **Google Cloud** — CPU instances in `us-central1`, plus the Gemini API.
- **Local host** — PostgreSQL, the web service, the Lean toolchain and the browser test
  suite.

Honest note: allocation is not utilisation, the billing meter was never queried, and total
provider spend is unknown. Failed and cancelled jobs are kept in the record alongside the
successful ones.

## Licences

All vendored web libraries are MIT and carry their licence files and verified digests.
Imported scientific records keep their own upstream licences; Zebrafish-GEM is CC-BY-4.0
as stated by its repository. Darwin's text is public domain via Project Gutenberg.
