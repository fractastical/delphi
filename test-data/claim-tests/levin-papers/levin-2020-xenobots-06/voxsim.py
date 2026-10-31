"""Simplified voxel soft-body simulator and evolutionary loop shared by the tests of
levin-2020-xenobots-06 and levin-2020-xenobots-10.

This is a pre-registered stand-in for the authors' Voxelyze/VoxCad pipeline
(github.com/skriegman/reconfigurable_organisms), not a port of it: a 3D mass-spring lattice with
nodes at voxel corners and springs on voxel edges, face diagonals and body diagonals. Contractile
voxels scale the rest length of their springs by 1 + A sin(2 pi f t + phi). The ground is a
penalty plane with smoothed Coulomb friction; "water" is reduced gravity plus linear drag on
exposed voxel faces. Units are dimensionless (voxel edge = 1, node mass = number of present
voxels sharing the node, time in seconds).

The time-stepping kernel is voxsim.mjs (Node 20+); this module holds the constants, the
genetics and the evolutionary loop. Needs numpy.
"""
import json
import os
import subprocess

import numpy as np

NX, NY, NZ = 5, 5, 4
NV = NX * NY * NZ

FREQ = 2.0
OMEGA = 2 * np.pi * FREQ
AMP = 1.5 ** (1 / 3) - 1          # 50% volumetric change, as in the authors' TEMP_AMP
DT = 1e-3
SETTLE = 0.5
EVAL = 10.0
G_LAND = 15.0                      # actuation acceleration AMP*OMEGA^2 ~ 23 > g: bounding admissible
G_WATER_FACTOR = 0.1
DRAG_PER_FACE = 1.0
K_TYPE = {"edge": 2000.0, "face": 1000.0, "body": 600.0}
SPRING_DAMP = 0.02                 # spring damping coefficient per unit stiffness
K_GROUND = 3000.0
D_GROUND = 30.0
MU = 1.0
V_EPS = 0.02
CONTACT_TOL = 0.05
RECORD_EVERY = 10
PHASE_LO, PHASE_HI = -np.pi / 2, np.pi / 2

CONST = dict(NX=NX, NY=NY, NZ=NZ, OMEGA=OMEGA, AMP=AMP, DT=DT, SETTLE=SETTLE, EVAL=EVAL,
             K_EDGE=K_TYPE["edge"], K_FACE=K_TYPE["face"], K_BODY=K_TYPE["body"],
             SPRING_DAMP=SPRING_DAMP, K_GROUND=K_GROUND, D_GROUND=D_GROUND, MU=MU, V_EPS=V_EPS,
             CONTACT_TOL=CONTACT_TOL, RECORD_EVERY=RECORD_EVERY)
KERNEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voxsim.mjs")

LAND = {"g": G_LAND, "drag": 0.0}
WATER = {"g": G_LAND * G_WATER_FACTOR, "drag": DRAG_PER_FACE}


def simulate(mat, phase, env, record=False):
    """Simulate bodies (rows of mat: 0 empty / 1 passive / 3 contractile; rows of phase) in the
    Node kernel. Returns arrays disp (net horizontal COM displacement over the evaluation),
    contact (fraction of recorded steps with the lowest node within CONTACT_TOL of the ground),
    path_len (if record) and finite."""
    payload = json.dumps(dict(mats=np.asarray(mat).astype(int).tolist(),
                              phases=np.asarray(phase, dtype=float).tolist(),
                              env=env, record=record, const=CONST))
    res = subprocess.run(["node", KERNEL], input=payload, capture_output=True, text=True, check=True)
    out = json.loads(res.stdout)
    if not record:
        out.pop("path_len")
    return {k: np.array(v, dtype=float) for k, v in out.items()}


def largest_component(cells):
    """Keep the largest face-connected component of a boolean (NX,NY,NZ) array."""
    seen = np.zeros_like(cells)
    best = []
    for start in zip(*np.nonzero(cells)):
        if seen[start]:
            continue
        stack, comp = [start], []
        seen[start] = True
        while stack:
            c = stack.pop()
            comp.append(c)
            for ax in range(3):
                for sgn in (-1, 1):
                    n = list(c)
                    n[ax] += sgn
                    n = tuple(n)
                    if all(0 <= n[d] < cells.shape[d] for d in range(3)) and cells[n] and not seen[n]:
                        seen[n] = True
                        stack.append(n)
        if len(comp) > len(best):
            best = comp
    out = np.zeros_like(cells)
    for c in best:
        out[c] = True
    return out


def random_body(rng, min_frac=0.25):
    while True:
        pres = largest_component(rng.random((NX, NY, NZ)) < 0.5)
        if pres.sum() < min_frac * NV:
            continue
        mat = np.where(pres, np.where(rng.random(pres.shape) < 0.5, 3, 1), 0)
        if (mat == 3).sum() == 0:
            continue
        return mat.ravel()


def random_phase(rng):
    return rng.uniform(PHASE_LO, PHASE_HI, NV)


def mutate(mat, phase, rng, evolve_phase, min_frac=0.25):
    """Per cell with p = 0.04 (at least one cell): switch among empty / passive / contractile.
    If evolve_phase, each cell's phase is perturbed with p = 0.1 by N(0, 0.4 pi), clipped to
    [-pi/2, pi/2]; otherwise the clade's phase field is inherited unchanged."""
    while True:
        m = mat.copy()
        hit = rng.random(NV) < 0.04
        if not hit.any():
            hit[rng.integers(NV)] = True
        for i in np.nonzero(hit)[0]:
            m[i] = rng.choice([s for s in (0, 1, 3) if s != m[i]])
        pres = largest_component((m > 0).reshape(NX, NY, NZ)).ravel()
        m = np.where(pres, m, 0)
        if pres.sum() < min_frac * NV or (m == 3).sum() == 0:
            continue
        p = phase.copy()
        if evolve_phase:
            ph = rng.random(NV) < 0.1
            p[ph] = np.clip(p[ph] + rng.normal(0, 0.4 * np.pi, ph.sum()), PHASE_LO, PHASE_HI)
        return m, p


def evolve(seed, env, evolve_phase, pop_size=32, gens=50, n_parents=16, log=None):
    """Truncation (mu + lambda) selection on net displacement with one random immigrant (new
    clade with a new phase field) per generation. Returns the champion and per-generation best."""
    rng = np.random.default_rng(seed)
    mats = np.array([random_body(rng) for _ in range(pop_size)])
    phases = np.array([random_phase(rng) for _ in range(pop_size)])
    fit = simulate(mats, phases, env)["disp"]
    gen0 = fit.copy()
    best_hist = [float(fit.max())]
    for gnum in range(1, gens + 1):
        order = np.argsort(-fit)[:n_parents]
        pm, pp, pf = mats[order], phases[order], fit[order]
        kids_m, kids_p = [], []
        for _ in range(pop_size - n_parents - 1):
            par = rng.integers(n_parents)
            m, p = mutate(pm[par], pp[par], rng, evolve_phase)
            kids_m.append(m)
            kids_p.append(p)
        kids_m.append(random_body(rng))
        kids_p.append(random_phase(rng))
        kids_m, kids_p = np.array(kids_m), np.array(kids_p)
        kf = simulate(kids_m, kids_p, env)["disp"]
        mats = np.concatenate([pm, kids_m])
        phases = np.concatenate([pp, kids_p])
        fit = np.concatenate([pf, kf])
        best_hist.append(float(fit.max()))
        if log:
            log(f"seed {seed} gen {gnum} best {fit.max():.3f}")
    b = int(np.argmax(fit))
    return dict(seed=seed, mat=mats[b].astype(int).tolist(), phase=phases[b].tolist(),
                fitness=float(fit[b]), gen0_fitness=gen0.tolist(), best_hist=best_hist)
