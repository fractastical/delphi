#!/usr/bin/env bash
# Bounded Morpheus epithelial J-scaling sweep. CPU only, one thread per arm, no git.
#
#   bash run_packet.sh [OUTDIR] [WORKERS]
#
# Needs: curl, sha256sum, tar, python3, timeout, setsid, xargs.
#
# Repairs after infra source review of packet 4f33453:
#  R1 BIN is exported, so xargs children reach the solver. Previously it was not, and every
#     child received an empty path.
#  R4 the binary and all scratch live in WORKSPACE, OUTSIDE the scientific output tree, so an
#     automatic collector sweeping OUTDIR never picks up a 15 MB executable. A receipt of the
#     binary (url, bytes, sha256, environment) is written into OUTDIR instead of the binary.
#     The download is bounded in bytes as well as seconds, its HTTP status is checked, and the
#     exact hash is verified before it is ever executed.
#  R5 each arm runs in its own process group under an explicit timeout, and the group is killed
#     on expiry. Whole-job limits, worker count and the output cap are declared below and
#     enforced.
#  R3 the run NEVER decides its own success. audit_completeness.py is the exit status.
set -u -o pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
OUT=${1:-$HERE/out}
WORKERS=${2:-8}

# ---- declared bounds (soft = per arm, hard = whole job) -----------------------------------
ARM_TIMEOUT_S=${ARM_TIMEOUT_S:-600}          # soft, per arm
ARM_KILL_GRACE_S=30
JOB_TIMEOUT_S=${JOB_TIMEOUT_S:-5400}         # hard, whole job: 240 arms / 8 workers at 31 s
                                             # measured maximum is ~930 s + setup; 5400 is 5x headroom
OUTPUT_CAP_MB=${OUTPUT_CAP_MB:-512}          # total scientific output
DOWNLOAD_CAP_BYTES=${DOWNLOAD_CAP_BYTES:-67108864}   # 64 MB; the binary is ~15 MB
BIN_URL=https://gitlab.com/morpheus.lab/morpheus/-/package_files/178666119/download
BIN_SHA=3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad

WORKSPACE=${PACKET_WORKSPACE:-$(mktemp -d -t epi-packet-XXXXXX)}
mkdir -p "$OUT" "$WORKSPACE"
BIN=${PACKET_BIN:-$WORKSPACE/morpheus-2.3.9}   # PACKET_BIN is for the control fixtures only

echo "workspace (not collected): $WORKSPACE"
echo "output    (collected)    : $OUT"

# ---- 1. verify the packet against its own manifest before anything runs ------------------
python3 "$HERE/verify_packet.py" --dir "$HERE" || { echo "packet verification failed; refusing"; exit 3; }

# ---- 2. fetch and verify the solver, bounded, outside OUT --------------------------------
if [ -z "${PACKET_BIN:-}" ]; then
  if [ ! -x "$BIN" ]; then
    code=$(curl -sS -L -m 600 --max-filesize "$DOWNLOAD_CAP_BYTES" \
                -w '%{http_code}' -o "$BIN.part" "$BIN_URL") || {
      echo "download failed (curl exit $?, http $code); refusing"; exit 3; }
    [ "$code" = "200" ] || { echo "download HTTP $code, expected 200; refusing"; exit 3; }
    mv "$BIN.part" "$BIN"
  fi
  got=$(sha256sum "$BIN" | cut -d' ' -f1)
  [ "$got" = "$BIN_SHA" ] || { echo "binary sha256 $got, pinned $BIN_SHA; refusing"; exit 3; }
  chmod +x "$BIN"
fi
python3 - "$BIN" "$BIN_URL" "$OUT/binary-receipt.json" <<'PY'
import hashlib, json, platform, subprocess, sys, os
b, url, out = sys.argv[1], sys.argv[2], sys.argv[3]
d = open(b, 'rb').read()
json.dump({"url": url, "bytes": len(d), "sha256": hashlib.sha256(d).hexdigest(),
           "note": "the binary itself is deliberately NOT in this output tree",
           "uname": platform.uname()._asdict(), "python": sys.version.split()[0],
           "nproc": os.cpu_count()}, open(out, 'w'), indent=1)
PY
echo "solver verified; receipt at $OUT/binary-receipt.json"

# ---- 3. run the arms -----------------------------------------------------------------------
run_one() {
  a=$1
  d="$OUT/$a"
  mkdir -p "$d"
  cp "$HERE/models/$a.xml" "$d/model.xml"
  # own process group, killed as a group on timeout
  ( cd "$d" && OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 \
      setsid timeout --kill-after="$ARM_KILL_GRACE_S" --signal=TERM "$ARM_TIMEOUT_S" \
        "$BIN" -f model.xml --no-gnuplot --num-threads 1 > stdout.log 2>&1
    echo "exit=$?" > exit.txt )
  # frames are never needed for a threshold sweep and would blow the output cap
  rm -f "$d"/*.tif "$d"/*.tiff "$d"/model_graph.dot 2>/dev/null
  return 0          # deliberately: per-arm success is decided by the audit, never here
}
export -f run_one
export BIN OUT HERE ARM_TIMEOUT_S ARM_KILL_GRACE_S      # R1: BIN was missing here

ARMS=$(python3 -c "import json,sys;print('\n'.join(a['name'] for a in json.load(open('$HERE/arms.json'))))")
echo "$ARMS" | timeout --kill-after=60 "$JOB_TIMEOUT_S" \
  xargs -P "$WORKERS" -I{} bash -c 'run_one "$@"' _ {}
job_rc=$?
echo "xargs/job wrapper exit=$job_rc (NOT the result; see the audit below)"

# ---- 4. output cap --------------------------------------------------------------------------
SZ=$(du -sm "$OUT" | cut -f1)
echo "scientific output: ${SZ} MB (cap ${OUTPUT_CAP_MB} MB)"
if [ "$SZ" -gt "$OUTPUT_CAP_MB" ]; then
  echo "output cap exceeded; refusing to package"; exit 4
fi

# ---- 5. the audit IS the exit status --------------------------------------------------------
python3 "$HERE/audit_completeness.py" --arms "$HERE/arms.json" --out "$OUT" \
        --job-wrapper-exit "$job_rc" --report "$OUT/completeness.json"
audit_rc=$?

tar czf "$OUT/../epithelial-sweep-result.tgz" -C "$OUT" .
echo "result tarball sha256: $(sha256sum "$OUT/../epithelial-sweep-result.tgz" | cut -d' ' -f1)"
echo "completeness audit exit=$audit_rc"
exit "$audit_rc"
