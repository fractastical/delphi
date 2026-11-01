import json,sys,math
sys.path.insert(0,'.')
import numpy as np
from pathlib import Path
from engineering.launch_glider import print_requirements as pr
panels=json.loads(Path('artifacts/fish3d/fish3d-v3a-fan/panels.json').read_text())
mat=pr.load_material(Path('data/materials/formlabs-studio-2026-10-31.json'))
pf=pr.planform(panels['fins']['pectoral_L'])
ld=pr.loads(0.020)
for t,hs in ((0.5e-3,1.2e-3),(0.4e-3,1.4e-3)):
    for n in (16,64,256,1024):
        r=pr.fin_case(pf,mat,t,1.6e-3,hs,ld['p_worst_Pa'],ld['a_normal_to_fin_m_s2'],1.2e-3,0.012,n_el=n)
        print(f't={t*1e3}mm hs={hs*1e3}mm n_el={n:5d} tip/L={r["tip_over_span"]:.5f} sigma_max={r["sigma_max_Pa"]/1e6:.3f} valid={r["small_deformation"]["valid"]}')
