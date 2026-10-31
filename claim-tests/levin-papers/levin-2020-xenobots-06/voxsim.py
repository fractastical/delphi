"""Simplified voxel soft-body simulator and evolutionary loop shared by the tests of
levin-2020-xenobots-06 and levin-2020-xenobots-10.

This is a pre-registered stand-in for the authors' Voxelyze/VoxCad pipeline
(github.com/skriegman/reconfigurable_organisms), not a port of it: a 3D mass-spring lattice with
nodes at voxel corners and springs on voxel edges, face diagonals and body diagonals. Contractile
voxels scale the rest length of their springs by 1 + A sin(2 pi f t + phi). The ground is a
penalty plane with smoothed Coulomb friction; "water" is reduced gravity plus linear drag on
exposed voxel faces. Units are dimensionless (voxel edge = 1, voxel mass = 8, time in seconds).

Needs numpy only.
"""
import numpy as np

NX, NY, NZ = 5, 5, 4
NV = NX * NY * NZ
NNX, NNY, NNZ = NX + 1, NY + 1, NZ + 1
NN = NNX * NNY * NNZ

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
SPRING_DAMP = 0.02                 # damping coefficient per unit stiffness (c = 0.02 k)
K_GROUND = 3000.0
D_GROUND = 30.0
MU = 1.0
V_EPS = 0.02
CONTACT_TOL = 0.05
RECORD_EVERY = 10
PHASE_LO, PHASE_HI = -np.pi / 2, np.pi / 2


def vid(i, j, k):
    return (i * NY + j) * NZ + k


def nid(i, j, k):
    return (i * NNY + j) * NNZ + k


def _build_lattice():
    corners = [(a, b, c) for a in (0, 1) for b in (0, 1) for c in (0, 1)]
    springs = {}
    for i in range(NX):
        for j in range(NY):
            for k in range(NZ):
                v = vid(i, j, k)
                cn = [nid(i + a, j + b, k + c) for a, b, c in corners]
                for p in range(8):
                    for q in range(p + 1, 8):
                        d = sum(x != y for x, y in zip(corners[p], corners[q]))
                        kind = {1: "edge", 2: "face", 3: "body"}[d]
                        key = (min(cn[p], cn[q]), max(cn[p], cn[q]))
                        springs.setdefault(key, [kind, set()])[1].add(v)
    keys = sorted(springs)
    S = len(keys)
    a = np.array([k[0] for k in keys])
    b = np.array([k[1] for k in keys])
    ktype = np.array([K_TYPE[springs[k][0]] for k in keys])
    M = np.zeros((S, NV))
    for s, k in enumerate(keys):
        for v in springs[k][1]:
            M[s, v] = 1.0
    node_pos = np.zeros((NN, 3))
    for i in range(NNX):
        for j in range(NNY):
            for k in range(NNZ):
                node_pos[nid(i, j, k)] = (i, j, k)
    rest0 = np.linalg.norm(node_pos[a] - node_pos[b], axis=1)
    VN = np.zeros((NV, NN))
    for i in range(NX):
        for j in range(NY):
            for k in range(NZ):
                for a_, b_, c_ in corners:
                    VN[vid(i, j, k), nid(i + a_, j + b_, k + c_)] = 1.0
    faces = []
    for i in range(NX):
        for j in range(NY):
            for k in range(NZ):
                for ax in range(3):
                    for sgn in (-1, 1):
                        nb = [i, j, k]
                        nb[ax] += sgn
                        inside = 0 <= nb[0] < NX and 0 <= nb[1] < NY and 0 <= nb[2] < NZ
                        fn = []
                        for a_, b_, c_ in corners:
                            off = [a_, b_, c_]
                            if off[ax] == (1 if sgn == 1 else 0):
                                fn.append(nid(i + a_, j + b_, k + c_))
                        faces.append((vid(i, j, k), vid(*nb) if inside else -1, fn))
    return a, b, ktype, M, node_pos, rest0, VN, faces


SA, SB, KTYPE, MEMB, NODE0, REST0, VN, FACES = _build_lattice()
NS = len(SA)


def largest_component(cells):
    """Keep the largest face-connected component of a boolean (NX,NY,NZ) array."""
    cells = cells.copy()
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


def body_arrays(mat, phase, env):
    """mat: (B, NV) int 0 empty / 1 passive / 3 contractile; phase: (B, NV)."""
    B = mat.shape[0]
    pres = (mat > 0).astype(float)
    act = (mat == 3).astype(float)
    nmem = pres @ MEMB.T                                   # (B,S) present voxels per spring
    sp_on = nmem > 0
    k = KTYPE[None, :] * nmem
    with np.errstate(invalid="ignore", divide="ignore"):
        U = np.where(sp_on, ((pres * act * np.cos(phase)) @ MEMB.T) / nmem, 0.0)
        W = np.where(sp_on, ((pres * act * np.sin(phase)) @ MEMB.T) / nmem, 0.0)
    mass = pres @ VN                                       # (B,NN) incident present voxels
    node_on = mass > 0
    drag = np.zeros((B, NN))
    if env["drag"] > 0:
        for v, nb, fn in FACES:
            exposed = pres[:, v] * (1.0 if nb < 0 else (1.0 - pres[:, nb]))
            for n in fn:
                drag[:, n] += env["drag"] / 4.0 * exposed
    return dict(k=k, c=SPRING_DAMP * k, U=U, W=W, mass=mass, node_on=node_on, drag=drag, sp_on=sp_on)


def simulate(mat, phase, env, record=False):
    """Simulate B bodies in parallel. Returns dict with displacement, contact fraction, path."""
    mat = np.asarray(mat)
    phase = np.asarray(phase, dtype=float)
    B = mat.shape[0]
    ba = body_arrays(mat, phase, env)
    m = np.where(ba["node_on"], ba["mass"], 1.0)
    inv_m = np.where(ba["node_on"], 1.0 / m, 0.0)[..., None]
    x = np.repeat(NODE0[None], B, axis=0).copy()
    v = np.zeros_like(x)
    k, c, U, W = ba["k"], ba["c"], ba["U"], ba["W"]
    drag = ba["drag"][..., None]
    g = env["g"]
    w = ba["mass"] / ba["mass"].sum(1, keepdims=True)
    big = 1e9
    n_steps_settle = int(round(SETTLE / DT))
    n_steps = n_steps_settle + int(round(EVAL / DT))
    contact_hits = np.zeros(B)
    n_rec = 0
    com_path = []
    start_com = None
    flat_a = (np.arange(B)[:, None] * NN + SA[None, :]).ravel()
    flat_b = (np.arange(B)[:, None] * NN + SB[None, :]).ravel()
    for step in range(n_steps):
        t = step * DT
        if step >= n_steps_settle:
            ta = t - SETTLE
            rest = REST0[None, :] * (1.0 + AMP * (U * np.sin(OMEGA * ta) + W * np.cos(OMEGA * ta)))
        else:
            rest = REST0[None, :]
        d = x[:, SB] - x[:, SA]
        L = np.sqrt((d * d).sum(-1)) + 1e-12
        u = d / L[..., None]
        relv = ((v[:, SB] - v[:, SA]) * u).sum(-1)
        f = (k * (L - rest) + c * relv)[..., None] * u    # force on a toward b
        F = np.zeros((B * NN, 3))
        fr = f.reshape(-1, 3)
        for ax in range(3):
            F[:, ax] = np.bincount(flat_a, fr[:, ax], minlength=B * NN) - np.bincount(flat_b, fr[:, ax], minlength=B * NN)
        F = F.reshape(B, NN, 3)
        F[..., 2] -= g * m
        F -= drag * v
        z = x[..., 2]
        pen = z < 0
        N = np.where(pen, np.maximum(K_GROUND * m * (-z) - D_GROUND * m * v[..., 2], 0.0), 0.0)
        F[..., 2] += N
        vt = v[..., :2]
        sp = np.sqrt((vt * vt).sum(-1) + V_EPS ** 2)
        F[..., :2] -= (MU * N / sp)[..., None] * vt
        v += DT * F * inv_m
        x += DT * v
        if step >= n_steps_settle and (step - n_steps_settle) % RECORD_EVERY == 0:
            zmin = np.where(ba["node_on"], x[..., 2], big).min(1)
            contact_hits += zmin <= CONTACT_TOL
            n_rec += 1
            com = (w[..., None] * x).sum(1)
            if start_com is None:
                start_com = com.copy()
            if record:
                com_path.append(com[:, :2].copy())
    end_com = (w[..., None] * x).sum(1)
    disp = np.linalg.norm(end_com[:, :2] - start_com[:, :2], axis=1)
    out = dict(disp=disp, contact=contact_hits / n_rec, finite=np.isfinite(x).all((1, 2)))
    if record:
        P = np.stack(com_path, 1)                          # (B,T,2)
        out["path_len"] = np.linalg.norm(np.diff(P, axis=1), axis=2).sum(1)
    out["disp"] = np.where(out["finite"], out["disp"], 0.0)
    return out


LAND = {"g": G_LAND, "drag": 0.0}
WATER = {"g": G_LAND * G_WATER_FACTOR, "drag": DRAG_PER_FACE}


def random_body(rng, min_frac=0.25):
    while True:
        pres = rng.random((NX, NY, NZ)) < 0.5
        pres = largest_component(pres)
        if pres.sum() < min_frac * NV:
            continue
        mat = np.where(pres, np.where(rng.random(pres.shape) < 0.5, 3, 1), 0)
        if (mat == 3).sum() == 0:
            continue
        return mat.ravel()


def random_phase(rng):
    return rng.uniform(PHASE_LO, PHASE_HI, NV)


def mutate(mat, phase, rng, evolve_phase, min_frac=0.25):
    """Per cell with p = 0.04: switch among empty / passive / contractile. If evolve_phase, each
    cell's phase is perturbed with p = 0.1 by N(0, 0.4 pi), clipped to [-pi/2, pi/2]."""
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
    clade with a new phase field) per generation. Returns champion and per-generation best."""
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
        for c in range(pop_size - n_parents - 1):
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
    return dict(seed=seed, mat=mats[b].tolist(), phase=phases[b].tolist(), fitness=float(fit[b]),
                gen0_fitness=gen0.tolist(), best_hist=best_hist)
