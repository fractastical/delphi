#!/usr/bin/env bash
# EVALUATION-RECOVERY packet controller (separately declared; the original primary FAILED and stays failed). No training. Infra supplies the returned files:
#   CKPT=<checkpoint.pt>   (sha256 1a0a185cdacd49e8a65aa77ece1cd8f51033533c996025b3f4da907cd2b2ae76, 5,421,109 bytes)
#   TRAIN_LOG=<train_loss.jsonl>   (sha256 2ecdd2ceb6eec513a634ec7edcaf5e37cc15cba3d3717c90c5ad7ab41dc05862, 36,009 bytes)
# Exact FP32 policy (infra backend-policy.json sha256 3a59246b...1932) is set before torch is imported by BOTH launchers below.
set -euo pipefail
cd "$(dirname "$0")"
OUT="${OUT:-out}"; CONTROL_OUT="${CONTROL_OUT:-$OUT/control}"; RECOVERY_OUT="${RECOVERY_OUT:-$OUT/recovery}"
sha256sum -c MANIFEST_recovery.sha256                                             # packet member hashes
python3 -c "import torch, numpy; print('imports ok', torch.__version__, numpy.__version__)"
[ "${PREFLIGHT:-0}" = "1" ] && exit 0                                             # preflight-only: nothing below runs
: "${CKPT:?set CKPT}"; : "${TRAIN_LOG:?set TRAIN_LOG}"
echo "1a0a185cdacd49e8a65aa77ece1cd8f51033533c996025b3f4da907cd2b2ae76  $CKPT" | sha256sum -c
echo "2ecdd2ceb6eec513a634ec7edcaf5e37cc15cba3d3717c90c5ad7ab41dc05862  $TRAIN_LOG" | sha256sum -c
mkdir -p "$CONTROL_OUT"
python3 launch_secondary.py control --out "$CONTROL_OUT"                          # frozen control gate under the explicit FP32 policy; non-zero exit blocks the recovery
if [ -e "$RECOVERY_OUT" ] && [ -n "$(ls -A "$RECOVERY_OUT")" ]; then echo "recovery output dir must be new and empty" >&2; exit 3; fi
python3 launch_recovery.py --ckpt "$CKPT" --train-log "$TRAIN_LOG" --out "$RECOVERY_OUT"   # new empty directory; no flags that alter checkpoint or policy exist in production
tar -czf "$OUT/part_recovery_control.tgz" -C "$CONTROL_OUT" control.json
tar -czf "$OUT/part_recovery.tgz" -C "$RECOVERY_OUT" .
ls -l "$OUT"/part_recovery*.tgz; sha256sum "$OUT"/part_recovery*.tgz
