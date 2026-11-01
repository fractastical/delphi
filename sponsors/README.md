# Sponsor services: what we used, one file per sponsor

Science Claw Hack @ MIT, Oct 30 – Nov 1, 2026. Each file states what we used the sponsor's service
for, where in the repository the record is, what it produced, and what we did not do. Every number
is read from a named file or issue, following the repo rule that no figure is written that was not
computed. The highlights are merged into the main [README](../README.md#sponsor-services-what-we-used).

| Sponsor | Used for | File |
|---|---|---|
| NVIDIA | Brev L40S serving a self-hosted Qwen3-32B assessor over 566 Aristotle claims; BioNeMo ESMFold NIM called and refused (401), recorded as such; NIM protein-design backends wired, not exercised | [NVIDIA.md](NVIDIA.md) |
| OpenResearch (alphaXiv) | `orx discover` literature grounding, made a release requirement (role A2): six headline tests (5 of 6 already answered by prior work), the 59-search prior-art report, the physics thread, the open-problems catalogue | [OPENRESEARCH.md](OPENRESEARCH.md) |
| Nebius | Scientific AI Platform: 19 Cellpose operations testing three Thompson cell-packing claims (with the segmenter-bias null that downgraded one verdict); 23 ESMFold2 operations for three pre-registered Levin tests | [NEBIUS.md](NEBIUS.md) |
| Formlabs | Two 140 mm SLA dragonfly hindwings printed (real venation beside the Hoffmann 2018 model) and several flying zebrafish printed (project lead's report, no photo in the repo yet); the 71-file winged-zebrafish kit designed to Formlabs specs; a pre-registered printed test of a Lean-proved bilayer law | [FORMLABS.md](FORMLABS.md) |

Anthropic, OpenAI and Google models are used throughout as builders and assessors (the assessor
records in each `claim-sources/<project>/assessment/assessors.json` name them); they are not written
up here because this folder covers the four services the team used for compute, literature and
fabrication. The remaining sponsor integration issues (#5, #9, #12, #13) are proposals that were not
run.
