"""S_print -- printed bilayer element, Art analog of S_elem

Art counterpart of S_elem, Timoshenko coupling for a printed bilayer.

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

# per-lamina observables from T_stack
es1 = sf(b.get("eps_strip_1"))
es2 = sf(b.get("eps_strip_2"))
d12_1 = sf(b.get("delta_12_1"))
d12_2 = sf(b.get("delta_12_2"))

# drivers
d_thk = es1 - es2
d_12  = d12_1 - d12_2

# active driver
resp  = b.get("response", "bending")
d_act = d_12 if resp == "twisting" else d_thk

# geometry + moduli
h1 = sf(b.get("h_1"), 0.06)
h2 = sf(b.get("h_2"), 0.10)
e1 = sf(b.get("E1"),  3500.0)
e2 = sf(b.get("E2"),  3500.0)
if e2 <= 0: e2 = e1
if e1 <= 0: e1 = 3500.0

h_tot = h1 + h2
if h_tot > 0 and h1 > 0 and h2 > 0 and e1 > 0 and e2 > 0:
    m = h1 / h2
    n = e1 / e2
    denom  = h_tot * (3.0 * (1.0 + m)**2 + (1.0 + m*n) * (m*m + 1.0/(m*n)))
    C_geom = 6.0 * (1.0 + m)**2 / denom if denom else 0.0
else:
    m = n = 1.0
    C_geom = 0.0

kappa       = C_geom * d_act
kappa_bend  = C_geom * d_thk
kappa_twist = C_geom * d_12

bundle = bundle_in + ";" + ";".join([
    "m_ratio={:.4f}".format(m), "n_ratio={:.4f}".format(n),
    "h_tot={:.4f}".format(h_tot), "C_geom={:.6f}".format(C_geom),
    "delta_eps_thk={:.6f}".format(d_thk),
    "delta_eps_12={:.6f}".format(d_12),
    "delta_eps={:.6f}".format(d_act),
    "kappa={:.6f}".format(kappa),
    "kappa_bend={:.6f}".format(kappa_bend),
    "kappa_twist={:.6f}".format(kappa_twist),
])

report = (
    "S_print  f_print: Timoshenko bilayer\n"
    "  m=h1/h2={:.3f}  n=E1/E2={:.3f}  C_geom={:.4f}\n"
    "  delta_eps_thk = {:+.6f}   delta_eps_12 = {:+.6f}\n"
    "  response={}   kappa = {:+.4f} 1/cm (active)"
).format(m, n, C_geom, d_thk, d_12, resp, kappa)
