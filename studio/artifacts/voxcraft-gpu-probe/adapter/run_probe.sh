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
BUILD_TIMEOUT=600     # leaves >=300 s of the 900 s budget for run + validate + package
RUN_TIMEOUT=120
STAGE=start; STATUS=INCOMPLETE; FIRST_FAIL=""
j(){ printf '%s' "$1" | python3 -c 'import sys,json;print(json.dumps(sys.stdin.read()))'; }
fin(){ # fin <status> <stage> [first-fail-file]
  STATUS="$1"; STAGE="$2"
  [ -n "${3:-}" ] && [ -f "$3" ] && FIRST_FAIL="$(head -c 4000 "$3")"
  python3 - "$R" "$STATUS" "$STAGE" <<'PY'
import json,sys,os,subprocess,glob
R,status,stage=sys.argv[1],sys.argv[2],sys.argv[3]
d=json.load(open(R)) if os.path.exists(R) else {}
d["schema"]="frontier.voxcraft-gpu-probe-receipt/1"; d["status"]=status; d["failed_stage"]=stage
d["first_failure_excerpt"]=os.environ.get("FIRST_FAIL","")[:4000]
json.dump(d,open(R,"w"),indent=1)
PY
  export FIRST_FAIL
  echo "PROBE-STATUS=$STATUS  STAGE=$STAGE"
  tar czf "$WORK/out/probe-return.tar.gz" -C "$WORK" logs out --exclude=probe-return.tar.gz 2>/dev/null
  echo "RETURN=$WORK/out/probe-return.tar.gz  bytes=$(stat -c%s "$WORK/out/probe-return.tar.gz" 2>/dev/null || echo 0)"
  exit $([ "$STATUS" = PASS ] && echo 0 || echo 1)
}

############ stage 0: environment / driver / device / image receipt ############
STAGE=preflight
{ echo "== date =="; date -u +%FT%TZ
  echo "== uname =="; uname -a
  echo "== nvidia-smi =="; nvidia-smi 2>&1 || echo "nvidia-smi ABSENT"
  echo "== nvidia-smi query =="; nvidia-smi --query-gpu=name,driver_version,compute_cap,memory.total --format=csv 2>&1 || true
  echo "== nvcc =="; (nvcc --version 2>&1) || echo "nvcc ABSENT"
  echo "== /usr/local/cuda =="; ls -ld /usr/local/cuda* 2>&1 || echo "no /usr/local/cuda*"
  echo "== cmake =="; (cmake --version 2>&1 | head -1) || echo "cmake ABSENT"
  echo "== g++ =="; (g++ --version 2>&1 | head -1) || echo "g++ ABSENT"
  echo "== image hints =="; cat /etc/os-release 2>/dev/null | head -3
  env | grep -iE '^(NVIDIA_|CUDA_|NV_)' | sort || true
  echo "== boost =="; ls /usr/include/boost/version.hpp 2>&1; ls /usr/lib/x86_64-linux-gnu/libboost_filesystem* 2>&1 || echo "no boost libs"
} > "$L/00-preflight.txt" 2>&1
python3 - "$R" "$L/00-preflight.txt" <<'PY'
import json,sys,re
R,pf=sys.argv[1],sys.argv[2]; t=open(pf,errors="replace").read()
def g(p,d=None):
    m=re.search(p,t); return m.group(1).strip() if m else d
json.dump({"schema":"frontier.voxcraft-gpu-probe-receipt/1","status":"RUNNING",
 "expected_image_digest":"nvcr.io/nvidia/pytorch@sha256:11e9976339d08669ede155cdbc601b1df5f57772fcee772b23527efc54e05602",
 "environment":{"gpu_line":g(r"\n([^\n]*,\s*\d+\.\d+[^\n]*,\s*\d+\.\d+[^\n]*)"),
   "nvcc_release":g(r"release ([\d.]+)"),"cuda_build":g(r"Cuda compilation tools[^\n]*"),
   "cmake":g(r"cmake version ([\d.]+)"),"gxx":g(r"g\+\+ \(([^\n]*)"),
   "nvidia_smi_present":"nvidia-smi ABSENT" not in t,
   "nvcc_present":"nvcc ABSENT" not in t,
   "cmake_present":"cmake ABSENT" not in t,
   "boost_present":"no boost libs" not in t},
 "preflight_log":"logs/00-preflight.txt"},open(R,"w"),indent=1)
PY
grep -q "nvidia-smi ABSENT" "$L/00-preflight.txt" && fin NO_GPU preflight "$L/00-preflight.txt"
grep -q "nvcc ABSENT"       "$L/00-preflight.txt" && fin NO_CUDA_TOOLKIT preflight "$L/00-preflight.txt"
grep -q "cmake ABSENT"      "$L/00-preflight.txt" && fin NO_CMAKE preflight "$L/00-preflight.txt"

############ stage 1: fetch immutable public source, verify bytes ############
STAGE=fetch
curl -sL --max-time 300 --max-filesize 4000000 "$TARURL" -o src.tar.gz 2> "$L/10-fetch.txt"
GOTB=$(stat -c%s src.tar.gz 2>/dev/null || echo 0); GOTS=$(sha256sum src.tar.gz 2>/dev/null | cut -d' ' -f1)
{ echo "url=$TARURL"; echo "expected_bytes=$TARBYTES got_bytes=$GOTB";
  echo "expected_sha256=$TARSHA"; echo "got_sha256=$GOTS"; } >> "$L/10-fetch.txt"
if [ "$GOTB" != "$TARBYTES" ] || [ "$GOTS" != "$TARSHA" ]; then
  echo "SOURCE BYTES DO NOT MATCH THE PIN. Stopping. No fallback is attempted here by design:" >> "$L/10-fetch.txt"
  echo "a silent switch to another source would make the compiler result unattributable." >> "$L/10-fetch.txt"
  fin SOURCE_HASH_MISMATCH fetch "$L/10-fetch.txt"
fi
tar xzf src.tar.gz
python3 "$HERE/verify_pin.py" --root "$SRC" --pin "$HERE/source-pin.json" > "$L/11-verify.txt" 2>&1 \
  || fin SOURCE_FILE_HASH_MISMATCH verify "$L/11-verify.txt"

############ stage 2: confirm -DCUDA_ARCH actually bypasses autodetection ############
STAGE=cmake-inspect
{ echo "Checking, in the FETCHED bytes, that defining CUDA_ARCH skips the GPU-probing branch."
  grep -n 'if (NOT DEFINED CUDA_ARCH)' "$SRC/CMakeLists.txt"
  grep -n 'CUDA_SELECT_NVCC_ARCH_FLAGS(RET_ARCH_FLAGS)' "$SRC/CMakeLists.txt"
  grep -n 'Nvidia GPU not found. Abort.' "$SRC/CMakeLists.txt"
  grep -n 'list(APPEND CMAKE_CUDA_FLAGS -gencode=' "$SRC/CMakeLists.txt"
} > "$L/20-cmake-inspect.txt" 2>&1
grep -q 'if (NOT DEFINED CUDA_ARCH)' "$SRC/CMakeLists.txt" \
  || fin CMAKE_GUARD_ABSENT cmake-inspect "$L/20-cmake-inspect.txt"

############ stage 3: dependencies ############
STAGE=deps
if ! ls /usr/lib/x86_64-linux-gnu/libboost_filesystem* >/dev/null 2>&1; then
  if [ "$DEP_INSTALL" = 1 ]; then
    { echo "Boost absent. Installing the four components CMakeLists.txt line 37 requires."
      echo "This is an AUTHORISED, RECORDED install, not a silent repair."
    } > "$L/30-deps.txt"
    ( apt-get update -qq && apt-get install -y -qq --no-install-recommends \
        libboost-filesystem-dev libboost-thread-dev libboost-chrono-dev libboost-program-options-dev \
    ) >> "$L/30-deps.txt" 2>&1 || fin DEP_INSTALL_FAILED deps "$L/30-deps.txt"
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
STAGE=configure
mkdir -p "$SRC/build" && cd "$SRC/build"
cmake .. -DCMAKE_BUILD_TYPE=Release \
         -DCMAKE_CUDA_ARCHITECTURES=90 \
         -DCUDA_ARCH=arch=compute_90,code=sm_90 > "$L/40-configure.txt" 2>&1 \
  || fin CONFIGURE_FAIL configure "$L/40-configure.txt"
grep -q "Using GPU Architecture: arch=compute_90,code=sm_90" "$L/40-configure.txt" \
  || echo "WARNING: configure did not echo the forced architecture" >> "$L/40-configure.txt"

############ stage 5: build. FIRST failure is the result. No retry. ############
STAGE=build
BUILD_T0=$(date +%s)
timeout -s TERM "$BUILD_TIMEOUT" make -j2 > "$L/50-build.txt" 2>&1; BRC=$?
BUILD_SECS=$(( $(date +%s) - BUILD_T0 ))
echo "MAKE-EXIT=$BRC BUILD_SECONDS=$BUILD_SECS" >> "$L/50-build.txt"
grep -m1 -nE "error:|Error [0-9]+" "$L/50-build.txt" > "$L/51-first-error.txt" 2>/dev/null || true
grep -nE "cudaDeviceSynchronize|dynamic parallelism|cudaDeviceSynchronize is not|CDP" "$L/50-build.txt" \
     | head -20 > "$L/52-device-sync-evidence.txt" 2>/dev/null || true
if [ "$BRC" -eq 124 ] || [ "$BRC" -eq 143 ]; then
  echo "The build hit the ${BUILD_TIMEOUT}s cap. A TIMEOUT IS NOT A COMPATIBILITY FAILURE." >> "$L/50-build.txt"
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
STAGE=run
cd "$SRC/build"
for CASE in actuated passive; do
  mkdir -p "$WORK/case-$CASE"
  cp "$HERE/cases/$CASE/base.vxa" "$HERE/cases/$CASE/robot.vxd" "$WORK/case-$CASE/"
  T0=$(date +%s)
  timeout -s TERM "$RUN_TIMEOUT" ./voxcraft-sim -i "$WORK/case-$CASE" -o "$WORK/out/$CASE.xml" -f \
      > "$WORK/out/$CASE.history" 2> "$L/60-run-$CASE.txt"; RRC=$?
  echo "RUN-EXIT=$RRC SECONDS=$(( $(date +%s) - T0 )) HISTORY_BYTES=$(stat -c%s "$WORK/out/$CASE.history" 2>/dev/null || echo 0)" >> "$L/60-run-$CASE.txt"
  if [ "$RRC" -eq 124 ] || [ "$RRC" -eq 143 ]; then fin RUN_TIMEOUT "run-$CASE" "$L/60-run-$CASE.txt"; fi
  [ "$RRC" -ne 0 ] && fin RUNTIME_FAIL "run-$CASE" "$L/60-run-$CASE.txt"
done

############ stage 7: validate the history structure and the actuation contrast ############
STAGE=validate
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
python3 - "$R" "$WORK" "$BUILD_SECS" <<'PY'
import json,sys,os
R,W,bs=sys.argv[1],sys.argv[2],int(sys.argv[3])
d=json.load(open(R)); d["build_seconds"]=bs
v=os.path.join(W,"out","validation.json")
if os.path.exists(v): d["validation"]=json.load(open(v))
d["history_bytes"]={c:os.path.getsize(os.path.join(W,"out",c+".history"))
                    for c in ("actuated","passive") if os.path.exists(os.path.join(W,"out",c+".history"))}
json.dump(d,open(R,"w"),indent=1)
PY
fin PASS complete
