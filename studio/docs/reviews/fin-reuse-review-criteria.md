# Review criteria: reuse of the fin EI_crit Claim at 0.9x and 1.1x (pre-registered)

Written by the independent reviewing agent **before** any author protocol or result was seen. Review process: an independent AI agent
process (actor `fin-reuse-reviewer`, operator `independent-review-agent`). It is **not** an independent laboratory and **not** a human
reviewer, and nothing here is biological acceptance. This file authors no output record and accepts nothing.

## Target
Exact Claim `node-a/eng-finmech-claim-ei-crit@4998ef85bd98ec64c0f4bc86e77337ea25df7ff5683ac6b62dc9095cf5f62f57`
(read from the public `/api/record` route: kind Claim, issuer `importer`, local status `imported_unreviewed`, head; payload `prior_review`
= none). Its statement: for the declared request (canonical sha256 prefix `f276a86069b8577d`) EI_crit = 1323/2048000 N m^2, binding
limit `tip_over_L`. The Claim's own limitations say the producer's code made both claim and result, nothing re-ran it, EI is an assumed
range, and the load is a declared pressure proxy.

## Expected values, derived by hand before the runs (exact rationals; I did not run the producer's `beam.py`)
Declared inputs read from `engineering/fin_mechanics/example_request.json`: rho 1.225, V 5, CL 1, b 3/2, ray length 1/5 of semispan
(L = 3/20 m), tributary width 1/100 m, limits tip/L <= 1/10 and slope <= 1/5 rad.

* p = rho V^2 CL / 2 = 245/16 Pa; q = p * width = 49/320 N/m.
* Uniform-load cantilever: tip = q L^4 / (8 EI), slope = q L^3 / (6 EI).
* EI_tip = (5/4) q L^3 = **1323/2048000** (equals the Claim's number exactly); EI_slope = (5/6) q L^3 = 441/1024000; binding = tip.

| Candidate | EI (N m^2) | tip/L | tip (m) | slope (rad) | expected verdict |
|---|---|---|---|---|---|
| 0.9 x EI_crit | 11907/20480000 = 5.81396484375e-4 | 1/9 = 0.1111 | 1/60 = 0.016667 | 0.14815 | **outside** the tip limit, slope within |
| 1.1 x EI_crit | 14553/20480000 = 7.10595703125e-4 | 1/11 = 0.0909 | 0.013636 | 0.12121 | **within** both limits |

Anything else, or a candidate EI that is a rounded float and not the exact rational times 9/10 or 11/10, is a finding.

## What a passing author protocol must show (gates, checked in this order)
1. **Exact Claim consumed before the runs.** The run record cites the full 64-hex version above (not the id, not a prefix, not "head"),
   and the read of that version precedes the run start in the record's own timestamps. A wrong or truncated pin must be refused.
   The request used hashes to the Claim's declared canonical sha256 (prefix `f276a86069b8577d`), so the reuse is under the same declared example.
2. **Candidates are 0.9 and 1.1 of the Claim's exact EI_crit,** nothing else varied (rho, V, CL, width, L, limits, mesh).
3. **FEM against closed form.** Finite-element tip and slope agree with the closed forms above, and a stated mesh-convergence result
   exists. For constant EI and uniform load a Hermite-cubic solution should match to round-off; a large residual is a finding.
   I will recompute with my own code (closed form plus an independent numerical integration of M/EI), not by calling the author's.
4. **Controls that can fail.** Zero load gives zero deflection and slope and no validity violation at any EI. Mutation controls
   (e.g. L^3 to L^2, factor 8 to 3, tip and slope limits swapped, 0.9 and 1.1 swapped) must each be detected, with the mutated value
   shown beside the real one. A control that cannot fail, or a mutation that is not reported, does not count.
5. **Source and domain limits stated in the output itself:** declared example only; EI assumed, not a fin-ray measurement; load is a
   mean lift-pressure proxy; Euler-Bernoulli, linear, static; slenderness is **not** checkable because no ray thickness is declared;
   no fluid-structure coupling; no extrapolation to other rho, V, CL, width, length; evidence kind `SimulationResult`/derived, never
   `Observation`. A statement that 0.9/1.1 results say anything about a fish is a finding.
6. **No mutation of the original Claim.** New records link to the exact version by a typed edge; the Claim keeps its own status.

## How the verdict will be scoped
The store's policy (`frontier-independent-review-0.1`, `Store.review`) lets an `accepted` decision pass only when **every one of seven
dimensions** is `passed` or `not_applicable` and `target_fidelity` and `applicability` are both `passed`. I will not mark
`independent_replication` or `empirical_relevance` `not_applicable` to make a record acceptable: they are `insufficient` or `unreviewed`
unless there is an actual replication or measurement. So the likely honest outcome for a reuse computation of this kind is a
**non-accepted, explicitly scoped review** (for example `disputed` or `rejected` with limitations, or no decision), which is a root
decision about what the system should do with a correct-but-unreplicated simulation, not a failure of the author. Raised now so it is
not discovered at the end.

Also required by the store: the reviewer's operator must differ from the submitter's operator of the target, and the reviewer actor
must not be the issuer. If the author's records are submitted under `independent-review-agent`, the review will be refused.

## Credential handling
The reviewer credential file named in the task has been listed (mode 600, owner only) and **not opened, printed or copied**. It will be
read only by the submit call, from the file, and never written to the repo, a message or a log.
