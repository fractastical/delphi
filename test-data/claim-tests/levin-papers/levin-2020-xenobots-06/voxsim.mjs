// Physics kernel for voxsim.py (the numpy version was too slow for the pre-registered budget).
// Reads {mats, phases, env, record, const} as JSON on stdin, writes {disp, contact, path_len, finite}.
// Mass-spring voxel lattice: nodes at voxel corners, springs on edges, face and body diagonals,
// stiffness scaled by the number of present voxels sharing the spring. Contractile voxels scale
// rest lengths by 1 + A sin(omega t + phi) averaged over the voxels sharing the spring.
import { readFileSync } from "node:fs";

const inp = JSON.parse(readFileSync(0, "utf8"));
const C = inp.const;
const [NX, NY, NZ] = [C.NX, C.NY, C.NZ];
const NV = NX * NY * NZ, NNX = NX + 1, NNY = NY + 1, NNZ = NZ + 1, NN = NNX * NNY * NNZ;
const vid = (i, j, k) => (i * NY + j) * NZ + k;
const nid = (i, j, k) => (i * NNY + j) * NNZ + k;

const corners = [];
for (const a of [0, 1]) for (const b of [0, 1]) for (const c of [0, 1]) corners.push([a, b, c]);
const smap = new Map();
for (let i = 0; i < NX; i++) for (let j = 0; j < NY; j++) for (let k = 0; k < NZ; k++) {
  const v = vid(i, j, k);
  const cn = corners.map(([a, b, c]) => nid(i + a, j + b, k + c));
  for (let p = 0; p < 8; p++) for (let q = p + 1; q < 8; q++) {
    let d = 0;
    for (let ax = 0; ax < 3; ax++) if (corners[p][ax] !== corners[q][ax]) d++;
    const lo = Math.min(cn[p], cn[q]), hi = Math.max(cn[p], cn[q]);
    const key = lo * NN + hi;
    if (!smap.has(key)) smap.set(key, { a: lo, b: hi, kind: d, vox: [] });
    smap.get(key).vox.push(v);
  }
}
const springs = [...smap.keys()].sort((x, y) => x - y).map((k) => smap.get(k));
const NS = springs.length;
const KT = { 1: C.K_EDGE, 2: C.K_FACE, 3: C.K_BODY };
const node0 = new Float64Array(NN * 3);
for (let i = 0; i < NNX; i++) for (let j = 0; j < NNY; j++) for (let k = 0; k < NNZ; k++) {
  const n = nid(i, j, k);
  node0[3 * n] = i; node0[3 * n + 1] = j; node0[3 * n + 2] = k;
}
const rest0 = springs.map((s) => Math.hypot(...[0, 1, 2].map((ax) => node0[3 * s.a + ax] - node0[3 * s.b + ax])));
const voxNodes = [];
for (let i = 0; i < NX; i++) for (let j = 0; j < NY; j++) for (let k = 0; k < NZ; k++)
  voxNodes[vid(i, j, k)] = corners.map(([a, b, c]) => nid(i + a, j + b, k + c));
const faces = [];
for (let i = 0; i < NX; i++) for (let j = 0; j < NY; j++) for (let k = 0; k < NZ; k++)
  for (let ax = 0; ax < 3; ax++) for (const sgn of [-1, 1]) {
    const nb = [i, j, k]; nb[ax] += sgn;
    const inside = nb[0] >= 0 && nb[0] < NX && nb[1] >= 0 && nb[1] < NY && nb[2] >= 0 && nb[2] < NZ;
    const fn = corners.filter((o) => o[ax] === (sgn === 1 ? 1 : 0)).map(([a, b, c]) => nid(i + a, j + b, k + c));
    faces.push({ v: vid(i, j, k), nb: inside ? vid(...nb) : -1, fn });
  }

function simulate(mat, phase, env, record) {
  const pres = mat.map((m) => (m > 0 ? 1 : 0)), act = mat.map((m) => (m === 3 ? 1 : 0));
  const idx = [], k = [], c = [], U = [], W = [], r0 = [], sa = [], sb = [];
  springs.forEach((s, si) => {
    let n = 0, u = 0, w = 0;
    for (const v of s.vox) if (pres[v]) { n++; if (act[v]) { u += Math.cos(phase[v]); w += Math.sin(phase[v]); } }
    if (n === 0) return;
    idx.push(si); sa.push(s.a); sb.push(s.b); r0.push(rest0[si]);
    k.push(KT[s.kind] * n); c.push(C.SPRING_DAMP * KT[s.kind] * n); U.push(u / n); W.push(w / n);
  });
  const S = idx.length;
  const mass = new Float64Array(NN);
  for (let v = 0; v < NV; v++) if (pres[v]) for (const n of voxNodes[v]) mass[n] += 1;
  const on = [];
  for (let n = 0; n < NN; n++) if (mass[n] > 0) on.push(n);
  const drag = new Float64Array(NN);
  if (env.drag > 0) for (const f of faces) {
    const exposed = pres[f.v] * (f.nb < 0 ? 1 : 1 - pres[f.nb]);
    if (exposed) for (const n of f.fn) drag[n] += (env.drag / 4) * exposed;
  }
  const x = Float64Array.from(node0), v = new Float64Array(NN * 3), F = new Float64Array(NN * 3);
  let mtot = 0;
  for (const n of on) mtot += mass[n];
  const com = () => {
    let cx = 0, cy = 0;
    for (const n of on) { cx += mass[n] * x[3 * n]; cy += mass[n] * x[3 * n + 1]; }
    return [cx / mtot, cy / mtot];
  };
  const nSettle = Math.round(C.SETTLE / C.DT), nSteps = nSettle + Math.round(C.EVAL / C.DT);
  let hits = 0, nrec = 0, start = null, pathLen = 0, prev = null, finite = true;
  for (let step = 0; step < nSteps; step++) {
    const live = step >= nSettle;
    const ta = (step - nSettle) * C.DT;
    const sn = live ? Math.sin(C.OMEGA * ta) : 0, cs = live ? Math.cos(C.OMEGA * ta) : 0;
    F.fill(0);
    for (let s = 0; s < S; s++) {
      const a = 3 * sa[s], b = 3 * sb[s];
      const dx = x[b] - x[a], dy = x[b + 1] - x[a + 1], dz = x[b + 2] - x[a + 2];
      const L = Math.sqrt(dx * dx + dy * dy + dz * dz) + 1e-12;
      const ux = dx / L, uy = dy / L, uz = dz / L;
      const rv = (v[b] - v[a]) * ux + (v[b + 1] - v[a + 1]) * uy + (v[b + 2] - v[a + 2]) * uz;
      const rest = live ? r0[s] * (1 + C.AMP * (U[s] * sn + W[s] * cs)) : r0[s];
      const f = k[s] * (L - rest) + c[s] * rv;
      F[a] += f * ux; F[a + 1] += f * uy; F[a + 2] += f * uz;
      F[b] -= f * ux; F[b + 1] -= f * uy; F[b + 2] -= f * uz;
    }
    let zmin = Infinity;
    for (const n of on) {
      const i = 3 * n, m = mass[n];
      F[i + 2] -= env.g * m;
      F[i] -= drag[n] * v[i]; F[i + 1] -= drag[n] * v[i + 1]; F[i + 2] -= drag[n] * v[i + 2];
      const z = x[i + 2];
      if (z < 0) {
        const N = Math.max(C.K_GROUND * m * -z - C.D_GROUND * m * v[i + 2], 0);
        F[i + 2] += N;
        const sp = Math.sqrt(v[i] * v[i] + v[i + 1] * v[i + 1] + C.V_EPS * C.V_EPS);
        F[i] -= (C.MU * N / sp) * v[i]; F[i + 1] -= (C.MU * N / sp) * v[i + 1];
      }
      for (let ax = 0; ax < 3; ax++) { v[i + ax] += (C.DT * F[i + ax]) / m; x[i + ax] += C.DT * v[i + ax]; }
      if (x[i + 2] < zmin) zmin = x[i + 2];
    }
    if (live && (step - nSettle) % C.RECORD_EVERY === 0) {
      if (zmin <= C.CONTACT_TOL) hits++;
      nrec++;
      const p = com();
      if (start === null) start = p;
      if (record && prev) pathLen += Math.hypot(p[0] - prev[0], p[1] - prev[1]);
      prev = p;
    }
  }
  for (let i = 0; i < x.length; i++) if (!Number.isFinite(x[i])) { finite = false; break; }
  const end = com();
  const disp = finite ? Math.hypot(end[0] - start[0], end[1] - start[1]) : 0;
  return { disp, contact: hits / nrec, path_len: record ? pathLen : null, finite };
}

const out = { disp: [], contact: [], path_len: [], finite: [] };
inp.mats.forEach((m, b) => {
  const r = simulate(m, inp.phases[b], inp.env, inp.record);
  for (const key of Object.keys(out)) out[key].push(r[key]);
});
process.stdout.write(JSON.stringify(out));
