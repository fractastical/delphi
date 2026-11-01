"""beta_bend_prime -- T_stack bend reduction, Art analog of beta_bend

Art counterpart of beta_bend, selects the bending driver on the printed stack.

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
    "response=bending",
    "delta_eps_thk={:.6f}".format(d_thk),
    "delta_eps_12={:.6f}".format(d_12),
    "delta_eps={:.6f}".format(d_thk),
])

report = (
    "beta_bend_prime  (bend active)\n"
    "  delta_eps_thk = {:+.6f}  (active)\n"
    "  delta_eps_12  = {:+.6f}  (crosstalk)"
).format(d_thk, d_12)
