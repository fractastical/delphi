"""beta_twist -- T_tis twist reduction (in-plane shear mismatch)

Selects in-plane shear mismatch as the active kinematic driver for twisting.

Inputs : bundle_in
Outputs: bundle, report
"""

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

es1 = sf(b.get("eps_strip_1"));  es2 = sf(b.get("eps_strip_2"))
d12_1 = sf(b.get("delta_12_1")); d12_2 = sf(b.get("delta_12_2"))

d_thk = es1 - es2
d_12  = d12_1 - d12_2

bundle = bundle_in + ";" + ";".join([
    "response=twisting",
    "delta_eps_thk={:.6f}".format(d_thk),
    "delta_eps_12={:.6f}".format(d_12),
    "delta_eps={:.6f}".format(d_12),
])

report = (
    "beta_twist  (twist active)\n"
    "  delta_eps_12  = {:+.6f}  (active)\n"
    "  delta_eps_thk = {:+.6f}  (crosstalk)"
).format(d_12, d_thk)
