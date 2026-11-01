Epithelial gap-closure J-scaling sweep (Morpheus v2.3.9, CPU only)

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
