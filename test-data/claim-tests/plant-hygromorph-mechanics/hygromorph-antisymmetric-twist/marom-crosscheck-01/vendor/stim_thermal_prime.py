"""stim_thermal_prime -- Art thermal stimulus

Art counterpart of stim_thermal for engineered thermally-responsive materials.

Inputs : mat1, mat2, T_ref, T_cur
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
t0 = sf(T_ref, 25.0)
tc = sf(T_cur, 80.0)
dT = tc - t0

bundle = ";".join([
    "stim_type=thermal",
    "T_ref={:.2f}".format(t0), "T_cur={:.2f}".format(tc),
    "u_ref={:.4f}".format(t0), "u={:.4f}".format(tc), "du={:.4f}".format(dT),
    "alpha_L_1={:.6f}".format(m1.get("alpha_L", 0.0)),
    "alpha_T_1={:.6f}".format(m1.get("alpha_T", 0.0)),
    "alpha_L_2={:.6f}".format(m2.get("alpha_L", 0.0)),
    "alpha_T_2={:.6f}".format(m2.get("alpha_T", 0.0)),
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
    "stim_thermal_prime  environment + coefficients\n"
    "  T_ref={:.2f}  T_cur={:.2f}  dT={:.4f}\n"
    "  L1  alpha=({:.6f}, {:.6f})\n"
    "  L2  alpha=({:.6f}, {:.6f})"
).format(t0, tc, dT,
         m1.get("alpha_L", 0.0), m1.get("alpha_T", 0.0),
         m2.get("alpha_L", 0.0), m2.get("alpha_T", 0.0))
