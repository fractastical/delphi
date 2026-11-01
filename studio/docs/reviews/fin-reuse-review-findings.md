# Independent review findings: fin Claim reuse at 0.9x and 1.1x EI_crit

Reviewer: an independent AI agent process (actor `fin-reuse-reviewer`, operator `independent-review-agent`). Not an independent laboratory,
not a human, and no biological acceptance. Criteria were committed before any author output (`fin-reuse-review-criteria.md`, 11fa785).
Author checkout read at `02bb06a258a4` (read-only worktree; `git status` empty before and after my replays).

## Checked, with what I ran
| Check | Result |
|---|---|
| Source pins | `source-request.json` sha256 = protocol's `943b8f64...`; `source-result.json` = `971aa005...`; request canonical sha256 starts `f276a86069b8577d` (my own canonicalisation: sorted keys, compact separators); all as the Claim declares |
| Artifact hashes | every artifact listed in both Evidence records (9 each) matches the committed file's sha256 and byte size; no mismatches |
| Exact Claim consumed | `claim-read-before-run.json` in both cases is identical to the live public record of `node-a/Claim/eng-finmech-claim-ei-crit@4998ef85...`; EI_crit parsed by my own regex = 1323/2048000 |
| Independent derivation | by hand with exact fractions from the request's declared inputs: q = 49/320, L = 3/20, EI_tip = 1323/2048000 (= the Claim, exactly), EI_slope = 441/1024000 |
| Candidates | author's solver EI equals 0.9 and 1.1 times the exact rational (11907/20480000 and 14553/20480000), margins `9/10` and `11/10`, nothing else varied |
| Results vs my closed form | below: tip/L = 1/9 exact, slope 4/27, invalid at the 1/10 tip limit; above: tip/L = 1/11, slope 4/33, valid. The author's tip/L 0.111111111158 and 0.090909090883 and slopes 0.148148148207 and 0.121212121180 agree with these to 4.2e-10 |
| Own FEM | my own Hermite-cubic assembly (not the author's code), 16/32/64 elements: relative tip error vs exact 1e-12 to 7e-11; difference from the author's tip and slope at most 5.1e-10 |
| Replay of author code | `compute()` run in my own output dir, 1 CPU, 4 GiB, swap 0, TasksMax 128: `effective-inputs.json` equal apart from the timestamp, validity and controls equal, tip difference 0.0, `profile.csv` byte-identical, both cases |
| Controls | zero load gives exactly 0.0 m; the L^3 mutant has relative error 5.67 and is rejected; my positive control (unmutated record) runs, and five altered Claim records (version, id, statement EI, source locator, binding-limit text) are each refused, all by the Record digest check |

## Findings (none changes the numerical result)
1. **Inherited limitation text.** Limitation 0 of both Evidence records is copied from the source Claim: "Frontier did not execute this and no one has re-run it ... not independent evidence". For these Evidence records it is wrong in the conservative direction (an agent did execute them), and it reads as a statement about the Evidence. Recommend relabelling it as the source Claim's limitation.
2. **"Mesh convergence" is round-off, not convergence.** For constant EI and a uniform load the Hermite element is exact at the nodes, so the 16/32/64 results differ only by round-off, and the author's error grows with refinement (1.4e-12, 5.7e-11, 4.2e-10). It shows exactness to round-off, not a convergence rate. No finding against the values.
3. **Mutation controls are caught by the digest check.** The altered-Claim controls are refused because the record digest no longer matches, which is a real refusal but is not the "full scope gate rejects inconsistency" the Action names; I did not exercise that second gate in isolation.
4. **Margins only in a digest in the Actions.** The 0.9/1.1 margins are in the frozen protocol and effective inputs, but not in the Action payloads, which carry them only inside the `parameters` cache-key digest.

## Not checked
The producer's `workflow.py` MCP transcripts and timestamps (I did not re-verify the read-before-run order beyond the identical before-run record and the Action/Evidence `retrieved_time`s), the coordinator's readiness step, edge-by-edge graph contents (the Claim's graph read showed `qualifies`, `produced_by`, `uses` edges but I did not trace each endpoint), hosted-byte availability (artifacts are reference-only URNs, licences null), Euler-Bernoulli slenderness (no thickness is declared), and anything about a real fin.

## What this does and does not support
Supports: for the declared example, the computed domain verdicts (0.9x outside the tip limit, 1.1x inside) are correct, reproducible, and independently recomputed in closed form and by a separate FEM.
Does not support: any statement about a fish, a measured fin-ray stiffness or load, fluid-structure behaviour, or that EI_crit is meaningful beyond the declared surrogate. No independent non-computational replication and no empirical data exist for this scope.
