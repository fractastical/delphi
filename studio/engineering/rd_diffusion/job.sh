#!/usr/bin/env bash
# Packet controller. PREFLIGHT=1 verifies hashes and imports only and never trains. Otherwise: preflight, CUDA+numerical control gate, then dataset -> train -> freeze -> evaluate.
set -euo pipefail
cd "$(dirname "$0")"; OUT="${OUT:-out}"; mkdir -p "$OUT"
python3 rd_ddpm.py preflight --out "$OUT"                       # exits here when PREFLIGHT=1 (handled inside rd_ddpm.py); also runs as the first gate otherwise
[ "${PREFLIGHT:-0}" = "1" ] && exit 0                            # preflight-only mode: nothing below runs
python3 rd_ddpm.py control --out "$OUT"                         # needs CUDA; writes control.json; non-zero exit blocks the run
tar -czf "$OUT/part1_setup.tgz" -C "$OUT" control.json
python3 rd_ddpm.py run --out "$OUT"                             # data (GPU solver) -> train -> frozen checkpoint -> held-out evaluation, timings, telemetry
tar -czf "$OUT/part2_model_eval.tgz" -C "$OUT" checkpoint.pt evaluation.json examples.npz train_loss.jsonl
ls -l "$OUT"/part*.tgz; sha256sum "$OUT"/part*.tgz
