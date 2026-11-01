# Actual inverse-pattern NCA experiment

**Execution: complete. Design tests: 32/48 declared passed, 48 executed.** Completing training is separate from achieving the target. Empty-state negative controls: 4/4 declared passed.

| Frozen candidate | Actual training steps | Status | Design predicates |
| --- | --- | --- | --- |
| undamaged-pool-s20261031 | 2000 | complete | 6/12 executed |
| damage-pool-s20261031 | 2000 | complete | 9/12 executed |
| undamaged-pool-s20261101 | 2000 | complete | 8/12 executed |
| damage-pool-s20261101 | 2000 | complete | 9/12 executed |

Of the executed design tests, 3 end with exactly zero raw RGBA. An empty field fails the target predicate. Under this rule, the activity mask makes the empty full state absorbing. Current seed_xy is [7, 41]; membership in target silhouette: True. The original projected root[8,42] lies outside the silhouette, one pixel from foreground. The additive experiment tests seed placement as a possible mechanism without replacing that original failure or presuming a repair.

The goal is a fixed 64×64 design raster of the existing biological-v3a pectoral fin/rays (653 foreground pixels), with synthetic colors. It is **not an observed tissue or cellular image**. The computational seed_xy is [7, 41]. Computational updates/pixels have no biological time/cell-size calibration.

## Implemented rule and inverse objective

The shared 16-channel rule computes identity and two Sobel perceptions, a 48→128 ReLU→16 residual, then stochastic per-cell updates (fire probability0.5). Pre/post alpha-neighborhood masks restrict activity. Learned perception is3×3; composing the activity masks makes total one-step dependency5×5. The 12 hidden channels have no measured biochemical identity. There are8336 learned parameters.

Adam minimizes raw RGBA mean-square error to the design goal. Both regimes use the same pool128, batch8, unroll64–95, final2000-step budget and paired initialization/update schedules. Damage training additionally erases random circles. Final checkpoints are pinned before held-out masks load; no best-model or held-out selection occurs. This adapts [Distill2020, Model and Experiments2/3](https://distill.pub/2020/growing-ca/) and its [official notebook](https://github.com/google-research/self-organising-systems/blob/master/notebooks/growing_ca.ipynb); pool/budget/target/framework differ, so this is not an exact benchmark reproduction.

Evaluation uses three update seeds (reused from the parent: True; reused cases are not fresh untouched heldouts), persistence to1024 updates, and three fixed erasure masks after256 growth updates plus512 recovery updates. Match requires silhouette IoU≥0.75 and raw RGBA MSE≤0.02. Persistence requires every saved checkpoint256–1024; recovery requires a valid pre-damage pattern AND final recovery. All-erased controls test an absorbing zero state and are excluded from the48 design tests. Repeated probes share learned weights and source assumptions; counts are descriptive, not biological probabilities or independent biological replicates.

## Numerical and provenance checks

Same-job CPU controls passed: True; CPU/CUDA controls passed: True. The numerical tolerances were frozen before training and remain unchanged. 48 final metric comparisons differ bit-for-bit; maximum absolute difference 5.5511151231257827e-17. Exact reproduction remains false where recorded; the separately frozen roundoff comparison is not substituted for it. Returned-byte audit checked 128 files/9875825bytes; final visible-state metrics exact reproduction: False; separately named fixed-roundoff diagnostic: True. Predicate counts are recomputed from raw final RGBA plus saved per-checkpoint metrics. Hidden-state all-zero assertions rely on saved whole-state summary metrics except where full-state snapshots were preselected; this audit does not independently rerun training or every hidden-state trajectory.

Actual device: NVIDIA H100 80GB HBM3. Environment: {"cuda_runtime": "13.1", "numpy": "2.1.0", "python": "3.12.3", "torch": "2.10.0a0+b4e4ee81d3.nv25.12"}. Native science wall time: 710.833s. Dollar cost unknown/null. Final checkpoint barrier SHA256: 1c7b6b8e2a0c9c162694ee64117df3d8a3df44e9f943cfb822b2c0bbd3241d26. Protocol SHA256: 4976736fa66756f4fdf41d7b0b132db8ff3d8ddabe4602e62751f6a36aa57b11. Source hashes, final/periodic checkpoints, optimizer/RNG state, all52 evaluation records where executed, raw final RGBA, and eight preselected histories are retained. The training pool is not serialized: checkpoints do not promise exact training resume.

The video uses only actual selected central-square/update-seed7001 states; saved update256 before/after erasure are distinct phases. It does not interpolate physics or invent intermediate patterns. RGBA is clipped only for display; every loss/IoU uses raw state values. Simulation/training and render provenance remain separate.

## Applicability and next question

Pattern growth/recovery, if achieved, would establish only this computational local-rule design objective. It would not implement DNA, measured cell signaling, tissue material, fish neural control or organism feasibility. All failed target predicates, empty/collapsed patterns, incomplete arms and numerical failures stay visible. A further optimization repair would require a separately frozen experiment; this report does not alter the target, initial seed, loss, evaluation masks, thresholds or original results.
