# Matched damage curriculum: actual returned computation

Native status: **complete**. Fixed design predicates passed **89/192 declared**, 192 executed. Erased-state absorbing controls passed **8/8 declared**, 8 executed; these are outside the design denominator. Completed final checkpoints: 8/8. Missing evaluation identities: 0. All eight candidates and incomplete/failed arms are retained.

| Paired initialization | Endpoint family | Three-circle baseline | Prefix curriculum | Curriculum minus baseline fraction |
| --- | --- | --- | --- | --- |
| 20261102 | all_design | 12/24 (24 executed) | 6/24 (24 executed) | -0.25 |
| 20261102 | persistence | 3/3 (3 executed) | 0/3 (3 executed) | -1.0 |
| 20261102 | damage | 9/21 (21 executed) | 6/21 (21 executed) | -0.14285714285714285 |
| 20261103 | all_design | 12/24 (24 executed) | 12/24 (24 executed) | 0.0 |
| 20261103 | persistence | 3/3 (3 executed) | 3/3 (3 executed) | 0.0 |
| 20261103 | damage | 9/21 (21 executed) | 9/21 (21 executed) | 0.0 |
| 20261104 | all_design | 12/24 (24 executed) | 12/24 (24 executed) | 0.0 |
| 20261104 | persistence | 3/3 (3 executed) | 0/3 (3 executed) | -1.0 |
| 20261104 | damage | 9/21 (21 executed) | 12/21 (21 executed) | 0.14285714285714285 |
| 20261105 | all_design | 9/24 (24 executed) | 14/24 (24 executed) | 0.20833333333333334 |
| 20261105 | persistence | 0/3 (3 executed) | 0/3 (3 executed) | 0.0 |
| 20261105 | damage | 9/21 (21 executed) | 14/21 (21 executed) | 0.23809523809523808 |

The four training initialization pairs are the replicate units. Three update seeds and eight endpoint families probe the same learned weights and are dependent. These fractions and differences are descriptive of the declared computational scenarios, not independent biological replicates, biological-success probabilities or evidence of a general curriculum benefit. Inspect persistence separately from damage to expose a possible tradeoff. Partial evaluations have no substituted denominator or invented outcome.

The intervention replaces exactly one of three circular erasures with a staged left-prefix erasure. The remaining circles, initialization, optimizer, raw RGBA loss, stochastic-update budget and target are matched within each pair. All eight final 2000-step weights were prescribed before evaluation; there is no best-model selection. New independently committed masks and update seeds are used here; the original zero-pattern failure and prior seed-placement result remain unchanged.

Target: one synthetic-colored 64×64 raster of the biological-v3a fin design, not an observed cell/tissue image. The shared local rule is adapted from [Growing Neural Cellular Automata, Model and Experiments 2–3](https://distill.pub/2020/growing-ca/). Its 12 hidden channels have no measured biochemical meaning. Pixels and updates have no measured cell-size or biological-time mapping. A computational pattern is not DNA, neural control, tissue regeneration or a feasible organism.

Criteria were fixed before training: raw RGBA MSE≤.02 AND alpha>.1 silhouette IoU≥.75. Persistence requires all saved checkpoints256–2048; recovery requires a valid pattern before erasure at256 and after512 recovery updates. Failure to establish the pre-damage pattern fails recovery. Negative all-erased state tests are separate.

Returned-byte audit checked 441 files/20862541 bytes against the native receipt, pinned execution snapshots, source hashes and protocols. Checkpoint barrier and read-guard events are checked. Independent commitment plus a source-order guard is not cryptographic secrecy when plaintext files ship with the job. Guard coverage is the configured mask path in the cooperative frozen program, not protection against an adversarial reader.

Final visible-state metrics are recomputed from every returned raw final RGBA. Selected trajectory visible metrics and the all-channel before/after damage operator are also checked. Persistence at checkpoints without saved whole states and all-erased hidden-state zero rely on source-pinned saved metrics; this is not a training/trajectory replication. Bit-for-bit metric reproduction: False; 360 nonexact comparisons, maximum absolute discrepancy 2.2204460492503131e-16. Separately named fixed-roundoff diagnostic (rtol1e-10,atol1e-12): True. Neither replaces the original exact outcome or changes a criterion.

Actual device: NVIDIA H100 80GB HBM3. Environment: {'python': '3.12.3', 'torch': '2.10.0a0+b4e4ee81d3.nv25.12', 'numpy': '2.1.0', 'cuda_runtime': '13.1'}. Science wall time: 1481.069s. Dollar cost unknown. Protocol SHA256 b0a79db35b7823d31946ab2d26c51e99da8f59badce2edcb641619a1a7f3baa8; receipt SHA256 278a03f9f26d12a54aa9da406c08ccdbb8101790a2b0d963138fdd5a683ec0c4. Checkpoints omit the training pool and do not provide exact resume. Full provenance and per-case values are in audit.json and the native files.

Movie panels show only the eight preselected new-left-prefix-34/first-update-seed histories. There is no interpolation or replacement by a more successful case. RGBA clipping is display-only; reported metrics use raw values. All-channel snapshots and raw failure records remain available. Empirical biological validation remains unknown.
