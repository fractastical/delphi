# Self-hosted assessors

`run-assessor.mjs` runs a dataset-resolvability assessor against any OpenAI-compatible endpoint
and writes `claim-sources/<project>/assessment/raw/<assessor>/batch-N.json` in the shape the
subagent assessors produce, so `build/merge-assessments.mjs` and `generate-assessments.mjs`
treat it like GPT, Gemini or Grok. The model gets the project's `INSTRUCTIONS.md`, `rubric.json`
and one claim per request, with a JSON schema enforced by the server; it never sees `claims.json`,
the extraction or other assessors' outputs. Add the assessor to the project's `assessors.json`.

```sh
node scripts/assess/run-assessor.mjs --project aristotle-biology --assessor qwen \
  --model Qwen/Qwen3-32B-AWQ --base-url http://127.0.0.1:8000/v1 [--batches 1,2] [--concurrency 24]
```

Runs are resumable: claims already in the output file are skipped unless `--force`.

## The `qwen` assessor on NVIDIA Brev

Qwen3-32B (AWQ 4-bit) served by vLLM 0.32 on the `delphi-gpu` instance (massedcompute L40S,
46 GB). Zero per-token cost; about one claim per second at concurrency 24, so a 566-claim project
takes ten minutes. Setup, done once on the instance (`brev shell delphi-gpu` or `ssh delphi-gpu`):

```sh
uv venv ~/vllm --python 3.12 && uv pip install --python ~/vllm/bin/python vllm
uvx --from huggingface_hub hf download Qwen/Qwen3-32B-AWQ     # ~19 GB
```

Serve (in tmux; the instance firewall only allows SSH, so bind to localhost and tunnel):

```sh
tmux new -d -s vllm "VLLM_USE_FLASHINFER_SAMPLER=0 ~/vllm/bin/vllm serve Qwen/Qwen3-32B-AWQ \
  --host 127.0.0.1 --port 8000 --max-model-len 16384 --gpu-memory-utilization 0.92 --max-num-seqs 32"
```

`VLLM_USE_FLASHINFER_SAMPLER=0` is needed because the instance has no CUDA toolkit (`nvcc`) and
FlashInfer's sampler JIT-compiles. Startup takes about two minutes. From the laptop:

```sh
ssh -N -L 8000:127.0.0.1:8000 delphi-gpu &
```

Thinking mode is off (`chat_template_kwargs.enable_thinking: false`) and the output is
schema-constrained; thinking mode has not been compared. Stop the instance
(`brev stop delphi-gpu`) when nothing is queued; it bills while idle.
