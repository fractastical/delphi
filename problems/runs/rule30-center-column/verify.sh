#!/usr/bin/env bash
# Small verification of the fast implementation (run before and independent of the big run).
#  1. fast column == slow big-integer reference (sha256 of packed column) for many N and
#     for several (S, TILE, K, threads) settings;
#  2. the same N=10^6 column from different parameter sets is bit-identical, and the N=10^6
#     prefix of an N=2*10^6 run equals the N=10^6 run (light-cone trimming is prefix-consistent);
#  3. the first 100,001 bits equal the OEIS A051023 b-file (fetched, not recalled).
set -euo pipefail
cd "$(dirname "$0")"
WORK="${WORK:-/tmp/rule30-work}"; mkdir -p "$WORK"
[ -x "$WORK/rule30" ] || cc -O3 -march=native -pthread -o "$WORK/rule30" rule30.c 2>/dev/null \
  || cc -O3 -mcpu=native -pthread -o "$WORK/rule30" rule30.c
R="$WORK/rule30"
fail=0
for n in 1 2 3 5 17 63 64 65 100 127 129 1000 4097 20000 100000; do
  ref=$(python3 ref_slow.py "$n" | cut -d' ' -f1)
  for cfg in "-S 1024 -T 2048 -K 4 -j 3" "-S 64 -T 3 -K 1 -j 2" "-S 100 -T 5 -K 3 -j 4" "-S 192 -T 7 -K 8 -j 1" "-S 37 -T 1 -K 2 -j 10"; do
    $R "$n" $cfg -q -o "$WORK/o.bin" 2>/dev/null
    got=$(shasum -a 256 "$WORK/o.bin" | cut -d' ' -f1)
    if [ "$ref" != "$got" ]; then echo "MISMATCH n=$n cfg=[$cfg]"; fail=1; fi
  done
  echo "n=$n ref=${ref:0:16}... checked against 5 configs"
done
[ $fail = 0 ] || { echo "VERIFICATION FAILED"; exit 1; }
# parameter independence and prefix consistency at 10^6
$R 1000000 -S 1024 -T 2048 -K 4 -j 10 -q -o "$WORK/a.bin" 2>/dev/null
$R 1000000 -S 320 -T 100 -K 5 -j 4 -q -o "$WORK/b.bin" 2>/dev/null
$R 2000000 -S 1024 -T 2048 -K 4 -j 10 -q -o "$WORK/c.bin" 2>/dev/null
shasum -a 256 "$WORK/a.bin" "$WORK/b.bin"
python3 - "$WORK" <<'E'
import sys; w=sys.argv[1]
a=open(w+'/a.bin','rb').read(); b=open(w+'/b.bin','rb').read(); c=open(w+'/c.bin','rb').read()
assert a==b, "parameter dependence"
n=1000000; nb=(n+1)//8
assert a[:nb]==c[:nb] and (a[nb]>>(7-((n+1)%8)+0) if False else True)
# compare bits 0..n exactly
def bits(x,m): return [(x[t>>3]>>(7-(t&7)))&1 for t in range(m+1)]
assert bits(a,n)==bits(c,n), "prefix inconsistency"
print("param independence and prefix consistency OK at N=10^6")
E
python3 check_oeis.py "$WORK/a.bin"
echo "VERIFICATION PASSED"
