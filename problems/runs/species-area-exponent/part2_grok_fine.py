#!/usr/bin/env python3
"""EXPLORATORY, post hoc (logged in DEVIATIONS.md): fine individuals-per-km2 sweep of the grok-4-7 n=2
logseries null, using the noise-free expected curve alpha*ln(1 + a N/alpha) (the replicate nulls of
part2_analysis.py have 95% intervals of width < 0.02, so the expected-curve exponent is the null median).
Writes derived/part2_grok_fine.csv and prints the density range whose null z contains the empirical z.
Not used in any pre-registered verdict.
"""
import json, os
import numpy as np
import pandas as pd
from scipy import optimize
import part2_analysis as P

HERE = os.path.dirname(os.path.abspath(__file__))
DER = os.path.join(HERE, "derived")
df = pd.read_csv(os.path.join(DER, "gift_richness.csv"))
isl = df[df.role == "island"].reset_index(drop=True)
A, y = isl.area.values.astype(float), isl.native_richness.values.astype(float)
ci = int(np.argmax(A))
Acal, Scal = A[ci], float(y[ci])
Ao, yo = np.delete(A, ci), np.delete(y, ci)
p_emp, _ = P.power_fit_fast(Ao, yo)
z_emp = p_emp[1]
ain = Ao / Acal
rows = []
for lr in np.arange(1.0, 9.01, 0.25):
    rho = 10 ** lr
    N = rho * Acal
    alpha = optimize.brentq(lambda al: al * np.log1p(N / al) - Scal, 1e-6, Scal)
    E = alpha * np.log1p(ain * N / alpha)
    p, _ = P.power_fit_fast(Ao, np.round(E))
    # NB fit on rounded expected richness is the same estimator as in the replicate null
    rows.append(dict(log10_rho=lr, alpha=alpha, z_null=p[1]))
t = pd.DataFrame(rows)
t.to_csv(os.path.join(DER, "part2_grok_fine.csv"), index=False, float_format="%.5g")
cross = np.interp(z_emp, t.z_null.values[::-1], t.log10_rho.values[::-1])
out = dict(z_empirical=float(z_emp), log10_rho_matching_empirical_z=float(cross), rho_matching=float(10 ** cross),
           null_z_at_rho_1e6=float(np.interp(6, t.log10_rho, t.z_null)), null_z_at_rho_1e7=float(np.interp(7, t.log10_rho, t.z_null)),
           null_z_range_over_grid=[float(t.z_null.min()), float(t.z_null.max())])
json.dump(out, open(os.path.join(DER, "part2_grok_fine.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
