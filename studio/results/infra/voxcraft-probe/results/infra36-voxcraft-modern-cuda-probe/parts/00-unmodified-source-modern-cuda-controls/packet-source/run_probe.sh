#!/usr/bin/env bash
# voxcraft-sim modern-toolkit H100 compatibility probe. ONE arm. Not a sweep.
#
# Pins and budgets are frozen in probe.json. This script changes NO upstream source
# byte. Its only adapter action is passing architecture/configuration flags to cmake.
# If the build fails, the FIRST failure is captured and the script STOPS. There is no
# retry, no flag-shuffling and no source repair.
#
# Usage: run_probe.sh <workdir> [--no-dep-install]
set -uo pipefail
WORK="${1:?usage: run_probe.sh <workdir> [--no-dep-install]}"; shift || true
DEP_INSTALL=1; for a in "$@"; do [ "$a" = "--no-dep-install" ] && DEP_INSTALL=0; done
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$WORK"/{logs,out}; cd "$WORK"
R="$WORK/out/receipt.json"; L="$WORK/logs"
PIN=dd8668f99ff74fb2fc2ee60deb91287a3b519d8f
TARURL="https://codeload.github.com/voxcraft/voxcraft-sim/tar.gz/$PIN"
TARSHA=0a0f4fd105a8df21df8b62a7d00e5178096d28415f2fb9f1679f6c78fd2c6546
TARBYTES=1247489
SRC="$WORK/voxcraft-sim-$PIN"

# ---- hard outer wall. EVERYTHING is inside it: fetch, deps, configure, build, runs, pack.
HARD_DEADLINE_S=${HARD_DEADLINE_S:-900}
BUILD_CAP_S=600            # stage cap; the effective cap is min(this, time left)
RUN_CAP_S=120              # per case
PACK_RESERVE_S=25          # never spend the last seconds building
RETURN_MAX_BYTES=$((16*1024*1024))
T_START=$(date +%s)
left(){ echo $(( HARD_DEADLINE_S - ( $(date +%s) - T_START ) )); }
budget(){ # budget <stage-cap> -> min(stage cap, time left minus pack reserve)
  local cap="$1" rem; rem=$(( $(left) - PACK_RESERVE_S ))
  [ "$rem" -lt "$cap" ] && cap="$rem"; echo "$cap"; }

STAGE=start; STATUS=INCOMPLETE; BUILD_SECS=0
fin(){ # fin <status> <stage> [first-failure-file]
  trap - TERM INT EXIT
  STATUS="$1"; STAGE="$2"; local ff="${3:-}"
  # the excerpt is passed to python by PATH, as an argument. It is NOT passed through the
  # environment: an earlier version exported FIRST_FAIL *after* the python heredoc ran, so
  # every receipt carried an empty excerpt. selftest.sh fixture 1 pins this.
  python3 - "$R" "$STATUS" "$STAGE" "$ff" "$(left)" "$BUILD_SECS" <<'PY'
import json,sys,os
R,status,stage,ff,left,bsecs = sys.argv[1:7]
d=json.load(open(R)) if os.path.exists(R) else {}
d["schema"]="frontier.voxcraft-gpu-probe-receipt/1"
d["status"]=status; d["failed_stage"]=stage
d["seconds_remaining_in_outer_bound"]=int(left)
d["build_seconds"]=int(bsecs)
excerpt=""
if ff and os.path.exists(ff):
    with open(ff,errors="replace") as fh: excerpt=fh.read(4000)
d["first_failure_file"]=os.path.basename(ff) if ff else None
d["first_failure_excerpt"]=excerpt
json.dump(d,open(R,"w"),indent=1)
PY
  # ---- pack. The archive is written OUTSIDE the tree being archived, and exclusions come
  # BEFORE the operands. Measured with GNU tar 1.35: the previous form, which wrote into
  # out/ with --exclude after the operands, exited 2 AND embedded a copy of itself, and the
  # old code hid both by discarding stderr and never reading $?.
  #
  # NOTHING IN out/ IS EVER MODIFIED HERE. An earlier revision truncated the history files
  # to fit a transport cap while its own message claimed the full history stayed on the node.
  # It did not: head/mv had replaced the only copy. Scientific output is immutable. If the
  # archive cannot be produced or does not fit, that is a TRANSPORT failure, reported as
  # such, with the originals left exactly as the simulator wrote them. Incomplete evidence
  # is never promoted to a pass.
  local OUT="$WORK/probe-return.tar.gz"; rm -f "$OUT"
  # hash the science output BEFORE packing, so infra's native copy can be checked against it
  ( cd "$WORK/out" 2>/dev/null && sha256sum *.history 2>/dev/null ) > "$L/97-history-sha256.txt" 2>/dev/null || true
  tar --exclude='probe-return.tar.gz' -czf "$OUT" -C "$WORK" logs out; local trc=$?
  local bytes; bytes=$(stat -c%s "$OUT" 2>/dev/null || echo 0)
  local transport="OK"
  if [ "$trc" -ne 0 ]; then transport="TAR_EXIT_$trc"
  elif [ "$bytes" -gt "$RETURN_MAX_BYTES" ]; then transport="RETURN_TOO_LARGE_${bytes}B"
  fi
  python3 - "$R" "$transport" "$bytes" "$trc" "$RETURN_MAX_BYTES" "$L/97-history-sha256.txt" <<'PY2'
import json,sys,os
R,transport,b,trc,cap,shafile = sys.argv[1:7]
d=json.load(open(R)) if os.path.exists(R) else {}
d["transport"]={"status":transport,"archive_bytes":int(b),"tar_exit":int(trc),"cap_bytes":int(cap),
  "scientific_output_mutated":False,
  "policy":"out/ is never modified to fit a transport cap. On TAR_EXIT_* or RETURN_TOO_LARGE the "
           "originals are left intact for infra's native collector and the run exits non-zero."}
if os.path.exists(shafile):
    d["history_sha256"]=dict(reversed(l.split(None,1)) for l in open(shafile).read().split("\n") if l.strip())
    d["history_sha256"]={k.strip():v for k,v in d["history_sha256"].items()}
json.dump(d,open(R,"w"),indent=1)
PY2
  echo "PROBE-STATUS=$STATUS  STAGE=$STAGE  ELAPSED=$(( $(date +%s) - T_START ))s"
  echo "TRANSPORT=$transport  RETURN=$OUT  bytes=$bytes  tar_exit=$trc  self_member=$(tar tzf "$OUT" 2>/dev/null | grep -c 'probe-return.tar.gz')"
  # exit 0 ONLY when the science passed AND the evidence actually travelled intact.
  if [ "$STATUS" = PASS ] && [ "$transport" = OK ]; then exit 0; fi
  if [ "$transport" != OK ]; then
    echo "TRANSPORT FAILURE: originals in $WORK/out are untouched; collect them natively."
    exit 3
  fi
  exit 1
}
on_signal(){ echo "signal received in stage $STAGE"; echo "terminated by signal during stage $STAGE at $(( $(date +%s) - T_START ))s" > "$L/99-signal.txt"; fin DEADLINE_EXCEEDED "$STAGE" "$L/99-signal.txt"; }
trap on_signal TERM INT
deadline_guard(){ # deadline_guard <stage>
  if [ "$(left)" -le "$PACK_RESERVE_S" ]; then
    echo "outer ${HARD_DEADLINE_S}s bound reached before stage $1" > "$L/98-deadline.txt"
    echo "partial logs are preserved. A DEADLINE IS NOT A COMPILER FAILURE." >> "$L/98-deadline.txt"
    fin DEADLINE_EXCEEDED "$1" "$L/98-deadline.txt"
  fi; }

############ stage 0: environment / driver / device / image receipt ############
STAGE=preflight; deadline_guard preflight
# Only explicitly named, non-secret variables are recorded. A prefix match such as
# ^(NVIDIA_|CUDA_|NV_) would capture anything a future image happens to name that way,
# including a token. The allow-list cannot.
ENV_ALLOW="CUDA_VERSION CUDA_HOME CUDA_PATH CUDA_VISIBLE_DEVICES NVIDIA_VISIBLE_DEVICES
NVIDIA_DRIVER_CAPABILITIES NVIDIA_REQUIRE_CUDA NV_CUDA_LIB_VERSION NV_CUDNN_VERSION
NVIDIA_PRODUCT_NAME NVIDIA_BUILD_ID CUDNN_VERSION NCCL_VERSION"
{ echo "== date =="; date -u +%FT%TZ
  echo "== uname =="; uname -a
  echo "== nvidia-smi =="; nvidia-smi 2>&1 || echo "nvidia-smi ABSENT"
  echo "== nvidia-smi query =="; nvidia-smi --query-gpu=name,driver_version,compute_cap,memory.total --format=csv 2>&1 || true
  echo "== nvcc =="; (nvcc --version 2>&1) || echo "nvcc ABSENT"
  echo "== /usr/local/cuda =="; ls -ld /usr/local/cuda* 2>&1 || echo "no /usr/local/cuda*"
  echo "== cmake =="; (cmake --version 2>&1 | head -1) || echo "cmake ABSENT"
  echo "== g++ =="; (g++ --version 2>&1 | head -1) || echo "g++ ABSENT"
  echo "== os =="; head -3 /etc/os-release 2>/dev/null
  echo "== allow-listed env (exact names only; no prefix match, so no token can appear) =="
  for v in $ENV_ALLOW; do [ -n "${!v:-}" ] && echo "$v=${!v}"; done
  echo "== boost =="; ls /usr/include/boost/version.hpp 2>&1; ls /usr/lib/x86_64-linux-gnu/libboost_filesystem* 2>&1 || echo "no boost libs"
} > "$L/00-preflight.txt" 2>&1
python3 - "$R" "$L/00-preflight.txt" <<'PY'
import json,sys,re
R,pf=sys.argv[1],sys.argv[2]; t=open(pf,errors="replace").read()
g=lambda p,d=None:(re.search(p,t).group(1).strip() if re.search(p,t) else d)
json.dump({"schema":"frontier.voxcraft-gpu-probe-receipt/1","status":"RUNNING",
 "expected_image_digest":"nvcr.io/nvidia/pytorch@sha256:11e9976339d08669ede155cdbc601b1df5f57772fcee772b23527efc54e05602",
 "environment":{"gpu_csv":g(r"name, driver_version, compute_cap, memory.total\n([^\n]+)"),
   "nvcc_release":g(r"release ([\d.]+)"),"cuda_build":g(r"(Cuda compilation tools[^\n]*)"),
   "cmake":g(r"cmake version ([\d.]+)"),"gxx":g(r"g\+\+ \(([^\n]*)"),
   "nvidia_smi_present":"nvidia-smi ABSENT" not in t,"nvcc_present":"nvcc ABSENT" not in t,
   "cmake_present":"cmake ABSENT" not in t,"boost_present":"no boost libs" not in t},
 "env_capture_policy":"explicit allow-list of non-secret names; no prefix matching",
 "preflight_log":"logs/00-preflight.txt"},open(R,"w"),indent=1)
PY
grep -q "nvidia-smi ABSENT" "$L/00-preflight.txt" && fin NO_GPU preflight "$L/00-preflight.txt"
grep -q "nvcc ABSENT"       "$L/00-preflight.txt" && fin NO_CUDA_TOOLKIT preflight "$L/00-preflight.txt"
grep -q "cmake ABSENT"      "$L/00-preflight.txt" && fin NO_CMAKE preflight "$L/00-preflight.txt"

############ stage 1: fetch immutable public source, verify bytes ############
STAGE=fetch; deadline_guard fetch
curl -sL --max-time "$(budget 300)" --max-filesize 4000000 "$TARURL" -o src.tar.gz 2> "$L/10-fetch.txt"
GOTB=$(stat -c%s src.tar.gz 2>/dev/null || echo 0); GOTS=$(sha256sum src.tar.gz 2>/dev/null | cut -d' ' -f1)
{ echo "url=$TARURL"; echo "expected_bytes=$TARBYTES got_bytes=$GOTB"
  echo "expected_sha256=$TARSHA"; echo "got_sha256=$GOTS"; } >> "$L/10-fetch.txt"
if [ "$GOTB" != "$TARBYTES" ] || [ "$GOTS" != "$TARSHA" ]; then
  { echo "SOURCE BYTES DO NOT MATCH THE PIN. Stopping. No fallback is attempted here by design:"
    echo "a silent switch to another source would make the compiler result unattributable."; } >> "$L/10-fetch.txt"
  fin SOURCE_HASH_MISMATCH fetch "$L/10-fetch.txt"
fi
tar xzf src.tar.gz || fin SOURCE_EXTRACT_FAIL fetch "$L/10-fetch.txt"
python3 "$HERE/verify_pin.py" --root "$SRC" --pin "$HERE/source-pin.json" > "$L/11-verify.txt" 2>&1 \
  || fin SOURCE_FILE_HASH_MISMATCH verify "$L/11-verify.txt"

############ stage 2: confirm -DCUDA_ARCH actually bypasses autodetection ############
STAGE=cmake-inspect; deadline_guard cmake-inspect
{ echo "Checking, in the FETCHED bytes, that defining CUDA_ARCH skips the GPU-probing branch."
  grep -n 'if (NOT DEFINED CUDA_ARCH)' "$SRC/CMakeLists.txt"
  grep -n 'CUDA_SELECT_NVCC_ARCH_FLAGS(RET_ARCH_FLAGS)' "$SRC/CMakeLists.txt"
  grep -n 'Nvidia GPU not found. Abort.' "$SRC/CMakeLists.txt"
  grep -n 'list(APPEND CMAKE_CUDA_FLAGS -gencode=' "$SRC/CMakeLists.txt"
} > "$L/20-cmake-inspect.txt" 2>&1
grep -q 'if (NOT DEFINED CUDA_ARCH)' "$SRC/CMakeLists.txt" \
  || fin CMAKE_GUARD_ABSENT cmake-inspect "$L/20-cmake-inspect.txt"

############ stage 3: dependencies ############
STAGE=deps; deadline_guard deps
if ! ls /usr/lib/x86_64-linux-gnu/libboost_filesystem* >/dev/null 2>&1; then
  if [ "$DEP_INSTALL" = 1 ]; then
    { echo "Boost absent. Installing the four components CMakeLists.txt line 37 requires."
      echo "This is an AUTHORISED, RECORDED install, not a silent repair."; } > "$L/30-deps.txt"
    timeout -s TERM "$(budget 180)" bash -c 'apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        libboost-filesystem-dev libboost-thread-dev libboost-chrono-dev libboost-program-options-dev' \
      >> "$L/30-deps.txt" 2>&1 || fin DEP_INSTALL_FAILED deps "$L/30-deps.txt"
    { echo "== installed versions =="; dpkg -l | grep -i boost || true
      echo "== static lib hashes =="; sha256sum /usr/lib/x86_64-linux-gnu/libboost_{filesystem,thread,chrono,program_options}.a 2>/dev/null || true
    } >> "$L/30-deps.txt" 2>&1
  else
    echo "Boost absent and --no-dep-install was given." > "$L/30-deps.txt"
    fin DEP_MISSING_BOOST deps "$L/30-deps.txt"
  fi
else
  { echo "Boost already present."; dpkg -l | grep -i boost || true
    sha256sum /usr/lib/x86_64-linux-gnu/libboost_{filesystem,thread,chrono,program_options}.a 2>/dev/null || true
  } > "$L/30-deps.txt" 2>&1
fi

############ stage 4: configure (adapter action = these flags ONLY) ############
STAGE=configure; deadline_guard configure
mkdir -p "$SRC/build" && cd "$SRC/build"
timeout -s TERM "$(budget 120)" cmake .. -DCMAKE_BUILD_TYPE=Release \
         -DCMAKE_CUDA_ARCHITECTURES=90 \
         -DCUDA_ARCH=arch=compute_90,code=sm_90 > "$L/40-configure.txt" 2>&1 \
  || fin CONFIGURE_FAIL configure "$L/40-configure.txt"
grep -q "Using GPU Architecture: arch=compute_90,code=sm_90" "$L/40-configure.txt" \
  || echo "WARNING: configure did not echo the forced architecture" >> "$L/40-configure.txt"

############ stage 5: build. FIRST failure is the result. No retry. Two threads. ############
STAGE=build; deadline_guard build
BCAP=$(budget "$BUILD_CAP_S")
BUILD_T0=$(date +%s)
timeout -s TERM "$BCAP" make -j2 > "$L/50-build.txt" 2>&1; BRC=$?
BUILD_SECS=$(( $(date +%s) - BUILD_T0 ))
echo "MAKE-EXIT=$BRC BUILD_SECONDS=$BUILD_SECS BUILD_CAP_USED=$BCAP" >> "$L/50-build.txt"
grep -m1 -nE "error:|Error [0-9]+" "$L/50-build.txt" > "$L/51-first-error.txt" 2>/dev/null || true
grep -nE "cudaDeviceSynchronize|dynamic parallelism|CDP" "$L/50-build.txt" | head -20 > "$L/52-device-sync-evidence.txt" 2>/dev/null || true
if [ "$BRC" -eq 124 ] || [ "$BRC" -eq 143 ]; then
  { echo "The build hit its ${BCAP}s cap. A TIMEOUT IS NOT A COMPATIBILITY FAILURE."
    echo "If BUILD_CAP_USED is below ${BUILD_CAP_S}s, the cap was shortened by the outer ${HARD_DEADLINE_S}s bound."
  } >> "$L/50-build.txt"
  [ "$BCAP" -lt "$BUILD_CAP_S" ] && fin DEADLINE_EXCEEDED build "$L/50-build.txt"
  fin BUILD_TIMEOUT build "$L/50-build.txt"
fi
if [ "$BRC" -ne 0 ]; then
  { echo "=== FIRST compiler error, preserved verbatim, no retry attempted ==="
    sed -n '1,200p' "$L/51-first-error.txt" 2>/dev/null
    echo "=== device-side synchronisation evidence, if any ==="
    cat "$L/52-device-sync-evidence.txt" 2>/dev/null
  } > "$L/53-failure-summary.txt"
  fin COMPILE_FAIL build "$L/53-failure-summary.txt"
fi

############ stage 6: run the two cases ############
STAGE=run; cd "$SRC/build"
for CASE in actuated passive; do
  STAGE="run-$CASE"; deadline_guard "run-$CASE"
  mkdir -p "$WORK/case-$CASE"
  cp "$HERE/cases/$CASE/base.vxa" "$HERE/cases/$CASE/robot.vxd" "$WORK/case-$CASE/"
  RCAP=$(budget "$RUN_CAP_S"); T0=$(date +%s)
  timeout -s TERM "$RCAP" ./voxcraft-sim -i "$WORK/case-$CASE" -o "$WORK/out/$CASE.xml" -f \
      > "$WORK/out/$CASE.history" 2> "$L/60-run-$CASE.txt"; RRC=$?
  echo "RUN-EXIT=$RRC SECONDS=$(( $(date +%s) - T0 )) CAP_USED=$RCAP HISTORY_BYTES=$(stat -c%s "$WORK/out/$CASE.history" 2>/dev/null || echo 0)" >> "$L/60-run-$CASE.txt"
  if [ "$RRC" -eq 124 ] || [ "$RRC" -eq 143 ]; then
    [ "$RCAP" -lt "$RUN_CAP_S" ] && fin DEADLINE_EXCEEDED "run-$CASE" "$L/60-run-$CASE.txt"
    fin RUN_TIMEOUT "run-$CASE" "$L/60-run-$CASE.txt"
  fi
  [ "$RRC" -ne 0 ] && fin RUNTIME_FAIL "run-$CASE" "$L/60-run-$CASE.txt"
done

############ stage 7: validate ############
STAGE=validate; deadline_guard validate
python3 "$HERE/validate_history.py" --actuated "$WORK/out/actuated.history" \
        --passive "$WORK/out/passive.history" --expect-voxels 32 --min-frames 3 \
        --out "$WORK/out/validation.json" > "$L/70-validate.txt" 2>&1; VRC=$?
cat "$L/70-validate.txt"
case "$VRC" in
  0) : ;;
  2) fin HISTORY_STRUCTURAL_FAIL validate "$L/70-validate.txt" ;;
  3) fin ACTUATION_DISCRIMINATOR_FAIL validate "$L/70-validate.txt" ;;
  *) fin INCONCLUSIVE validate "$L/70-validate.txt" ;;
esac

############ stage 8: fold measurements into the receipt and package ############
python3 - "$R" "$WORK" <<'PY'
import json,sys,os
R,W=sys.argv[1],sys.argv[2]; d=json.load(open(R))
v=os.path.join(W,"out","validation.json")
if os.path.exists(v): d["validation"]=json.load(open(v))
d["history_bytes"]={c:os.path.getsize(os.path.join(W,"out",c+".history"))
                    for c in ("actuated","passive") if os.path.exists(os.path.join(W,"out",c+".history"))}
json.dump(d,open(R,"w"),indent=1)
PY
fin PASS complete
