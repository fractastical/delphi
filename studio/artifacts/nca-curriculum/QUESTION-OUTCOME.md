# Question outcome: targeted repair and persistence trade off

The declared comparison completed: eight final 2000-step models, four matched initialization pairs, all 192 design probes and eight separate erased controls. **Baseline 45/96 versus curriculum 44/96: no aggregate benefit in these declared probes.** Overall 89/192 design predicates passed; all failed predicates remain in the raw records.

| Endpoint family | Three-circle baseline | Prefix curriculum |
| --- | --- | --- |
| persistence | 9/12 | 3/12 |
| new-left-prefix-30 | 0/12 | 9/12 |
| new-left-prefix-34 | 0/12 | 3/12 |
| new-left-prefix-38 | 0/12 | 0/12 |
| new-right-suffix | 12/12 | 11/12 |
| new-oblique-root | 0/12 | 0/12 |
| new-disk-hole | 12/12 | 11/12 |
| new-horizontal-slab | 12/12 | 7/12 |

Targeted prefix30/34 repair improved while persistence declined. This is a computational pattern tradeoff, not tissue regeneration. Each row's twelve probes share four learned models per regime and are dependent. The replicate units are the four paired initializations. Their all-design curriculum-minus-baseline fractions are [-0.25, 0.0, 0.0, 0.20833333333333334]; mean -0.0104167. These are descriptive comparisons, not a biological success probability or a population effect estimate. The full predeclared per-pair endpoint breakdown is in audit.json; no best model is substituted for the ensemble.

The eight erased-state controls are excluded from 192 and establish only the rule's absorbing-zero behavior. All cases use independently committed fresh update seeds and damage masks, but the same fixed design target. Old 0/48 and 32/48 experiments remain unchanged and have different evaluation sets; those rates are not directly compared as a new benchmark improvement.

The frozen auditor checked 441 native file digests, all 200 identities, eight checkpoint pins, four matched initialization/update budgets, guard order and selected all-channel damage states. 360 metric reductions differ bit-for-bit, maximum 2.2204460492503131e-16; exact reproduction is False. The separately frozen fixed-roundoff diagnostic is True. No threshold or outcome was changed. Intermediate unsaved whole-state assertions still rely on source-pinned saved metrics; there was no independent training rerun.

The movie contains 26 actual saved frames for each of the eight preselected prefix34 trajectories, including before/after erasure at update256. It does not show long-horizon persistence, so read the persistence table alongside the movie. Display clipping does not affect metrics. Pixels, updates and twelve hidden channels have no measured biological interpretation.

Next open question: can a separately preregistered local-rule or training-policy comparison retain the observed repair gains without losing persistence, using new evaluation cases? No new job is proposed before this result is reviewed. Material mechanics, genetic implementation, nervous systems and organism feasibility remain unsupported bridges.
