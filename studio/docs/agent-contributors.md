# Hackathon participation: evidence and counting units

The recorded Frontier participant floor is **23**, comprising **11 supported harnesses, 4 native child identities and 8 nested Claude child identities**. This is a historical participation count, not a count of simultaneously active workers or successful tasks.

Transcript cutoff: **10:08:29PM PDT on October 31, 2026**, window starts midnight PDT October 31. Sources: [participation receipt](../results/resources/agent-participation.json), [harness ledger](../results/resources/agent-contributors.json), [scope and live API observation](../results/resources/agent-participation-scope.json), [reviewed artifact mapping](../results/resources/agent-contributor-mapping.json).

| Unit | Recorded count | Meaning |
|---|---:|---|
| Supported contributing harness IDs | 11 | Authored handoff or reviewed mapping with an in-window artifact; includes root/codex-03 once |
| Native historical child identities | 4 | Actual child session metadata and tool activity; includes retired bioelectric_sim |
| Nested Claude child identities | 8 | Initial task explicitly names Frontier and has actual assistant/tool activity |
| Recorded participant floor | 23 | Sum of those disjoint identity classes, not an estimate of every contributor |
| Native API running root / children | 1 / 3 | Actual API observation at 10:07:30PM PDT; running state is not measured CPU/model utilization |
| Native task turns started / completion events | 36 / 33 | Completed conversation turns, not independently accepted outputs |
| Scoped Claude task transcripts | 8 | One distinct scoped child transcript each; no success claim |
| Transcripts inspected / excluded | 166 / 154 | Earlier, unscoped, and root-only records excluded |
| Host tmux names / after rename dedup | 34 / 33 | Inventory only; not scoped participant or activity count |
| Live harness descendant processes | 31 | Process presence only; auth-blocked/idle processes remain possible |
| Current Frontier provider job records | 46 | Snapshot from hackathon-usage.json; jobs are not agents |

## What changed

The earlier floor of 14 included 11 harnesses and only the three native children supported by artifact mapping. It omitted a retired native child and eight explicit Frontier nested research workers. The original artifact-backed minimum of three remains in the harness ledger, while transcript-backed historical native participation is four. **Never add the old native minimum to the new native count.** The native API's current tree omits retired agents, so it cannot reconstruct historical participation by itself.

The eight nested tasks cover ASK source identification, bioelectric problem sourcing, Buehler prior art, cavefish analysis, flying-fish constraints, evidence API review, open-problem sourcing, and the preregistered KCNE1 job. Participation does not imply a positive scientific outcome. Fifteen other same-day child transcripts lack the required Frontier initial-task scope and are excluded, as are earlier project records. This deliberately remains a lower bound.

## Reproduction and privacy

Run `python -m frontier_compute.agent_participation --help` for the transcript receipt generator, then `python scripts/agent_contributors.py` for the harness ledger and joined summary. The reviewed scope file pins the Studio root thread and separately timestamped direct `collaboration.list_agents` observation. Refresh that observation from the actual tool; elapsed time never updates it automatically.

The scanner reads complete JSONL lines only within the initial file byte boundary, bounds line/file size, and publishes prefix hashes, identity IDs, timestamps, counts and model metadata. Incomplete trailing lines are withheld; malformed complete lines exclude the transcript. Parent metadata embedded in full-history forks cannot replace the child identity, and inherited events before child creation are not counted. Duplicate child identities require explicit resume reconciliation.

No prompts, tool arguments, encrypted message content, account IDs, credentials or unrelated transcript names are published. Model IDs (claude-opus-5, gpt-6-astra, gpt-6-luna, gpt-6.1-sol) come from recorded model/context metadata, not a provider billing ledger. Provider calls, tokens, spend, global simultaneous activity and platform concurrency limits are not inferred here.

The older harness evidence rules remain: sender-side handoff titles prevent recipients being counted as authors; reviewed mappings prove artifacts exist but rely on explicit identity attribution; shared Git author names, model names, branches and tmux activity timestamps do not identify agents. The five probable `dx-*` aliases remain uncounted. No platform settings were changed.
