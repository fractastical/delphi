# i think we can close all flying fish related repos

- **Started:** 2026-11-01 11:06 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 11:10 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `fae29061-ae71-4ea7-8f57-00cca6fbcfc6`

## Conversation

### 2026-11-01 11:06 — Turn 1 (User)

> i think we can close all flying fish related repos

**Assistant:**

I'll look up which flying-fish repositories exist and how they're referenced here before closing them.

The flying-fish work lives in this repository’s work-package issues, not in separate GitHub repositories. I’m closing those issues and leaving the parent ask open, because it also lists work that is not about the fish.

There are no separate flying-fish GitHub repositories under your account or the team's. That work lives in `fractastical/delphi`, so I closed the work-package issues there.

**Completed**, because the deliverable is already in the repo:

- [#50](https://github.com/fractastical/delphi/issues/50) — glide table (`physics/glide-data.csv`, 27 rows)
- [#43](https://github.com/fractastical/delphi/issues/43) — Thompson envelope test (the measured fish is inside the envelope; the scaling test was inconclusive)

**Closed as not planned**, the engineering packages we are not finishing:

- [#44](https://github.com/fractastical/delphi/issues/44) fin outlines and an STL
- [#45](https://github.com/fractastical/delphi/issues/45) add-on wing
- [#46](https://github.com/fractastical/delphi/issues/46) printable spar
- [#47](https://github.com/fractastical/delphi/issues/47) test rig
- [#48](https://github.com/fractastical/delphi/issues/48) bioprinting path
- [#49](https://github.com/fractastical/delphi/issues/49) glide-to-flap

Design notes under `fabrication/flying-zebrafish/` and `anatomy-model/print/` stay in the repo.

[#42](https://github.com/fractastical/delphi/issues/42) is still open. Its headline is the flying fish, but the standing asks under it (segmenter review, phylogenetics, Lean, dataset scoring, bioelectric series, knowledge-graph partners) are not fish work. I left a comment there saying the packages are closed.

I did not archive `kganjam/delphi-frontier` or the Delphi forks. Those are other people's repositories, and they are broader than the flying fish. The plant-hygromorph issue ([#65](https://github.com/fractastical/delphi/issues/65)) is a flytrap, so that stayed open too.

_Tools used: GetDynamicTools ×6, Glob ×4, Grep ×14, Read ×2, SearchConversations ×3, Shell ×19, frontier_capabilities, frontier_search, list_namespaces_
