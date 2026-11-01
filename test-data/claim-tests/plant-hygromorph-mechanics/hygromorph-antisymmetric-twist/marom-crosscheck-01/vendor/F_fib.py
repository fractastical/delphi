"""F_fib -- fiber object (X, E, f_fib)

Applies the finest-scale constitutive law converting stimulus into primary strain.

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

stim_type = b.get("stim_type", "hygro")
u   = sf(b.get("u"))
du  = sf(b.get("du"))

# dispatch on stim_type to pick coefficients
if stim_type == "thermal":
    cL1 = sf(b.get("alpha_L_1"));  cT1 = sf(b.get("alpha_T_1"))
    cL2 = sf(b.get("alpha_L_2"));  cT2 = sf(b.get("alpha_T_2"))
else:   # hygro
    cL1 = sf(b.get("chi_L_1"));    cT1 = sf(b.get("chi_T_1"))
    cL2 = sf(b.get("chi_L_2"));    cT2 = sf(b.get("chi_T_2"))

# apply f_fib at equilibrium
eL1 = cL1 * du
eT1 = cT1 * du
eL2 = cL2 * du
eT2 = cT2 * du

bundle = bundle_in + ";" + ";".join([
    "e_1={:.6f}".format(u), "eps_L_1={:.6f}".format(eL1), "eps_T_1={:.6f}".format(eT1),
    "e_2={:.6f}".format(u), "eps_L_2={:.6f}".format(eL2), "eps_T_2={:.6f}".format(eT2),
])

report = (
    "F_fib  f_fib ({}) at equilibrium\n"
    "  L1  eps=({:+.6f}, {:+.6f})\n"
    "  L2  eps=({:+.6f}, {:+.6f})"
).format(stim_type, eL1, eT1, eL2, eT2)
