# Which Delphi ontology version are we using

- **Started:** 2026-10-30 19:11 UTC-4 (EDT)
- **Last activity:** 2026-10-30 19:11 UTC-4 (EDT)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `2a7af20d-910d-49d9-b275-fa134c462b29`

## Conversation

### 2026-10-30 19:11 — Turn 1 (User)

> what delphi ontology veriosn are we using?

**Assistant:**

I'm going to check the BEST_PRACTICES section around line 150, looking for pinned commits, submodules, and the package.json.

Let me check what the generators actually emit, since documentation and code may differ.

We're on **Delphi ontology 2.0**, from [fractastical/project-delphi-ontology](https://github.com/fractastical/project-delphi-ontology). The repo doesn't pin that version, though: there's no submodule, package dependency, commit hash or `owl:versionInfo`. It just points at the upstream `main` branch.

Here's what shows we're on 2.0:

- **The docs say so.** Section 9 of `BEST_PRACTICES.md` tells us to use the canonical namespaces from [ontology 2.0](https://github.com/fractastical/project-delphi-ontology/blob/main/ONTOLOGY.md) and the 2.0 attribution shape.
- **The generator follows it.** `darwin-origin/build/generate.mjs` emits the 2.0 namespace `@prefix delphi: <https://w3id.org/delphi/ontology/>`.
- **The output follows it.** All 62 generated `.trig` files use that namespace. None use the deprecated 1.0 forms (`probknow` IRIs, `delphi:Model`, `delphi:assessedBy`).

Because we track `main`, an upstream change would reach us without notice. That includes the lint step, which clones whatever is current. If you want reproducible builds, which `BEST_PRACTICES.md` asks for elsewhere ("pin … the generator's commit"), we could record a specific upstream commit or tag.

I'm noting that there's no pinned version number or commit to rely on, so I'll just give the answer as it stands.

_Tools used: Grep ×2, Read, Shell ×2_
