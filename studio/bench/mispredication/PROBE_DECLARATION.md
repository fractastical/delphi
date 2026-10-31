# Declared-prior probe of the mispredication claim (critic, 2026-10-31)

Written and committed BEFORE the committed output of `probe_declared_prior.py` exists. Purpose: test the README claim
"above about 1.5 critical wavelengths the textbook criterion is reliable (under 1%)" on a grid that is not only half-integer
multiples of the critical wavelength, with the sampling distribution stated.

## What was observed before this file was committed (honest disclosure)
A first, uncommitted scratch run of an earlier version of the same calculation (same priors, seed 12345, 20,000 systems per prior,
grid 0.5-5.0 without 4.25) produced, as percent mispredicted:

| prior (Dv/Du log-uniform on) | 1.25 | 1.75 | 2.25 | 2.75 | all half-integers 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0 |
|---|---|---|---|---|---|
| [1, 30] | 6.52 | 3.66 | 2.10 | 1.39 | 0.00 |
| [1, 100] | 4.35 | 2.33 | 1.41 | 1.00 | 0.00 |
| [1, 1000] | 2.83 | 1.55 | 0.98 | 0.57 | 0.00 |

That run is why the priors below were chosen; the committed script re-runs them and adds controls, so the committed output is a replay of a
declared design, not an independent confirmation of a hypothesis stated in advance.

## Declared design
- Systems: Jacobian entries a, b, c, d independent uniform on [-2, 2]; Du = 1; Dv/Du log-uniform on [1, R], R in {30, 100, 1000}.
  Keep a draw only if all four continuum conditions hold: trace < 0, det > 0, Dv a + Du d > 0, (Dv a + Du d)^2 > 4 Du Dv det.
  This is a TOY ensemble. It is not a sample of any biological population and its percentages describe this sampling distribution only.
- n = 20,000 accepted systems per prior, seed 12345 (numpy default_rng).
- Misprediction at length L = x * lambda_c, lambda_c = 2 pi / k_c, k_c^2 = (det / (Du Dv))^(1/2): a system is mispredicted when no integer
  n >= 1 gives q_n = (n pi / L)^2 strictly inside the band where det(J - q D) < 0.
- Grid x: 0.1, 0.5, 1.0, 1.25, 1.5, 1.75, 2.0, 2.25, 2.5, 2.75, 3.0, 4.0, 4.25, 5.0.
## Controls (the run fails loudly if any fails)
1. Positive control: at every half-integer x (0.5, 1.0, 1.5, ...), mode n = 2x lies at k_c, which is inside the band, so misprediction must be exactly 0.
2. Must-fail control: at x = 0.1 the large majority must be mispredicted (> 90%); otherwise the counter cannot report failure.
3. Cross-check of the band criterion against direct eigenvalues: for 500 systems and 6 lengths, mark a system unstable when some mode n in 1..60 gives
   eig(J - q_n diag(Du, Dv)) with a positive real part; this must equal "an integer n in the band" in every case.
## What this can and cannot say
It can show that the claim "<1% beyond 1.5 lambda_c" depends on the grid and the prior (a counterexample at non-half-integer lengths).
It cannot say how often real Turing systems mispredict, nothing about nonlinear/subcritical outcomes, nothing about any organism.

## Amendment 1 (after the run; 2026-10-31 12:06 PDT per `date`)
The committed run exited 1 because declared control 2 (x = 0.1 must be > 90% mispredicted for every prior) failed on ONE prior:
Dv/Du log-uniform [1,1000] gave 89.53%. The 90% line was my guess before seeing any output, not derived from anything; the control's purpose
(the counter can report failure) is met by 89.5-98.5%, but I am not editing the declared threshold or the script to make the run pass. The output
files stay as the run produced them (`probe_declared_prior.out`, `.json`, exit 1). Controls 1 and 3 passed (half-integers exactly 0; band criterion vs direct eigenvalues,
3,000 comparisons, 0 disagreements). The results below are therefore reported with that failed control stated.
Counts differ slightly from the earlier scratch run (e.g. 3.41 vs 3.66 at x = 1.75, R = 30) because the committed script draws all priors from one seeded stream in a different order; neither number is more correct.
