"""stim_hygro_prime -- Art hygroscopic stimulus

Art counterpart of stim_hygro for engineered hygroscopic materials.

Inputs : mat1, mat2, RH_ref, RH
Outputs: bundle, report
"""

def sf(x, d=0.0):
    try:    return float(x)
    except: return d

def si(x, d=0):
    try:    return int(float(x))
    except: return d

def parse(s):
    d = {}
    for t in str(s or "").split(";"):
        if "=" in t:
            k, v = t.split("=", 1)
            try:    d[k.strip()] = float(v.strip())
            except: d[k.strip()] = v.strip()
    return d

m1 = parse(mat1)
m2 = parse(mat2)
u0 = sf(RH_ref, 30.0) / 100.0
u  = sf(RH,     80.0) / 100.0
du = u - u0

bundle = ";".join([
    "stim_type=hygro",
    "RH_ref={:.2f}".format(u0 * 100), "RH={:.2f}".format(u * 100),
    "u_ref={:.6f}".format(u0), "u={:.6f}".format(u), "du={:.6f}".format(du),
    "chi_L_1={:.6f}".format(m1.get("chi_L", 0.0)),
    "chi_T_1={:.6f}".format(m1.get("chi_T", 0.0)),
    "chi_L_2={:.6f}".format(m2.get("chi_L", 0.0)),
    "chi_T_2={:.6f}".format(m2.get("chi_T", 0.0)),
    "E1={}".format(m1.get("E", 0)), "E2={}".format(m2.get("E", 0)),
    "mat1={}".format(m1.get("name", "mat1")), "mat2={}".format(m2.get("name", "mat2")),
    "v_min_1={}".format(si(m1.get("v_min", 0))), "v_max_1={}".format(si(m1.get("v_max", 0))),
    "T_min_1={}".format(si(m1.get("T_min", 0))), "T_max_1={}".format(si(m1.get("T_max", 0))),
    "T_bed_1={}".format(si(m1.get("T_bed", 0))),
    "v_min_2={}".format(si(m2.get("v_min", 0))), "v_max_2={}".format(si(m2.get("v_max", 0))),
    "T_min_2={}".format(si(m2.get("T_min", 0))), "T_max_2={}".format(si(m2.get("T_max", 0))),
    "T_bed_2={}".format(si(m2.get("T_bed", 0))),
])

report = (
    "stim_hygro_prime  environment + coefficients\n"
    "  u_ref={:.2f}  u={:.2f}  du={:.4f}\n"
    "  L1  chi=({:.5f}, {:.5f})\n"
    "  L2  chi=({:.5f}, {:.5f})"
).format(u0, u, du,
         m1.get("chi_L", 0.0), m1.get("chi_T", 0.0),
         m2.get("chi_L", 0.0), m2.get("chi_T", 0.0))
