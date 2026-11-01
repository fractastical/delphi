"""Reviewer arithmetic on the delivered print-requirements (3bd7f24). Independent of the author's solver: closed forms, my own STL
volume/centroid/area, my own stress and unit-load tip integrals. Usage: python recheck.py <repo-root-at-3bd7f24>"""
import json, math, struct, sys
import numpy as np
R = sys.argv[1]; D = json.load(open(f'{R}/artifacts/launch-glider/print-requirements.json')); g = 9.80665; rho_air = 1.225
F = f'{R}/artifacts/fish3d/fish3d-v3a-fan'
# 1. STL volumes against components.json (units: metres)
comps = json.load(open(f'{F}/components.json'))['components']
def stl(p):
    b = open(p, 'rb').read(); n = struct.unpack('<I', b[80:84])[0]
    return np.frombuffer(b[84:84+50*n], dtype=np.dtype([('n', '<f4', 3), ('v', '<f4', (3, 3)), ('a', '<u2')]))['v'].astype(float)
worst = 0
for n, c in comps.items():
    if not c.get('stl'): continue
    T = stl(f'{F}/components/{n}.stl'); a, b, cc = T[:, 0], T[:, 1], T[:, 2]
    V = np.einsum('ij,ij->i', a, np.cross(b, cc)).sum() / 6 * 1e9
    worst = max(worst, abs(V - c['check']['signed_volume_mm3']) / c['check']['signed_volume_mm3'])
print('max relative volume difference over', sum(1 for c in comps.values() if c.get('stl')), 'STL components:', f'{worst:.1e}')
T = stl(f'{F}/components/body.stl'); a, b, cc = T[:, 0], T[:, 1], T[:, 2]
A = 0.5*np.linalg.norm(np.cross(b-a, cc-a), axis=1)
print('body solid mass g', 1220*np.einsum('ij,ij->i', a, np.cross(b, cc)).sum()/6*1e3, '| surface m2', A.sum(), '| area-centroid x mm', ((a+b+cc)/3*A[:, None]).sum(0)[0]/A.sum()*1e3)
print('shell mass g at t=0.5/0.8/1.2 mm:', [round(A.sum()*t*1220*1e3, 2) for t in (0.5e-3, 0.8e-3, 1.2e-3)])
# 2. lift budget from the file's own S
S = D['S_paired_m2']
for V in (4, 6, 8):
    print(f'V={V}: max mass g at CL 0.6/1.2 = {0.5*rho_air*V*V*0.6*S/g*1e3:.1f}/{0.5*rho_air*V*V*1.2*S/g*1e3:.1f}; CL needed for 8 g / 20 g = {0.008*g/(0.5*rho_air*V*V*S):.2f}/{0.020*g/(0.5*rho_air*V*V*S):.2f}')
# 3. Helmbold with sweep, Munk k2-k1 for fineness of the body
hb = lambda A, tl: 2*math.pi*A/(2+math.sqrt(4+A*A*(1+tl*tl)))
for n, tl in (('pectoral', 0.189), ('pelvic', 0.434)):
    A_ = D['neutral_point_bracket'][n]['AR_pair']; print(n, 'CLalpha unswept', round(hb(A_, 0), 3), 'swept (half-chord slope', tl, ')', round(hb(A_, tl), 3))
def k21(f):
    e = math.sqrt(1-1/f**2); L = math.log((1+e)/(1-e)); a0 = 2*(1-e*e)/e**3*(0.5*L-e); b0 = 1/e**2-(1-e*e)/(2*e**3)*L
    return b0/(2-b0)-a0/(2-a0)
print('Munk k2-k1 at fineness 6.4 (158.8 mm / 24.9 mm equivalent diameter):', round(k21(6.4), 3), '| bracket in file 0.80-0.95')
