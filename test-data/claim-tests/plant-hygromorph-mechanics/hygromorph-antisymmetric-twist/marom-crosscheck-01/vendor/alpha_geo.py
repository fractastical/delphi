"""alpha_geo -- T_tis -> S_elem, element geometric embedding

Applies element-scale geometric descriptors (thicknesses, strip dimensions) for the Timoshenko embedding.

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

h1 = sf(g.get("h_1",  0.06))
h2 = sf(g.get("h_2", 0.10))
L  = sf(g.get("L", 8.0))
W  = sf(g.get("W", 1.2))
bc = g.get("bc", "free")

bundle = bundle_in + ";" + ";".join([
    "h_1={:.4f}".format(h1), "h_2={:.4f}".format(h2),
    "L={:.4f}".format(L), "W={:.4f}".format(W),
    "bc={}".format(bc),
])

report = (
    "alpha_geom  aggregate element descriptors\n"
    "  h=({:.3f}, {:.3f}) cm  L={:.2f} cm  W={:.2f} cm  bc={}"
).format(h1, h2, L, W, bc)
