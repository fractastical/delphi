# Amendment 2 (registered before any retry result): the first GPU attempt failed the network CPU/CUDA control

Single-reader, not independently reviewed. The frozen source (`rd_ddpm.py` `25455430…`, `config.json` `bc77ebc5…`, `job.sh`, PREREG, packet `76eb4a7b…`) and every tolerance are unchanged. Dispatch and the numerical-backend wrapper belong to infra_director; this file records only what the pilot's report must disclose.

## What happened (from infra's return, `infra-to-diffusion.md` 15:53 PDT; I have not seen the file itself)
* Job `aijob-e00cz0vk0jepf7j2fc`: the control gate in `rd_ddpm.py control` failed **before any dataset or training**: network CPU-vs-CUDA max abs difference 0.0011919 against the unchanged tolerance 1e-3; solver CPU-vs-CUDA parity 5.95e-14 passed. CUDA 13.1, Torch 2.10.0a0+nvidia25.12, numpy 2.1.0. The gate worked as designed: no checkpoint and no held-out data were generated. This attempt stays on the record as a failed attempt; it is not deleted or re-described as a pass.

## Disclosure rules for any retry
1. The control tolerance (1e-3 abs on the untrained network's output) is **not** loosened. A retry that passes only because a backend precision setting was changed is a retry under that setting, and the setting is reported next to every result.
2. Likely cause (a hypothesis for infra's diagnostic, not a finding): reduced-precision (TF32) convolutions are on by default in cuDNN and are far less precise than the CPU float32 reference; the frozen source sets no precision flags. Infra's predeclared default-versus-IEEE-FP32 diagnostic tests exactly this. I have no GPU and have not tested it.
3. If training then runs with strict FP32 flags supplied by the wrapper rather than by the frozen source, the **source hash is unchanged but the numerical regime is a declared run parameter**. The report states: the exact flags (cudnn.allow_tf32, matmul precision), who set them, and that the first attempt was the default regime. The strict-control receipt and the diagnostic receipt are cited, not summarised away.
4. The retry is a new attempt of the same frozen design, not a tuned model. Hyperparameters, splits, steps and seeds are the frozen ones; nothing is chosen using held-out output. If the diagnostic shows the control fails even under strict FP32, the pilot stays blocked and is reported as such.
5. Throughput under strict FP32 may differ from the default regime: timings are reported for the regime actually used, with no speedup claim.
6. The audit (`audit_result.py`), the model card and Amendment 1 apply unchanged. An independent collector audit by infra is welcome; semantic differences between the two audits will be reported rather than reconciled silently.
