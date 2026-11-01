#!/usr/bin/env bash
# Reproduce the whole run from a clean checkout.
#   needs: cc (clang or gcc), python3 with numpy, network (OEIS and Wolfram pages are fetched live).
#   N=70000000 bash run.sh      (about 50 to 90 minutes at N = 7e7 on an Apple M4; cost grows as N^2)
# Outputs: derived/*.json, derived/*.csv, result.json.  The column itself stays in $WORK (not committed).
set -euo pipefail
cd "$(dirname "$0")"
WORK="${WORK:-/tmp/rule30-work}"; export WORK
N="${N:-70000000}"; THREADS="${THREADS:-6}"; R="${R:-1000}"
mkdir -p "$WORK" derived
cc -O3 -mcpu=native -pthread -o "$WORK/rule30" rule30.c 2>/dev/null || cc -O3 -march=native -pthread -o "$WORK/rule30" rule30.c
cc -O3 -mcpu=native -pthread -o "$WORK/stats" stats.c -lm 2>/dev/null || cc -O3 -march=native -pthread -o "$WORK/stats" stats.c -lm
bash verify.sh | tee derived/verify.log
if [ ! -s "$WORK/column.bin" ] || [ -n "${FORCE:-}" ]; then
  /usr/bin/time -p "$WORK/rule30" "$N" -j "$THREADS" -o "$WORK/column.bin" 2> "$WORK/main.log" || true
fi
# L = N+1 bits for a completed run; for a run stopped early write the bit count to $WORK/L_reached
LREAL=$(cat "$WORK/L_reached" 2>/dev/null || echo $((N+1)))
"$WORK/stats" "$WORK/column.bin" "$LREAL" "$R" -j "$THREADS" -bm 1000000 -bmreps 20 > derived/stats_full.json
"$WORK/stats" "$WORK/column.bin" 1000001 "$R" -j "$THREADS" -bm 1000000 -bmreps 20 > derived/stats_1e6.json
python3 analysis.py "$WORK/column.bin" "$LREAL"
