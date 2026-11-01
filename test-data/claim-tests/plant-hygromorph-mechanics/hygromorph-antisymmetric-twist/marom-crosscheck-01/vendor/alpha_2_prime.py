"""alpha_2_prime -- L_lay -> T_stack, Art analog of alpha_2

Art counterpart of alpha_2, stacks printed layers with their raster orientations.

Inputs : bundle_in, geo_bundle
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

g = parse(geo_bundle)

th1 = sf(g.get("theta_1",  0.0))
th2 = sf(g.get("theta_2", 90.0))
h1  = sf(g.get("h_1",  0.06))
h2  = sf(g.get("h_2", 0.10))

bundle = bundle_in + ";" + ";".join([
    "theta_1={:.4f}".format(th1), "theta_2={:.4f}".format(th2),
    "h_1={:.4f}".format(h1), "h_2={:.4f}".format(h2),
])

report = (
    "alpha_2_prime  aggregate M=2 printed layers\n"
    "  theta=({:+.1f}, {:+.1f})  h=({:.3f}, {:.3f})"
).format(th1, th2, h1, h2)
