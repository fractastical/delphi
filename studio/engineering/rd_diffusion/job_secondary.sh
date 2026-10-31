#!/usr/bin/env bash
# SECONDARY packet controller (AMENDMENT_1/3). Not the primary run. Inputs supplied by infra: CKPT (the returned frozen checkpoint.pt) and PRIMARY (its evaluation.json).
# The numerical policy (explicit FP32, infra backend-policy.json sha256 3a59246b...) is set by launch_secondary.py before torch is imported and verified by secondary_eval.py.
set -euo pipefail
cd "$(dirname "$0")"; OUT="${OUT:-out2}"; mkdir -p "$OUT"
sha256sum -c MANIFEST_secondary.sha256                                         # hash/import check only
python3 -c "import torch, numpy; print('imports ok', torch.__version__, numpy.__version__)"
[ "${PREFLIGHT:-0}" = "1" ] && exit 0
: "${CKPT:?set CKPT}"; : "${PRIMARY:?set PRIMARY}"
python3 - <<PY                                                                  # the checkpoint must be the one the primary evaluation recorded
import hashlib, json, os
want = json.loads(open(os.environ["PRIMARY"]).read())["train"]["checkpoint_sha256"]; got = hashlib.sha256(open(os.environ["CKPT"], "rb").read()).hexdigest()
assert want == got, f"checkpoint sha256 mismatch: {got} != {want}"
PY
python3 launch_secondary.py control --out "$OUT"                          # same CPU/CUDA gate as the primary, under the primary explicit-FP32 policy (set before torch is imported)
python3 launch_secondary.py secondary --ckpt "$CKPT" --primary "$PRIMARY" --out "$OUT"
tar -czf "$OUT/part_secondary.tgz" -C "$OUT" control.json secondary_evaluation.json generated_ensemble_full.npz examples.npz
ls -l "$OUT/part_secondary.tgz"; sha256sum "$OUT/part_secondary.tgz"
