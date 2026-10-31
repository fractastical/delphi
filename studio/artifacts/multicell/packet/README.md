Morpheus v2.3.9 full-horizon packet (StopTime 2.0). Three arms: baseline (seed 3445, feedback on), nofeedback (seed 3445,
g_l*0 inside CDK1 equation), seed2 (seed 7, feedback on). Source XML = upstream tag v2.3.9 commit
29a26b00838736c4180f22fea075688f1d51e619 `Examples/Multiscale/MultiscaleModel.xml` plus the recorded edits (docs/multicell.md);
the XMLs here are those edited files. Generic, NOT calibrated, NOT fish growth. Expect ~0.07 time units/min under load, so
~30+ min per arm; per-arm timeout default 3000 s (ARM_TIMEOUT_S); a timeout is a PARTIAL result, label it by last_t in result.txt.
Without GNUPLOT only logger.csv is produced (no movie). Output cap: PNG frames deleted if output >150 MB; result tarball is
`morpheus-packet-result.tgz` next to OUTDIR. Not verified: this packet's script was not run locally (no local reruns requested).
