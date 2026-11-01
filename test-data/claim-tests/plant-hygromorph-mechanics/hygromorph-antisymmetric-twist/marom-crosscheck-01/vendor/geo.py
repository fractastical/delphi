"""geo -- geometry bundler

Inputs : theta_1, theta_2 (deg); h_1, h_2, L, W (cm); bc (str)
Outputs: bundle
"""

def sf(x, d=0.0):
    try:    return float(x)
    except: return d

th1 = sf(theta_1,  0.0)
th2 = sf(theta_2, 90.0)
h1  = sf(h_1, 0.06)
h2  = sf(h_2, 0.10)
Lv  = sf(L, 8.0)
Wv  = sf(W, 1.2)
try:    bc_s = str(bc) if bc else "free"
except: bc_s = "free"

bundle = ";".join([
    "theta_1={:.4f}".format(th1),
    "theta_2={:.4f}".format(th2),
    "h_1={:.4f}".format(h1),
    "h_2={:.4f}".format(h2),
    "L={:.4f}".format(Lv),
    "W={:.4f}".format(Wv),
    "bc={}".format(bc_s),
])
