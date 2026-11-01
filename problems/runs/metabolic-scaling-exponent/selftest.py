#!/usr/bin/env python3
"""Validate the PGLS implementation on simulated data with known slope and lambda, on the real MCC tree
structure (tips = PanTHERIA BMR species). Also cross-checks GLS against statsmodels if installed."""
import os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pgls
from analysis import load_pantheria, load_tree_mcc

rng = np.random.default_rng(1)
df = load_pantheria()
tree = load_tree_mcc()
tips = [t for t in df["tip"]]
C, base, scale = tree.vcv(tips)
n = len(tips)
assert np.allclose(C, C.T) and C.min() >= -1e-12 and abs(np.diag(C).max() - 1) < 1e-12
print("n", n, "C diag range", np.diag(C).min(), np.diag(C).max())
x = rng.normal(size=n)
X = np.column_stack([np.ones(n), x])
res = []
for true_lam in (0.0, 0.5, 0.9):
    bs, ls = [], []
    for _ in range(40):
        V = true_lam * C
        V[np.diag_indices(n)] = np.diag(C)
        y = X @ [1.0, 0.7] + np.linalg.cholesky(V) @ rng.standard_normal(n) * 0.5
        f = pgls.fit_pgls(y, X, C)
        bs.append(f["beta"][1]); ls.append(f["lam"])
    print(f"true lambda {true_lam}: mean b {np.mean(bs):.3f} (true 0.7), mean lambda_hat {np.mean(ls):.3f}")
    res.append((true_lam, np.mean(bs), np.mean(ls)))
    assert abs(np.mean(bs) - 0.7) < 0.03 and abs(np.mean(ls) - true_lam) < 0.15
# coverage of the analytic 95% CI at lambda=0.5
cov = 0
for _ in range(100):
    V = 0.5 * C; V[np.diag_indices(n)] = np.diag(C)
    y = X @ [1.0, 0.7] + np.linalg.cholesky(V) @ rng.standard_normal(n) * 0.5
    f = pgls.fit_pgls(y, X, C)
    lo, hi = pgls.ci_t(f, 1)
    cov += lo <= 0.7 <= hi
print("CI coverage at lambda 0.5:", cov, "/ 100")
try:
    import statsmodels.api as sm
    V = 0.5 * C; V[np.diag_indices(n)] = np.diag(C)
    f = pgls.fit_pgls(y, X, C, lam=0.5)
    g = sm.GLS(y, X, sigma=V).fit()
    print("statsmodels GLS beta", g.params, "ours", f["beta"])
    assert np.allclose(g.params, f["beta"], atol=1e-8)
except ImportError:
    print("statsmodels not installed; skipped cross-check")
print("SELFTEST OK")
