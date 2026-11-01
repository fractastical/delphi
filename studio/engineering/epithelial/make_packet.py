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

README = """Epithelial gap-closure J-scaling sweep (Morpheus v2.3.9, CPU only)

WHAT IT TESTS
  A rule derived from the CPM energy, not fitted:
      Phi = lambda_V * A_gap^2 / (N_cells * J_cell_medium * P_gap),  P_gap = 2*sqrt(pi*A_gap)
  Phi is linear in lambda_V and inverse in J, so the closure threshold lambda_V* must be
  proportional to J. That has been verified LOCALLY at exactly one doubling: with gap k=4,
  the threshold bracket is (0.3, 1.0) at J=140 and (1, 2) at J=280. This sweep tests the
  same proportionality over J = 35 to 560, a FACTOR OF 16 (about 1.2 decades), at two gap
  sizes with three seeds. An earlier draft of this file said "two decades"; that was wrong,
  and the sweep range has not been changed to match the claim.

ACCEPTANCE (declared in analyze_sweep.py, whose own sha256 is written into every report)
  Per (gap, seed, J): the bracket is the largest lambda_V that CLOSED and the smallest that
  ARRESTED; lambda* is their geometric mean; the statistic is lambda*/J.
  PASS        every (gap, seed, J) cell resolved a bracket, AND max/min of lambda*/J within
              each gap size is <= 2.0.
  FAIL        all resolved, and that ratio exceeds 2.0 somewhere.
  UNRESOLVED  any cell failed to bracket inside the swept lambda_V range. UNRESOLVED IS NOT A
              PASS. An unresolved cell is named in the report and is never dropped so that the
              remaining cells can satisfy the rule.
  There is no flag that changes the tolerance. Changing it changes the criterion hash.

HOW SUCCESS IS DECIDED
  run_packet.sh NEVER decides its own success. Its exit status is audit_completeness.py's.
  A run is complete only if all 240 declared arm ids are present, exited 0, and produced a
  logger with every required field, at least two sampled times and finite values throughout.
  Zero successful arms is never complete. Failures are preserved and listed by id.

MEASUREMENT
  gap_nodes(t) = 40000 - sum(cell.volume) over living cells, read from logger.csv.
  CLOSED means gap_nodes reaches 0 before the stop time; otherwise ARRESTED.
  Closure is counted in Monte-Carlo sweeps, not model time: halving MCSDuration halves the
  model time to closure and leaves the sweep count unchanged (measured locally, 240 both ways).

CONTROLS CARRIED IN THE SWEEP
  Every (gap, J) column includes lambda_V values on both sides of the predicted threshold, so
  a column that closes everywhere or arrests everywhere is visible rather than inferred.
  Three seeds per grid cell. Seeds share one model: their spread is descriptive, not an
  empirical uncertainty.
  Known floor, measured locally and NOT a mechanism: with both drives off the k=4 gap still
  reduces by 22.0 percent, because 61 surviving cells at a 625-node target claim 38125 of
  40000 nodes. Any closed fraction at k=4 must be read against that floor.

COST, CAPS AND LAYOUT
  240 arms, single-thread CPU each, no GPU, no network after the binary fetch.
  Locally comparable arms took 6 to 31 s. At 8 workers, 240 arms x 31 s worst case projects
  about 930 s plus setup. Declared bounds, all enforced by run_packet.sh:
      per arm (soft)    ARM_TIMEOUT_S=600, own process group, SIGTERM then SIGKILL after 30 s
      whole job (hard)  JOB_TIMEOUT_S=5400
      workers           argument 2, default 8   (8 workers fit 8 CPU / 8 GiB; ~160 MB RSS per arm)
      output cap        OUTPUT_CAP_MB=512, checked before packaging; over cap exits 4
      download cap      DOWNLOAD_CAP_BYTES=67108864, plus HTTP status and exact hash checks
  The solver and all scratch live in WORKSPACE (mktemp, or PACKET_WORKSPACE), OUTSIDE the
  output tree, so an automatic collector over OUTDIR never picks up the 15 MB executable.
  OUTDIR gets binary-receipt.json instead: url, bytes, sha256 and environment.
  TIFF frames are deleted as each arm finishes; a threshold sweep needs no movies.
  Progress: result.txt and completeness.json; final: the result tarball's sha256 is printed,
  and completeness.json carries a manifest_sha256 over every arm's logger hash.

EXIT STATUS
  run_packet.sh : 0 complete, 1 incomplete (see completeness.json), 3 refused before running,
                  4 output cap exceeded.
  analyze_sweep.py : 0 PASS, 1 FAIL, 2 UNRESOLVED.

WHAT IS NOT CLAIMED
  Nothing here is calibrated to a cell line, a species or a measured tissue. CPM energies
  are model units from the upstream Act-model example. This is not a reproduction of any
  published model; see docs/epithelial-repair-card.md section 1. The rule's gap-size
  dependence is already REFUTED locally and this sweep does not test it: k=1 never arrests
  up to lambda_V 5000, and k=4 and k=7 share a bracket where Phi says they should differ
  2.4x. A PASS here would confirm the J-dependence only.

PROVENANCE
  Model XMLs in models/ were built as 12 named, exactly-once edits on the pinned upstream
  Examples/CPM/Protrusion_2D.xml at tag v2.3.9, base sha256
  da2a27c8e552041ee4a51d7ff1e7332466f5180762642c997594731c92737db2.
  Each arm's parameters are in arms.json. run_packet.sh verifies the packet against
  SHA256SUMS with verify_packet.py before anything runs, rejecting duplicates, symlinks,
  path traversal, unlisted files and hash mismatches.
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
    for f in ("run_packet.sh", "verify_packet.py", "audit_completeness.py", "analyze_sweep.py"):
        (stage / f).write_bytes((Path(__file__).parent / "packet_files" / f).read_bytes())
    sums = []
    for p in sorted(stage.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(stage)}")
    (stage / "SHA256SUMS").write_text("\n".join(sums) + "\n")

    # R2 (infra review of 4f33453): add REGULAR FILES ONLY, each exactly once. The previous
    # version walked every member including directories, and tar.add recurses into a directory
    # by default, so every file was archived twice.
    files = sorted(q for q in stage.rglob("*") if q.is_file() and not q.is_symlink())
    assert len({q.relative_to(stage) for q in files}) == len(files), "duplicate archive member"
    with tarfile.open(out, "w:gz") as tf:
        for q in files:
            ti = tf.gettarinfo(str(q), arcname=str(q.relative_to(stage)))
            assert ti.isfile(), f"refusing non-regular member {ti.name}"
            ti.uid = ti.gid = 0
            ti.uname = ti.gname = ""
            with q.open("rb") as fh:
                tf.addfile(ti, fh)
    subprocess.run(["rm", "-rf", str(stage)], check=True)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"{out}  {out.stat().st_size} bytes  sha256 {digest}  arms {len(arms)}")


if __name__ == "__main__":
    main()
