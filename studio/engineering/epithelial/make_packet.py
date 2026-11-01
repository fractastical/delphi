"""Build a self-contained, bounded CPU packet for the infra dispatcher.

The packet has no git access, no private paths and no repo dependency. It fetches the
pinned Morpheus binary by URL, refuses on a SHA mismatch, carries the pre-built model XMLs
so the worker never needs the upstream clone, and writes one small CSV per arm.

Scope of the ask: revision 1 and 2 ran locally in seconds, so nothing already done needs
cloud capacity. What does is the one place the rule is thin — the J-scaling was verified at
a single doubling. This packet tests it across two decades of J at two gap sizes with three
seeds, which is 240 embarrassingly parallel single-thread CPU runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

import build_model
from protocol import GAPS, arm

J_VALUES = (35, 70, 140, 280, 560)
LAMBDA_V = (0.1, 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12.8)
GAP_K = (4, 7)
SEEDS = (1, 2, 3)

RUN_SH = r"""#!/usr/bin/env bash
# Self-contained bounded Morpheus sweep. No git, no private access, CPU only, 1 thread per arm.
# Usage: bash run_packet.sh [OUTDIR] [PARALLEL]    Needs: curl, sha256sum, tar.
set -u
HERE=$(cd "$(dirname "$0")" && pwd); OUT=${1:-$HERE/out}; PAR=${2:-4}; mkdir -p "$OUT"
URL=https://gitlab.com/morpheus.lab/morpheus/-/package_files/178666119/download
BIN_SHA=3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad
BIN=$OUT/morpheus-2.3.9
[ -x "$BIN" ] || { curl -sL -m 600 -o "$BIN" "$URL" && chmod +x "$BIN"; }
[ "$(sha256sum "$BIN" | cut -d' ' -f1)" = "$BIN_SHA" ] || { echo "binary sha256 mismatch; refusing"; exit 3; }
(cd "$HERE" && sha256sum -c SHA256SUMS) || { echo "packet files do not match SHA256SUMS; refusing"; exit 3; }
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
run_one() {
  a=$1; mkdir -p "$OUT/$a"; cp "$HERE/models/$a.xml" "$OUT/$a/model.xml"
  ( cd "$OUT/$a" && timeout --kill-after=30 "${ARM_TIMEOUT_S:-600}" "$BIN" -f model.xml --no-gnuplot \
      --num-threads 1 > stdout.log 2>&1; echo "exit=$?" > exit.txt
    # keep only the small logger; drop frames and logs that are not needed for the threshold
    rm -f ./*.tif ./*.tiff model_graph.dot )
}
export -f run_one; export OUT HERE
ls "$HERE/models" | sed 's/\.xml$//' | xargs -P "$PAR" -I{} bash -c 'run_one {}'
for a in $(ls "$HERE/models" | sed 's/\.xml$//'); do
  echo "$a $(cat "$OUT/$a/exit.txt" 2>/dev/null) rows=$(wc -l < "$OUT/$a/logger.csv" 2>/dev/null || echo 0)"
done | tee "$OUT/result.txt"
(cd "$OUT" && tar czf ../epithelial-sweep-result.tgz --exclude=morpheus-2.3.9 .)
sha256sum "$OUT/../epithelial-sweep-result.tgz"
"""

README = """Epithelial gap-closure J-scaling sweep (Morpheus v2.3.9, CPU only)

WHAT IT TESTS
  A rule derived from the CPM energy, not fitted:
      Phi = lambda_V * A_gap^2 / (N_cells * J_cell_medium * P_gap),  P_gap = 2*sqrt(pi*A_gap)
  Phi is linear in lambda_V and inverse in J, so the closure threshold lambda_V* must be
  proportional to J. That has been verified LOCALLY at exactly one doubling: with gap k=4,
  the threshold bracket is (0.3, 1.0) at J=140 and (1, 2) at J=280. This sweep tests the
  same proportionality across two decades of J at two gap sizes with three seeds.

ACCEPTANCE (declared before the run; do not adjust it to fit the outcome)
  For each (k, seed), find the bracket: the largest lambda_V that CLOSED and the smallest
  that ARRESTED, and take lambda* as their geometric mean. The rule PASSES if lambda*/J is
  constant within a factor of 2 across J = 35..560 at each k, and FAILS otherwise.
  An arm where no bracket exists inside the swept lambda_V range is reported as
  NO-BRACKET, never silently dropped and never used to fit.

MEASUREMENT
  gap_nodes(t) = 40000 - sum(cell.volume) over living cells, read from logger.csv.
  CLOSED means gap_nodes reaches 0 before the stop time; otherwise ARRESTED.
  Closure is counted in Monte-Carlo sweeps, not model time: halving MCSDuration halves the
  model time to closure and leaves the sweep count unchanged (measured locally, 240 both ways).

CONTROLS CARRIED IN THE SWEEP
  Every (k, J) column includes lambda_V values on both sides of the predicted threshold, so
  a column that closes everywhere or arrests everywhere is visible rather than inferred.
  Three seeds per cell of the grid. Seeds share one model: their spread is descriptive, not
  an empirical uncertainty.
  Known floor, measured locally and NOT a mechanism: with both drives off the k=4 gap still
  reduces by 22.0 percent, because 61 surviving cells at a 625-node target claim 38125 of
  40000 nodes. Any closed fraction at k=4 must be read against that floor.

COST AND CAPS
  240 arms, single-thread CPU each, no GPU, no network after the binary fetch.
  Locally comparable arms took 6 to 31 s; budget 600 s per arm as a hard timeout.
  Run each arm under a cap: MemoryMax=2G MemorySwapMax=0 TasksMax=256 RuntimeMaxSec=600.
  MemoryMax alone does not bound anything on a host with swap; keep MemorySwapMax=0.
  Peak RSS measured locally: 160 MB per arm.
  Output: one logger.csv per arm, a few hundred KB each; the result tarball is a few MB.
  TIFF frames are deleted by the runner; this sweep needs no movies.

WHAT IS NOT CLAIMED
  Nothing here is calibrated to a cell line, a species or a measured tissue. CPM energies
  are model units from the upstream Act-model example. This is not a reproduction of any
  published model; see docs/epithelial-repair-card.md section 1.

PROVENANCE
  Model XMLs in models/ were built as 12 named, exactly-once edits on the pinned upstream
  Examples/CPM/Protrusion_2D.xml at tag v2.3.9, base sha256
  da2a27c8e552041ee4a51d7ff1e7332466f5180762642c997594731c92737db2.
  Each arm's parameters are in arms.json. Verify models/ against SHA256SUMS before running.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--clone", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    out = Path(a.out)
    stage = out.parent / "_packet"
    models = stage / "models"
    models.mkdir(parents=True, exist_ok=True)
    base = build_model.fetch_base(Path(a.clone))

    arms = []
    for k in GAP_K:
        for j in J_VALUES:
            for lv in LAMBDA_V:
                for s in SEEDS:
                    x = arm(f"S-k{k}-J{j}-lamV{lv}-s{s}", "S", "J-scaling sweep",
                            lambda_v=lv, j_cell_medium=j, wound_r2=GAPS[k], seed=s,
                            stop=1000, frame_step=100000)   # frames suppressed: no movie needed
                    xml, _ = build_model.build(base, x)
                    (models / f"{x['name']}.xml").write_text(xml)
                    arms.append(x)

    (stage / "arms.json").write_text(json.dumps(arms, indent=1))
    (stage / "README.md").write_text(README)
    (stage / "run_packet.sh").write_text(RUN_SH)
    sums = []
    for p in sorted(stage.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(stage)}")
    (stage / "SHA256SUMS").write_text("\n".join(sums) + "\n")

    with tarfile.open(out, "w:gz") as tf:
        for p in sorted(stage.rglob("*")):
            tf.add(p, arcname=str(p.relative_to(stage)))
    subprocess.run(["rm", "-rf", str(stage)], check=True)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"{out}  {out.stat().st_size} bytes  sha256 {digest}  arms {len(arms)}")


if __name__ == "__main__":
    main()
