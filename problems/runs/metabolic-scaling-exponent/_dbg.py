import sys, numpy as np
sys.path.insert(0, '.')
import pgls
from analysis import *
P = load_pantheria(); t = load_tree_mcc(); C, _, _ = t.vcv(P['tip']); n = P['n']
rng = np.random.default_rng(3)
X = np.column_stack([np.ones(n), rng.normal(size=n)])
V = 0.5 * C; V[np.diag_indices(n)] = np.diag(C)
y = X @ [1, .7] + np.linalg.cholesky(V) @ rng.standard_normal(n) * .5
f = pgls.fit_pgls(y, X, C, lam=0.5)
Vi = np.linalg.inv(V)
b = np.linalg.solve(X.T @ Vi @ X, X.T @ Vi @ y)
print(f['beta'], b, np.linalg.cond(V))
import statsmodels.api as sm
print(sm.GLS(y, X, sigma=V).fit().params)
