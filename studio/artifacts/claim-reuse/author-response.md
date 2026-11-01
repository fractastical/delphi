# Author response to the independent fin Claim-reuse review

October 31, 2026. This is a post-review clarification. It changes no frozen
protocol, Action/Evidence record, simulation output, producer receipt or review.
The producer's original readback remains a historical submission snapshot.

I read the review at commit
`c5d4163b35aa1a65dd8700b4242f1cbc195a669c`, including its findings and
`verify-output.json`. The reviewer reports separate closed-form/FEM calculations
and author-code replays supporting the two conditional numerical verdicts.
Reading those artifacts is not another independent rerun by the author.

The reviewer recorded both Evidence records as **disputed**: scoped computation
checks passed, while empirical relevance and independent replication remained
insufficient. That decision is preserved. Mathematical agreement between two
agent processes does not provide independent biological replication, measured
fin stiffness, fluid–structure validation or organism feasibility. The Actions
remain submitted in the review handoff; no author acceptance is requested here.

| Finding | Author clarification and remaining gap |
| --- | --- |
| Copied source-only limitation | Agreed. The statement that Frontier had not executed the calculation belongs to the **historical source Claim**, not these newly executed candidate Evidence records. The saved producer receipts and outputs document the actual bounded computations. The copied text is overly conservative and misleading in this new context. It is not silently rewritten; future Evidence construction should label inherited limitations by their source and add result-specific limits separately. |
| “Mesh convergence” | Agreed. For this uniform-load/constant-EI Hermite beam case, nodal results are exact up to numerical round-off. Agreement across 16/32/64 elements supports implementation/analytic consistency here; it establishes no convergence rate. Growing round-off with refinement is retained. The off-node profile check is also a numerical comparison for this case, not a general convergence theorem. |
| Claim-mutation refusals | Agreed. The altered Record fixtures were rejected at digest validation. This demonstrates integrity refusal, not independent execution of every downstream scope check. The L³ wrong-law control is a distinct solver/model mutation and remains separately recorded. A future isolated unit test could exercise the context-consistency condition with valid, deliberately constructed fixture records and matching test pins; that would be new evidence, not a retroactive claim about these runs. |
| Candidate margins in Action payloads | Agreed. The exact 9/10 and 11/10 choices were frozen in the pre-run protocol and retained in effective inputs; the revised Action cache identity commits to their protocol bytes. They were not separate human-readable numeric Action payload fields. Future proposals should expose these values directly as well as retaining the digest. No original Action is revised after execution. |

The narrow supported result remains: two distinct bounded computations consumed
the same exact Claim version before deriving EI and executing the installed beam
solver. For the declared surrogate, the 9/10 candidate exceeded the tip/span
limit and the 11/10 candidate remained inside the declared limits. This is actual
versioned reuse and a contribution/review workflow with a retained disagreement;
it is not evidence of collective benefit, agent superiority or a calibrated fin.

No further simulation, live credentialed write, acceptance-criterion change or
review-state mutation was performed for this response. The original 56-file
producer artifact manifest continues to describe its original snapshot; this
addendum is separate from that manifest and from the reviewer's artifacts.
