"""alpha_1 -- F_fib -> L_lam, N fibers to lamina (identity for N=1)

Averages N aligned fibers into a single lamina state.

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

e1  = sf(b.get("e_1"));  eL1 = sf(b.get("eps_L_1"));  eT1 = sf(b.get("eps_T_1"))
e2  = sf(b.get("e_2"));  eL2 = sf(b.get("eps_L_2"));  eT2 = sf(b.get("eps_T_2"))

# N=1 averaging => identity. Emit lamina-indexed state.
bundle = bundle_in + ";" + ";".join([
    "e_lam_1={:.6f}".format(e1), "eps_L_lam_1={:.6f}".format(eL1), "eps_T_lam_1={:.6f}".format(eT1),
    "e_lam_2={:.6f}".format(e2), "eps_L_lam_2={:.6f}".format(eL2), "eps_T_lam_2={:.6f}".format(eT2),
])

report = (
    "alpha_1  N=1 avg (identity)\n"
    "  L1  e_lam={:+.6f}  eps_L_lam={:+.6f}  eps_T_lam={:+.6f}\n"
    "  L2  e_lam={:+.6f}  eps_L_lam={:+.6f}  eps_T_lam={:+.6f}"
).format(e1, eL1, eT1, e2, eL2, eT2)
