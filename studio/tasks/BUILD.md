# Frontier execution board

Coordinator: codex-03. Started 2026-10-31 11:07 PDT from the fetched foundation.
All work is in isolated task worktrees. Existing subscription harnesses were
reused because they already hold relevant context and paid capacity; no new
metered model was selected. Provider-billed incremental spend is not yet known.

| Priority | Deliverable | Owner | Status / acceptance |
| --- | --- | --- | --- |
| P0 | Product goal, engineering contract, integrated site | codex-03 | Working; SPEC-005 and browser checks |
| P0 | Constraint solver + meaningful Lean boundary | dx-guilds | Assigned; candidate, conflict, unknown and mutant controls |
| P0 | Flying-fish sourced constraint checker | claude-15's flying-fish-research | Running; handoff via messages/flying-fish-checker.md |
| P0 | Scoped glide simulation + uncertainty | delphi-rethink-nca | Assigned; frozen protocol then convergence and baseline |
| P0 | MCP contribution tools | dx-collab | Working; real client against isolated Postgres |
| P0 | Typed attention and action adapter | dx-market | Authentication failed; recovery requested, not running |
| P0 | Persistent node + site data/export | codex-03 | Pending implementation |
| P1 | Data/tool indexes and multiscale source cards | dx-fable-lead | Working; primary-source research and explicit coupling gaps |
| P1 | OpenResearch and evidence/nanopub adapter | dx-corpus | Assigned; inspectable adapter and draft export |
| P1 | Nebius/Google live inventory and bounded execution | dx-gpuops | Authentication failed; recovery requested, no submission |
| P1 | Printable candidate geometry | codex-03 | Pending; dimensions/manifold controls and scope label |
| P1 | Reuse and allocation measurements | dx-market + codex-03 | Pending; matched tasks and receipt-derived counts |
| P1 | Integrated QA, deployment and pitch handoff | codex-03 + existing director | Pending; exact source SHA and checks |

## Findings to correct during integration

- The earlier site builder counted `def test_` lines as passing tests. Replace
  that count with actual execution receipts or omit it.
- Importable records were described as records in a store; no persistent node
  existed at takeover. Label snapshots accurately and initialize a real node.
- Git timestamps alone do not prove independent witnessing or preregistration.
  Preserve the recorded ordering and hashes without overstating the trust model.
- The inherited code has prose action bounds and no enforced resource runner.
  Report those limits; process scopes enforce actual local runs.
- Existing forecasts, reputation and attention mechanisms must not become truth
  scores or empirical claims of collective advantage.

## Resource and review bounds

All process-spawning test/build/worker runs use a systemd scope with TasksMax=128,
MemoryMax=4G, MemorySwapMax=0 and RuntimeMaxSec=600 unless a separately bounded
job needs a documented limit. CPU threads <=2. Raw GPU jobs remain with their
assigned owner, one GPU per job, at most the previously authorized ten in total,
yielding to other teams; never cancel others' work. Do not consume reset grants.

No website publication broadens the existing audience. New Sites start private.
No external emails or team outreach are authorized by this build board.
