"""Run the Nakamasu 2009 three-cell Turing model (infinitemorphospace) on a flank grid and export the
melanophore field u(y, x) for embossing the zebrafish stripes onto the print.
Run with the infinitemorphospace venv:  infinitemorphospace/venv/bin/python make_stripes.py
"""
import importlib.util, sys, json
from pathlib import Path
import numpy as np
SRC = Path("/Users/jdietz/Documents/GitHub/infinitemorphospace/models/2009-nakamasu-zebrafish-three-cell-stripes.py")
spec = importlib.util.spec_from_file_location("nakamasu", SRC); m = importlib.util.module_from_spec(spec)
sys.modules["nakamasu"] = m; spec.loader.exec_module(m)
# Adult flank: 5 dark stripes across L_y = 9.2 (model units); long axis x is ~ 3.5x the height
r = m.integrate_nakamasu_pde_2d(ny=96, nx=360, length_y=9.2, steps=420)
u = r["u"]; out = Path(__file__).parent
np.savez(out / "stripes_u.npz", u=u, x=r["x"], y=r["y"])
json.dump({"model": "Nakamasu et al. 2009 PNAS 106:8429, infinitemorphospace/models/2009-nakamasu-zebrafish-three-cell-stripes.py",
           "n_stripes": r["n_stripes"], "horiz_anisotropy": r["horiz_anisotropy"], "r_uv": r["r_uv"],
           "grid": list(u.shape)}, open(out / "stripes_meta.json", "w"), indent=1)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
plt.figure(figsize=(12, 3.5)); plt.imshow(u, cmap="gray_r", aspect="auto"); plt.title(f"Nakamasu 2009 melanophore field u, {r['n_stripes']} stripes")
plt.savefig(out / "stripes_u.png", dpi=110, bbox_inches="tight"); print(r["n_stripes"], r["horiz_anisotropy"], u.shape, float(u.min()), float(u.max()))
