# Hackathon contributor ledger: counting basis

Data: `results/resources/agent-contributors.json` (built by `python3 scripts/agent_contributors.py`; observed 2026-11-01T03:01:44.096881Z, window start 2026-10-31T07:00:00Z), reviewed input `results/resources/agent-contributor-mapping.json`, tests `tests/test_agent_contributors.py`.

## Counts by unit (never summed)

| Unit | Count | Meaning |
|---|---|---|
| **Supported contributing harnesses (minimum)** | 11: claude-02, claude-04, claude-05, claude-06, claude-07, claude-10, claude-13, claude-14, claude-15, codex-03, dx-submit | authored handoff in the window, or a reviewed mapping whose named artifact resolves in the window |
| Probable, not counted | 5 | `dx-*` session matches a bare role name; alias unproven |
| Named by others only | 3 | referenced, no authorship evidence |
| tmux session names, raw / after rename dedup | 34 / 33 | `dx-submit-retired-1` is a rename |
| **Live harness processes now** | 31 | a claude/codex process under the pane. Not a measure of work |
| Pane state (coarse class of the last lines) | {"auth_blocked": 13, "error_visible": 2, "idle": 6, "unknown": 11, "working": 1} | `idle` is an empty prompt; `auth_blocked` shows a login string; `error_visible` shows an API or hook error; `unknown` matched nothing |
| Roles in handoff filenames | 81 | topic names, not harnesses |
| Worker branches / own provider jobs | 93 / 42 | jobs, not agents |
| Git identities / models in trailers | 4 / 4 | `SciDEX Bot` is one shared identity; a model is not an agent |
| Native agents | not measured | separate unit; matched to a session only via the reviewed mapping |

Contribution activity is **unknown** for every session: a live process, an idle prompt or an auth block is not work.

## Evidence basis
- **Sender side of the title:** the text before the first arrow or ` to ` (or before `:`) decides who wrote a handoff, so a recipient ID is never taken as the author. `fish-glider (claude-05) → ...` and `# claude-07: ...` count; `BioModels to codex-03:` does not.
- **Role labels:** a title `role (claude-NN) →` labels that role as that harness; the label applies to other handoffs whose filename sender is exactly that role. A role labelled with two harnesses is a conflict and is not used (0 now).
- **Reviewed mapping:** 6 root-attested entries; each is checked against its commit, branch or handoff (resolves, in window, title names the harness) and counted only if it verifies. One git identity signs nearly all commits, so commit authorship cannot separate agents: a verified artifact shows the work exists and the harness link rests on the reviewed entry.
- **Not evidence:** tmux `session_activity` (one poller touched 18 sessions within 180 s), mentions, document names like `CODEX-21-...`.
- **Still a floor:** a worker with no ID in its titles and no mapping entry is missed. Unknowns: roles with no label, unattributed workers, reuse of pre-window sessions, the native-agent count.
- **Privacy:** private handoffs and pane tails were read for IDs and state classes only; the output holds names, sha256, times and classes, no text.
