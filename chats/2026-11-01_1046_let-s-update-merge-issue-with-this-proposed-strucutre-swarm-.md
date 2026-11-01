# let's update merge issue with this proposed strucutre /swarm -- all collaboratio

- **Started:** 2026-11-01 10:46 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 10:49 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `4bedb6fc-1b80-40c9-8728-e79f7472ee3f`

## Conversation

### 2026-11-01 10:46 — Turn 1 (User)

> let's update merge issue with this proposed strucutre
> 
> /swarm  -- all collaboration documentation, chat logs, structyur, etc 
> /engine --  
>    -- delphi-core - epistemic claim engine/nanopubs, 
>    -- studio - what now lives in frontier 
> /site -- everythign from kavita's repo for presentation 
> 
> anythign else we need? let's ping everone

**Assistant:**

I'll find the merge issue and the current layout so the proposed structure matches what's actually in the repo, then ping the people on that issue.

Issue #79 is the merge. I'll read it and map the top-level folders so the proposed layout covers what people actually own.

The three roots cover the products, but four things still have no home. I'll put that map on #79 and ping the team so the layout isn't decided in one checkout.

The three roots are enough. Four decisions were missing, so those are now on [#79](https://github.com/fractastical/delphi/issues/79) and the team is pinged: Amit, Ashley, Kavita, and Kris (he was not on the issue before).

```
swarm/                  chat logs, roster, decisions, forum, thread status
engine/
  delphi-core/          claims, Lean, tests, nanopubs, MCP
  studio/               design studio
site/                   Kavita's portal, plus the generated claims atlas
```

The repo entry stays thin (`README`, `AGENTS.md`, package and deploy files). [delphi-evolve](https://github.com/kganjam/delphi-evolve) stays a sibling.

What still needs a reply before any path move:

1. **Kris.** `engine/studio` is two different trees today: `sim-engine/` in this repo, and [delphi-frontier](https://github.com/kganjam/delphi-frontier) as his repo. He has to say whether frontier folds in. Open problems move into `delphi-core`.
2. **Kavita.** `site/` is the portal import (still at `ad8e85e` in `docs/PORTAL.md`) plus the generated atlas she already owns. She needs to say if the portal has moved past that commit.
3. **Amit.** The organism products at the root (anatomy, genotype, physics, physiology, sequences, and the rest) go under `studio`. Mission control splits: status threads to `swarm/`, the blueprint UI to `studio/`, deck and figures to `site/`. The 40.9 MB `genotype/map.json` on his branch does not come upstream as one tracked file.
4. **Ashley.** Nanopub generators and `claim-grounding/` move with `delphi-core`. #52 rebases after the layout.

#74 is already merged. The layout PR waits on those four replies, because landing it first conflicts every open branch.

_Tools used: GetDynamicTools, Glob ×4, Grep ×3, Read ×8, Shell ×8, Write_
