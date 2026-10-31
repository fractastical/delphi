#!/usr/bin/env bash
# Self-contained, bounded Morpheus full-horizon packet (3 arms, 1 thread each). No git, no private access.
# Usage: bash run_packet.sh [OUTDIR]   Needs: curl, sha256sum, tar. Optional: GNUPLOT=/path/to/gnuplot for PNG frames.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); OUT=${1:-$HERE/out}; mkdir -p "$OUT"
URL=https://gitlab.com/morpheus.lab/morpheus/-/package_files/178666119/download
BIN_SHA=3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad
BIN=$OUT/morpheus-2.3.9
[ -x "$BIN" ] || { curl -sL -m 300 -o "$BIN" "$URL" && chmod +x "$BIN"; }
[ "$(sha256sum "$BIN" | cut -d' ' -f1)" = "$BIN_SHA" ] || { echo "binary sha256 mismatch; refusing"; exit 3; }
(cd "$HERE" && sha256sum -c SHA256SUMS) || { echo "packet files do not match SHA256SUMS; refusing"; exit 3; }
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
GP=(); if [ -n "${GNUPLOT:-}" ]; then GP=(--gnuplot-path "$GNUPLOT"); else GP=(--no-gnuplot); fi
for a in baseline nofeedback seed2; do
  mkdir -p "$OUT/$a"; cp "$HERE/$a.xml" "$OUT/$a/model.xml"
  ( cd "$OUT/$a" && timeout --kill-after=30 "${ARM_TIMEOUT_S:-3000}" "$BIN" -f model.xml "${GP[@]}" > stdout.log 2>&1; echo "exit=$?" > exit.txt ) &
done
wait
for a in baseline nofeedback seed2; do echo "$a $(cat "$OUT/$a/exit.txt") last_t=$(tail -1 "$OUT/$a/logger.csv" | cut -f1)"; done | tee "$OUT/result.txt"
# output cap: keep logger, xml, logs, exit; PNG frames only if total under 150 MB
SZ=$(du -sm "$OUT" | cut -f1); [ "$SZ" -gt 150 ] && find "$OUT" -name 'plot_*.png' -delete
(cd "$OUT" && tar czf ../morpheus-packet-result.tgz --exclude=morpheus-2.3.9 .)
sha256sum "$OUT/../morpheus-packet-result.tgz"
