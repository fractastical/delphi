# Monte Carlo basin volumes on the disc (Douady–Couder), partial

- Target: `thompson-growth-form/thompson1917-ch14-05` (parastichy numbers vary with structure size;
  in the model, size relative to primordia is the growth parameter G).
- Pre-registered before any code ran, at
  `test-data/claim-tests/thompson-growth-form/thompson1917-ch14-05/overnight-phyllotaxis-atlas/result.json`
  (`status: "preregistered"`, 2026-11-01T05:53Z). Rule fixed there: R0 = 1, r = exp(G·age),
  kernel E(d) = d^-3, placement at the global minimum on r = R0 (720-angle grid, best 3 local
  minima refined by golden section to 1e-10 rad), far primordia with r − 1 > 10 dropped,
  3 random seed primordia, 300 in total, seed 20261101, 200 log-spaced G in [0.02, 1],
  500 seeds, last 50 divergences, tolerance 1e-3 rad, unclassified-measure threshold 0.01,
  1000-resample bootstrap (seed 20261102), plus a scalar pure-Python cross-check implementation.
- The pre-registration states in advance that the strict list test is expected to fail:
  at finite G the Fibonacci-branch divergence is a continuous function of G and equals the
  golden angle only as G → 0. A secondary branch-level list (Fibonacci incl. distichy, Lucas,
  bijugate, by parastichy pair) is pre-registered and does not change the primary outcome.
- `analysis.py` is written (vectorized simulator, reference simulator, classifier, bootstrap,
  basin-volume CSV and summary writer) but has NOT produced results.
- What happened: a timing run at G = 0.02 with 100 seeds did not finish in 5 minutes. Profiling
  showed elementwise numpy operations running roughly 20–50× slower than expected (about 1.6 s
  for 8.6 M multiply-adds), which points to a heavily loaded machine. Then the shell tool became
  unavailable, so no sweep, no reduced grid and no cross-check was run.
- No numbers exist: no basin volumes, no verdict. `result.json` stays `preregistered`, and its
  pre-registered fields are unchanged.
- Next step: on an idle machine, run `python3 analysis.py --time-only 0.02 --seeds 100`. If the
  full grid is too slow, run `python3 analysis.py --n-g <N> --seeds <S>` (the G values are thinned
  evenly; the 0.01 criterion is kept). Then fill `result.json` from `derived/summary.json` with
  `data_kind: "computational"`.
- Scope: even when complete, this atlas can falsify a proposed complete list of attractors.
  It cannot prove that any class has full measure, and it does not solve the problem, which
  needs a theorem.
