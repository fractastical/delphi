#!/usr/bin/env bash
# Build the Voxelyze soft-actuation comparison. Isolated: nothing is installed
# system-wide and no package manager is invoked. Needs only g++ and git.
#
# Upstream engine (NOT vendored here):
#   https://github.com/jonhiller/Voxelyze  @ 4287e365e11416dd108f2f361e9ec4c5a011a16c
#   licence: LGPL-3.0-or-later, declared in every src/*.cpp and include/*.h header.
#            There is NO LICENSE file at that commit, so the GitHub API reports
#            "license: null". The headers are the licence of record.
#
# NOTE: the upstream makefile's default FLAGS contain -DPARDISO_5=1, which leaves
# undefined references to pardisoinit/pardiso in the archive. Linking any program
# against it then fails unless a commercial Pardiso 5 library is present. We build
# with FLAGS overridden to drop that define; doLinearSolve() is unused here.
set -euo pipefail
PIN=4287e365e11416dd108f2f361e9ec4c5a011a16c
ROOT="${1:?usage: build.sh <work-dir>}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$ROOT"; cd "$ROOT"
[ -d Voxelyze ] || git clone -q https://github.com/jonhiller/Voxelyze.git Voxelyze
cd Voxelyze && git checkout -q "$PIN"
test "$(git rev-parse HEAD)" = "$PIN" || { echo "pin mismatch"; exit 1; }
make -j1 clean >/dev/null 2>&1 || true
make -j1 FLAGS="-O3 -std=c++11 -Wall -I./include"
cd "$ROOT"
for p in soft_actuation analytic_controls; do
  g++ -O2 -std=c++11 -I Voxelyze/include "$HERE/$p.cpp" -L Voxelyze/lib -lvoxelyze.0.9 -o "$p"
done
echo "built: $ROOT/soft_actuation $ROOT/analytic_controls (Voxelyze $PIN)"
