# Hackathon contributor ledger: counting basis

Data: `results/resources/agent-contributors.json`, built by `python3 scripts/agent_contributors.py` (read-only; observed 2026-11-01T02:50:57.712021Z, window start 2026-10-31T07:00:00Z). Tests: `tests/test_agent_contributors.py`.

## The answer, by unit (nothing is summed into one number)

| Unit | Count | What it means |
|---|---|---|
| Harness IDs with authored evidence in the window (**supported minimum**) | 4 (claude-05, claude-15, codex-03, dx-submit) | a handoff in the window whose filename or title names the ID as sender, or whose sender equals a session name |
| Harness IDs probable, not counted | 5 (dx-collab, dx-corpus, dx-gpuops, dx-guilds, dx-market) | a role name matches the session once `dx-` is stripped; alias unproven |
| Harness IDs named by other handoffs only | 9 | referenced, no evidence they authored anything |
| tmux session names / after rename dedup | 34 / 33 | `dx-submit-retired-1` is a rename of `dx-submit` |
| Sessions with a live claude/codex process now | 31 | a descendant process of the pane, checked at observation time; says nothing about contribution |
| Roles in handoff filenames | 98 | topic or worker names, not assumed to be distinct harnesses |
| Worker branches (`work/*`, `codex/*`) | 91 | jobs, not agents |
| Own provider jobs | 42 | from `hackathon-usage.json`, jobs not agents |
| Git identities in the window | 4 | `SciDEX Bot` is one shared identity for most commits; one is a human |
| Models in commit trailers | 4 | a model is not an agent |

## Basis and limits
- **Window:** handoff mtimes, commit times and job times from 2026-10-31 00:00 PDT. Earlier evidence is skipped.
- **Dedup:** `claude13`, `claude-13` and `Claude 13` are one ID; `-retired-N` is a rename; `-rN` sessions stay distinct and are flagged.
- **Not evidence:** tmux `session_activity` (one poller touched 18 sessions within 180 s, so it is ignored); a mention of an ID; document names such as `CODEX-21-...`.
- **Undercount, by construction:** a worker that wrote a handoff with no ID in its name or title, and committed under the shared identity, is not in the supported minimum. This session's own handoffs are an example. So 4 is a floor, not an estimate.
- **Unknowns:** role-to-harness mapping, unattributed workers, reuse of pre-window sessions, and the earlier "four native agents" figure (not reconstructed).
- **Privacy:** private handoffs were read for IDs only; the output carries file names, sha256 and times, no text. Regenerate to refresh.
