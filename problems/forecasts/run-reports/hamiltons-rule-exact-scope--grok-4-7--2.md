# Exact paired Moran computation

- Target: `math-bio-claims/hamilton-rule`.
- Pre-registered result before execution at
  `test-data/claim-tests/math-bio-claims/hamilton-rule/overnight-hamiltons-moran/result.json`.
- Ran `analysis.py` with Python 3 and exact `fractions.Fraction` arithmetic.
- Enumerated all 64 labelled configurations of six haploids in three fixed pairs.
- No datasets, Monte Carlo draws, or floating-point approximations were used.
- The stated seven-state count chain is not well-defined for fixed pairs: counts 2, 3, and 4
  each contain configurations with two distinct exact expected frequency changes.
- The stated no-mutation chain is absorbing, so “stationary-conditional” weights on transient
  three-cooperator configurations are also undefined.
- To emit the requested table, the script explicitly used uniform weighting over configurations
  conditional on each cooperator count.
- Against the pre-registered criterion, the result failed: the refit regression disagreed with
  aggregate expected-change signs at counts 2 and 3.
- The frozen predictor did disagree at endpoint count 1, but both required pass conditions did
  not hold.
- Verdict: `inconclusive` (`not-operationalizable`), confidence 0.99.
- Derived files: `derived/state-comparison.csv`, `derived/transition-matrix.csv`,
  and `derived/summary.json`.
- This does not settle the target claim: the failure is caused by collapsing non-lumpable
  configurations, not a counterexample to the within-state regression identity.
- It addresses only the proposed finite witness and does not solve the broader exact-scope
  problem, which also requires separating theorem, identity, and false forms across models.
