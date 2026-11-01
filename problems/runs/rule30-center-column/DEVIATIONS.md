# Deviations from PREREG.md

`PREREG.md` is unchanged: its SHA-256 (`4ec7231b...af93e`) was re-checked against `PREREG.sha256` after the
session was interrupted, and matches (2026-11-01, local 10:41).

## Order of events that PREREG.md does not show

1. **Benchmarking before registration.** Before `PREREG.md` was written I ran timing benchmarks of the
   generator: N = 10^7 with K = 1, 2, 4, 8 and tile settings (one set was killed part-way), N = 10^6 to 3x10^6
   thread-count runs, and a kernel rewrite (unconditional main loop) that cut single-thread time at N = 10^6
   from 4.8 s to 2.0 s. No statistic of any of those outputs was computed or printed. The generator's final
   message had printed a count of ones in its first version; I removed that line from `rule30.c` before the
   first benchmark, and the earlier verification runs sent stderr to /dev/null. So no density, run length or
   other statistic of the column had been seen when I registered. (PREREG.md says the same, in less detail.)
2. **Launch delay and a failed first launch.** The main run was meant to start immediately after registration
   (10:13 local). The first launch was backgrounded inside a shell that exited, which killed it (empty log, no
   output file), and the session was then cut. It was relaunched at 15:42:01Z (10:42 local), 29 minutes after
   registration. No statistic of the column was computed in between; the `stats` and `analysis.py` code was
   written and tested in that window on PRNG and synthetic (periodic, LFSR) inputs only, never on the column.
   The 150-minute stop rule in PREREG.md is therefore counted from the relaunch.
3. **`rule30.c` edited after verification.** The flush interval was changed from 300 s to 120 s (registered as
   "every 2 minutes") before the final verification run; `verify.sh` was re-run after that edit and passed.
   The source's SHA-256 at launch was `60107ecbaaf1b494645f7bffbacae8271153f176a85539144d769d9eefcf3da8`.
4. **Directory moves.** The repo working tree was briefly reorganised under `engine/` and then restored while
   I worked. My files were carried along both times; nothing was lost, and the scripts use paths relative to
   their own directory.

## Changes to the registered test plan

5. **Monte Carlo size for the secondary battery: 300 to 1000.** PREREG.md registers R = 300 for S1 and S2 but
   also flags a statistic at Monte Carlo p <= 0.001, which no p-value from 300 null sequences can reach
   (minimum 1/301). I used R = 1000 for every statistic, which makes the registered flag threshold attainable.
   This was decided before the statistics were run on the column.
6. **Statistics added to the stats program, not changing any registered test:** the argmax p of the
   suffix-agreement statistic, the Kolmogorov-Smirnov and max |z_b| block descriptives (registered as
   reported), and the running-density and block tables. The period statistic T4c is also tested against the
   PRNG null as an upper-tail p and counted among the secondary flags (PREREG.md lists T4c as "compared with
   the PRNG null" but did not say it counts toward the flags; it is one of about 45).
7. **Berlekamp-Massey (S4)** was registered as 20 null sequences for the first 10^6 bits and is descriptive only.

Further deviations found while running, if any, are appended below.

8. **Run stopped early, before the 150-minute cap and before any statistic of the column.** At 11:39 local
   (2026-11-01, about 57 minutes after the 10:42 relaunch) the generator was killed so the working tree could
   be committed. The last log line was `[ 3425.3s] t=55655424 (79.5% rows, 91.6% work)`. The partial column
   is `/tmp/rule30-work/column.bin` (about 6.5 MB) and is not in the repository. The registered tests on
   `L_reached` have not been run. This prefix is not a verdict.

