# Compute receipt (ids and hashes from the controller manifests; provider states read live)

Cost: **unavailable** (the event exposes no price or usage receipt to participants; this is not zero). No URLs are recorded.

| job name | job id | created (UTC) | provider state | provider start - finish (UTC) | controller status | in-container rc | returned bytes | returned sha256 | note |
|---|---|---|---|---|---|---|---|---|---|
| `delphi-evolve-ops-fcpuref1-cpu-reference-pilot-a1` | `aijob-e00b95e1p1mkbtxa78` | 2026-10-31T18:31:42Z | COMPLETED | 2026-10-31T18:33:51.802457860Z - 2026-10-31T18:37:03.764892819Z | done | 0 | 48115 | `3f83e68ec5894b92be1bf05b5a45e6155f30ade9979f605f8f55dbe5be418615` |  |
| `delphi-evolve-ops-fcpurefho1-cpu-reference-heldout-a1` | `aijob-e00cs2drpmgzwtqy4h` | 2026-10-31T19:06:56Z | COMPLETED | 2026-10-31T19:09:04.769133230Z - 2026-10-31T19:17:51.250728418Z | done | 0 | 149647 | `e23fad1cb8a64f295b160ce20591ea6bcc2f47f184a19506be1d6a84c1bf4038` |  |
| `delphi-evolve-ops-fevo2smoke1-evo2-7b-smoke-h100-a1` | `aijob-e00w9pbaxa5s241nj0` | 2026-10-31T19:31:42Z | COMPLETED | 2026-10-31T19:46:04.747455594Z - 2026-10-31T19:50:34.612227421Z | failed | None | None | `None` |  |
| `delphi-evolve-ops-fevo2smoke2-evo2-7b-smoke-h100-a1` | `aijob-e00g0nf8198feggzk6` | 2026-10-31T19:54:30Z | COMPLETED | 2026-10-31T20:00:51.353229751Z - 2026-10-31T20:01:49.533839762Z | done | 0 | 29451 | `782ae8d15591afd180a69d3f6671f815914a269a44ef0af3258c5a0e17c972f5` |  |
| `delphi-evolve-ops-fflow1-ns2d-shear-demo-h100-a1` | `aijob-e00bwhhhhwgeenfge9` | 2026-10-31T19:40:18Z | COMPLETED | 2026-10-31T19:54:02.658412069Z - 2026-10-31T19:54:58.886675056Z | done | 0 | 312523 | `9de495ec0fddb7f4d1b638f2bd133956464750fad0b4cf6805e43ab46198f441` |  |
| `delphi-evolve-ops-fgpuho1-heldout-validation-h100-a1` | `aijob-e00cmrs77wc8hp9snf` | 2026-10-31T19:18:54Z | COMPLETED | 2026-10-31T19:33:37.684471595Z - 2026-10-31T19:36:27.414813207Z | failed | 0 | 1029842 | `1119f2c3c89723bf4dbd4b3f16052ba8c9f412a44c3191408387245c554da2e6` | truncated;  |
| `delphi-evolve-ops-fgpuho2-heldout-validation-h100-a1` | `aijob-e00avhz5c9s4tgp4rp` | 2026-10-31T19:38:33Z | FAILED | 2026-10-31T19:52:17.571814983Z - 2026-10-31T19:52:19.957231380Z | failed | 1 | 171 | `cc9d9d3107e4292d32884867b5f1a8b8626e570688acfa9920d265acb8bb37bd` | Container exited with non-zero exit code. |
| `delphi-evolve-ops-fgpuho3-heldout-validation-h100-a1` | `aijob-e00r9m7mnr725zyqwt` | - | CANCELLED | None - None | failed | 0 | 1032298 | `5c325b4beb3be9d2e0ea00c8a2d11177fca7ee3186886de3c562607b8d0b2bac` |  |
| `delphi-evolve-ops-fgpupilot1-pattern-pilot-h100-a1` | `aijob-e00nrr5r9x951ph95t` | 2026-10-31T18:38:34Z | COMPLETED | 2026-10-31T18:53:48.974132Z - 2026-10-31T18:55:56.232950046Z | done | 0 | 355062 | `39959902519ab1d97e23a8a91d1db2bc5443e697573d2edacc9f02b663e7e40c` |  |

A provider state of COMPLETED means the container exited; it does not mean a scientific result exists or passed. See PROTOCOL*.md for the frozen labels.
