"""T_stack -- printed stack object, Art analog of T_tis

Art counterpart of T_tis, same projection for a printed stack.

Inputs : bundle_in
Outputs: bundle, report
"""
import math

def sf(x, d=0.0):
    try:    return float(x)
    except: return d

def parse(s):
    d = {}
    for t in str(s or "").split(";"):
        if "=" in t:
            k, v = t.split("=", 1)
            d[k.strip()] = v.strip()
    return d

b = parse(bundle_in)

eL1 = sf(b.get("eps_L_lam_1"));  eT1 = sf(b.get("eps_T_lam_1"))
eL2 = sf(b.get("eps_L_lam_2"));  eT2 = sf(b.get("eps_T_lam_2"))
r1  = math.radians(sf(b.get("theta_1",  0.0)))
r2  = math.radians(sf(b.get("theta_2", 90.0)))

es1 = eL1 * math.cos(r1)**2 + eT1 * math.sin(r1)**2
es2 = eL2 * math.cos(r2)**2 + eT2 * math.sin(r2)**2

d12_1 = 0.5 * (eL1 - eT1) * math.sin(2.0 * r1)
d12_2 = 0.5 * (eL2 - eT2) * math.sin(2.0 * r2)

bundle = bundle_in + ";" + ";".join([
    "eps_strip_1={:.6f}".format(es1), "eps_strip_2={:.6f}".format(es2),
    "delta_12_1={:.6f}".format(d12_1), "delta_12_2={:.6f}".format(d12_2),
])

report = (
    "T_stack  f_stack: strip-axis + shear projections\n"
    "  eps_strip  L1={:+.6f}  L2={:+.6f}\n"
    "  delta_12   L1={:+.6f}  L2={:+.6f}"
).format(es1, es2, d12_1, d12_2)
