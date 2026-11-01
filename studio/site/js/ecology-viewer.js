// Viewer for saved-state ecology trajectories (schema frontier.ecology.trajectory/1, SI units).
//
//   import { mountEcologyViewer } from "./ecology-viewer.js";
//   const v = mountEcologyViewer(el, {
//     cases: [{ id: "glide-passive", label: "Passive glide", url: "artifacts/ecology/run-v2/glide-passive/trajectory.json",
//               receipts: [{ label: "run summary", url: "artifacts/ecology/run-v2/summary.json", select: "glide-passive" }] }, ...],
//     meshUrl: "artifacts/fish3d/fish3d-v3a-fan/fish.glb", panelsUrl: "artifacts/fish3d/fish3d-v3a-fan/panels.json" });
//   await v.ready;
//
// Contract: messages/ecology-viewer-contract.md (native's; this viewer follows it, not the other way round).
//  * SAVED STATES are played; interpolation between them is an explicit, labelled toggle and never changes the numbers.
//  * Mesh: the v3a GLB is in METRES (glTF axes) -> fish axes (gx,-gz,gy) -> body_m = Rz(pi)*(mesh_m - [cg,0,0]).  Nothing is
//    multiplied by 0.001 (native's unit correction).  Each of the four fin nodes rotates about body +Y at its transformed
//    panels.json fin_plane.origin_m by fin_angle_rad[<component id>]; L/R labels are the file's, not guessed.
//  * force_model_valid:false states carry null forces; they are shown as an out-of-domain/numerical-failure state, never as zeros
//    or as validated physics.  Receipts (controls, dt-halving) are shown verbatim and every false flag is surfaced.
//  * The viewer holds no data: a missing or invalid file shows "Trajectory not available" and why, never a placeholder.
// The decorative scales mesh is omitted by default (opts.omitComponents): eight fish at ~460k triangles are too heavy to orbit.
// three.js 0.170.0 is vendored (site/vendor/three/VENDOR.json).  All file text is inserted with textContent.

const THREE_URL = new URL("../vendor/three/lib/three.module.js", import.meta.url).href;
const GLTF_URL = new URL("../vendor/three/examples/jsm/loaders/GLTFLoader.js", import.meta.url).href;
const ORBIT_URL = new URL("../vendor/three/examples/jsm/controls/OrbitControls.js", import.meta.url).href;

export const SCHEMA = "frontier.ecology.trajectory/1";
const FISH_COLOR = [0x4f7fb0, 0x6a9a4a, 0xc08a3a, 0x8a6ab0, 0x3aa0a0, 0xb05a6a, 0x7a7a7a, 0x4a4ab0];
const LOOK = { eye: 0x1c2630, fin: 0xdbe4ea };
const DISCLOSURE = "Quasi-steady per-fin forces from the v3a VLM polar plus an assumed drag closure, integrated by MuJoCo; not CFD, not a validated flying fish. " +
  "Assumed mass, centre of gravity, inertia, drag and control. A saved state with force_model_valid false is a domain exit or numerical failure, not physics. " +
  "Drawing: the decorative scales mesh is omitted for speed, and fins are rigid meshes rotated about their hinges (no fin bending, no rays moving).";
const FORCE_KEYS = ["fluid_force_world_N", "force_world_N", "torque_world_Nm"];
// fields shown first, in this order; anything else the file carries is listed after them, verbatim
const FIELD_ORDER = ["position_m", "orientation_wxyz", "linear_velocity_m_s", "angular_velocity_body_rad_s", "fin_angle_rad", "fin_command_rad",
  "fin_actuator_torque_Nm", "fin_effective_alpha_rad", "force_model_valid", ...FORCE_KEYS, "actuator_positive_power_W", "positive_actuator_work_J",
  "signed_actuator_work_J", "mechanical_energy_J", "escape_triggered", "escape_scheduled_time_s", "active", "termination_reason"];

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};
const finite = (x) => typeof x === "number" && Number.isFinite(x);
const vec = (v, n) => Array.isArray(v) && v.length === n && v.every(finite);
const fmt = (x, d = 4) => (finite(x) ? (Math.abs(x) >= 1000 || (Math.abs(x) < 1e-3 && x !== 0) ? x.toExponential(3) : x.toFixed(d)) : String(x));
const fmtV = (v) => "[" + v.map((x) => fmt(x)).join(", ") + "]";
const safeHref = (u) => { try { const x = new URL(u); return /^https?:$/.test(x.protocol) ? x.href : null; } catch { return null; } };
const hex6 = (c) => "#" + c.toString(16).padStart(6, "0");
const caseId = (j) => (j && j.case && typeof j.case === "object" ? j.case.id : j && j.case);

/** Validate a parsed trajectory against the contract. Returns {problems, notes}; problems refuse the file, notes are shown. */
export function validateTrajectory(j) {
  const bad = [], notes = [];
  if (!j || typeof j !== "object") return { problems: ["not a JSON object"], notes };
  if (j.schema !== SCHEMA) bad.push(`schema is ${JSON.stringify(j.schema)}, expected ${SCHEMA}`);
  if (j.units !== undefined && j.units !== "SI") bad.push(`units is ${JSON.stringify(j.units)}, expected "SI"`);
  const g = j.geometry;
  if (!g || !finite(g.cg_from_nose_m) || g.cg_from_nose_m <= 0) bad.push("geometry.cg_from_nose_m missing or not a positive number");
  if (g && /0\.001|mm/.test(String(g.mesh_mm_to_body_m || ""))) notes.push("the file's geometry carries the superseded millimetre transform text (mesh_mm*0.001); the viewer uses the corrected metre transform");
  if (!Array.isArray(j.frames) || !j.frames.length) { bad.push("frames missing or empty"); return { problems: bad, notes }; }
  const f0 = j.frames[0].fish;
  const ids = Array.isArray(f0) && f0.map((f) => f && f.id);
  if (!ids || !ids.length || ids.some((s) => typeof s !== "string")) { bad.push("frame 0 has no fish with string ids"); return { problems: bad, notes }; }
  const finKeys = f0[0].fin_angle_rad && typeof f0[0].fin_angle_rad === "object" && !Array.isArray(f0[0].fin_angle_rad) ? Object.keys(f0[0].fin_angle_rad) : [];
  if (!finKeys.length) bad.push("fin_angle_rad must be an object keyed by component id");
  let prev = -Infinity;
  for (let i = 0; i < j.frames.length && bad.length < 8; i++) {
    const fr = j.frames[i];
    if (!finite(fr.time_s)) { bad.push(`frame ${i}: time_s not finite`); continue; }
    if (fr.time_s <= prev) bad.push(`frame ${i}: time_s ${fr.time_s} is not after ${prev}`);
    prev = fr.time_s;
    if (!Array.isArray(fr.fish) || fr.fish.length !== ids.length || fr.fish.some((f, k) => !f || f.id !== ids[k])) { bad.push(`frame ${i}: fish ids differ from frame 0`); continue; }
    fr.fish.forEach((f) => {
      const w = `frame ${i} fish ${f.id}`;
      if (!vec(f.position_m, 3)) bad.push(`${w}: position_m`);
      if (!vec(f.orientation_wxyz, 4) || Math.abs(Math.hypot(...f.orientation_wxyz) - 1) > 1e-6) bad.push(`${w}: orientation_wxyz not a unit quaternion`);
      ["linear_velocity_m_s", "angular_velocity_body_rad_s"].forEach((k) => { if (!vec(f[k], 3)) bad.push(`${w}: ${k}`); });
      const fa = f.fin_angle_rad;
      if (!fa || typeof fa !== "object" || Array.isArray(fa) || finKeys.some((k) => !finite(fa[k])) || Object.keys(fa).length !== finKeys.length) bad.push(`${w}: fin_angle_rad keys/values differ from frame 0`);
      if (typeof f.force_model_valid !== "boolean") bad.push(`${w}: force_model_valid missing`);
      FORCE_KEYS.forEach((k) => {
        if (!(k in f)) return;
        if (f[k] === null) { if (f.force_model_valid !== false) bad.push(`${w}: ${k} is null but force_model_valid is not false`); }
        else if (!vec(f[k], 3)) bad.push(`${w}: ${k}`);
      });
      if (typeof f.active !== "boolean") bad.push(`${w}: active not boolean`);
      if (!(f.termination_reason === null || typeof f.termination_reason === "string")) bad.push(`${w}: termination_reason`);
      if (f.active === false && !f.termination_reason) bad.push(`${w}: inactive without a termination_reason`);
    });
  }
  return { problems: bad, notes };
}

// quaternion wxyz helpers on plain arrays
const qrot = (q, v) => { const [w, x, y, z] = q, t = [2 * (y * v[2] - z * v[1]), 2 * (z * v[0] - x * v[2]), 2 * (x * v[1] - y * v[0])];
  return [v[0] + w * t[0] + (y * t[2] - z * t[1]), v[1] + w * t[1] + (z * t[0] - x * t[2]), v[2] + w * t[2] + (x * t[1] - y * t[0])]; };
const slerp = (a, b, t) => { let d = a[0] * b[0] + a[1] * b[1] + a[2] * b[2] + a[3] * b[3], s = 1;
  if (d < 0) { d = -d; s = -1; }
  let ka, kb;
  if (d > 0.9995) { ka = 1 - t; kb = t * s; } else { const th = Math.acos(d), sn = Math.sin(th); ka = Math.sin((1 - t) * th) / sn; kb = (Math.sin(t * th) / sn) * s; }
  const q = a.map((x, i) => ka * x + kb * b[i]), n = Math.hypot(...q); return q.map((x) => x / n); };
const lerp3 = (a, b, t) => a.map((x, i) => x + (b[i] - x) * t);

export function mountEcologyViewer(host, opts = {}) {
  const cases = opts.cases || [];
  const meshUrl = new URL(opts.meshUrl || "artifacts/fish3d/fish3d-v3a-fan/fish.glb", document.baseURI).href;
  const panelsUrl = new URL(opts.panelsUrl || "artifacts/fish3d/fish3d-v3a-fan/panels.json", document.baseURI).href;
  const omit = new Set(opts.omitComponents || ["scales"]);
  const lazy = opts.lazy !== false;
  const S = { mode: "pending", reason: null, caseId: null, traj: null, problems: [], notes: [], t: 0, playing: false, speed: 1, interp: false,
              selected: null, view: "follow", frame: 0, perf: {}, receiptFalse: 0, meshUnits: "m" };
  let T, scene, camera, renderer, controls, io, ro, raf = 0, dirty = true, disposed = false, last = 0;
  let dyn = [], fishObjs = [], trails = [], markers = null, ground = null, threatMesh = null, ring = null, protoSrc = null, baked = null, bakedCg = null, panels = null, libs = null;
  let hinge = {};      // component id -> hinge point in BODY metres: Rz(pi) * (origin_m - [cg,0,0])

  host.textContent = "";
  host.classList.add("ev");
  const head = el("ul", "ev-badges");
  [["ACTUAL SAVED STATES from the run file", "actual"], ["quasi-steady VLM forces + assumed drag, not CFD", "warn"],
   ["engineering candidate, not a validated flying fish", "warn"]].forEach(([t, c]) => head.append(el("li", "ev-badge " + c, t)));
  const caseBar = el("div", "ev-bar ev-cases"); caseBar.setAttribute("role", "group"); caseBar.setAttribute("aria-label", "Scenario");
  const status = el("div", "ev-status"); status.setAttribute("role", "status"); status.hidden = true;
  const grid = el("div", "ev-grid");
  const stage = el("div", "ev-stage");
  const note = el("div", "ev-note", "Trajectory loads when scrolled into view.");
  stage.append(note);
  const side = el("div", "ev-side");
  const ctl = el("div", "ev-bar");
  const btnPlay = el("button", null, "Play"); btnPlay.type = "button"; btnPlay.disabled = true; btnPlay.setAttribute("aria-pressed", "false");
  const btnView = el("button", null, "View: follow school"); btnView.type = "button"; btnView.disabled = true;
  const speed = el("select"); speed.setAttribute("aria-label", "Playback speed"); speed.disabled = true;
  [0.1, 0.25, 0.5, 1].forEach((s) => { const o = el("option", null, s + "×"); o.value = s; if (s === 1) o.selected = true; speed.append(o); });
  const interpLab = el("label", "ev-chk"), interpCb = el("input"); interpCb.type = "checkbox"; interpCb.disabled = true;
  interpLab.append(interpCb, el("span", null, "render interpolation"));
  ctl.append(btnPlay, speed, interpLab, btnView);
  const scrub = el("input"); scrub.type = "range"; scrub.min = 0; scrub.max = 0; scrub.step = 1; scrub.value = 0; scrub.disabled = true;
  scrub.setAttribute("aria-label", "Saved state index");
  const clock = el("p", "ev-clock", "");
  const modeLabel = el("p", "ev-mode", "");
  const fishList = el("ul", "ev-fish"); fishList.setAttribute("aria-label", "Fish");
  const readout = el("div", "ev-readout"); readout.setAttribute("aria-live", "polite");
  const chartBar = el("div", "ev-bar");
  const metric = el("select"); metric.setAttribute("aria-label", "Chart quantity");
  chartBar.append(metric);
  const chart = el("canvas", "ev-chart"); chart.width = 560; chart.height = 150; chart.setAttribute("role", "img");
  const receipt = el("div", "ev-receipt");
  const links = el("ul", "ev-links"); links.setAttribute("aria-label", "Sources and equations");
  const disclosure = el("p", "ev-disclosure", DISCLOSURE);
  side.append(ctl, scrub, clock, modeLabel, fishList, readout, chartBar, chart, receipt, links, disclosure);
  grid.append(stage, side);
  host.append(head, caseBar, status, grid);
  const emit = (n, d) => host.dispatchEvent(new CustomEvent("ev:" + n, { detail: d, bubbles: true }));
  const draw = () => { dirty = true; };

  // ---- data access
  const frames = () => (S.traj ? S.traj.frames : []);
  const fishIds = () => (S.traj ? frames()[0].fish.map((x) => x.id) : []);
  const finIds = () => (S.traj ? Object.keys(frames()[0].fish[0].fin_angle_rad) : []);
  function indexAt(t) {
    const f = frames();
    let lo = 0, hi = f.length - 1;
    if (t <= f[0].time_s) return 0;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (f[m].time_s <= t) lo = m; else hi = m - 1; }
    return lo;
  }
  // pose of one fish at time t: saved state, or (interp on, both neighbours active) a render interpolation of it
  function stateOf(k, t, interp) {
    const f = frames(), i = indexAt(t), a = f[i].fish[k];
    const same = { position: a.position_m, quat: a.orientation_wxyz, fins: a.fin_angle_rad, saved: a, i, alpha: 0 };
    if (!interp || i >= f.length - 1 || !a.active) return same;
    const b = f[i + 1].fish[k];
    if (!b.active) return same;                                                       // never tween toward a terminal state
    const al = (t - f[i].time_s) / (f[i + 1].time_s - f[i].time_s);
    const fins = {}; Object.keys(a.fin_angle_rad).forEach((c) => { fins[c] = a.fin_angle_rad[c] + (b.fin_angle_rad[c] - a.fin_angle_rad[c]) * al; });
    return { position: lerp3(a.position_m, b.position_m, al), quat: slerp(a.orientation_wxyz, b.orientation_wxyz, al), fins, saved: a, i, alpha: al };
  }
  // sim-frame world position of a REST-POSE mesh point (metres, x snout->tail): p + R(q) * Rz(pi) * (m - [cg,0,0])
  function worldOf(k, meshPointM, t = S.t, interp = S.interp) {
    const st = stateOf(k, t, interp), cg = S.traj.geometry.cg_from_nose_m;
    const b = [meshPointM[0] - cg, meshPointM[1], meshPointM[2]], rz = [-b[0], -b[1], b[2]], r = qrot(st.quat, rz);
    return [st.position[0] + r[0], st.position[1] + r[1], st.position[2] + r[2]];
  }

  // ---- scene
  const simToThree = (p) => [p[0], p[2], -p[1]];                        // x, y left, z up  ->  x, y up, z = -left
  // the GLB (metres, glTF axes) in BODY metres: Rz(pi) * T(-cg) * (gx, -gz, gy); baked once per cg and shared by every fish and case
  function bake(cg) {
    if (bakedCg === cg && baked) return;
    if (baked) baked.forEach((b) => b.geometry.dispose());
    const toFish = new T.Matrix4().set(1, 0, 0, 0, 0, 0, -1, 0, 0, 1, 0, 0, 0, 0, 0, 1);              // glTF (x,y,z) -> fish (x, -z, y)
    const m = new T.Matrix4().makeRotationZ(Math.PI).multiply(new T.Matrix4().makeTranslation(-cg, 0, 0)).multiply(toFish);
    baked = protoSrc.map(({ name, src }) => { const g = src.clone(); g.applyMatrix4(m); g.computeVertexNormals(); g.userData.shared = true; return { name, geometry: g }; });
    bakedCg = cg;
  }
  function applyFish(k, st) {
    const o = fishObjs[k], q = st.quat;
    const R = new T.Matrix4().makeRotationFromQuaternion(new T.Quaternion(q[1], q[2], q[3], q[0])), Tp = new T.Matrix4().makeTranslation(...st.position);
    const Sm = new T.Matrix4().set(1, 0, 0, 0, 0, 0, 1, 0, 0, -1, 0, 0, 0, 0, 0, 1);
    o.group.matrix.multiplyMatrices(Sm, new T.Matrix4().multiplyMatrices(Tp, R)); o.group.matrixWorldNeedsUpdate = true;
    // each fin: rotate about body +Y through its hinge point (geometry is already in body metres)
    Object.entries(o.fins).forEach(([cid, g]) => {
      const h = hinge[cid], a = st.fins[cid] ?? 0;
      g.matrix.multiplyMatrices(new T.Matrix4().makeTranslation(h[0], h[1], h[2]),
        new T.Matrix4().multiplyMatrices(new T.Matrix4().makeRotationY(a), new T.Matrix4().makeTranslation(-h[0], -h[1], -h[2]))); g.matrixWorldNeedsUpdate = true;
    });
  }
  function pose() {
    if (!S.traj) return;
    const f = frames(), i = indexAt(S.t); S.frame = i;
    const pts = [];
    f[0].fish.forEach((_, k) => {
      const st = stateOf(k, S.t, S.interp); applyFish(k, st);
      const a = f[i].fish[k], o = fishObjs[k];
      o.mats.forEach((m) => { m.opacity = a.active ? 1 : 0.35; m.transparent = !a.active; });
      pts.push(...simToThree(st.position));
      trails[k].geometry.setDrawRange(0, i + 1);
    });
    markers.geometry.attributes.position.array.set(pts); markers.geometry.attributes.position.needsUpdate = true;
    if (S.view === "follow") {
      const c = new T.Vector3(); for (let k = 0; k < pts.length; k += 3) c.add(new T.Vector3(pts[k], pts[k + 1], pts[k + 2]));
      c.multiplyScalar(3 / pts.length);
      const d = c.clone().sub(controls.target); controls.target.copy(c); camera.position.add(d);
    }
    if (threatMesh) { const w = S.traj.threat.window_s; threatMesh.material.opacity = w && S.t >= w[0] && S.t <= w[1] ? 0.45 : 0.12; }
    if (ring) { const st = stateOf(Math.max(0, fishIds().indexOf(S.selected)), S.t, S.interp), p = simToThree(st.position); ring.position.set(p[0], p[1], p[2]); ring.visible = !!S.selected; }
    clock.textContent = `t = ${fmt(f[i].time_s, 3)} s (saved state ${i + 1} of ${f.length}; median spacing ${fmt(S.period, 4)} s, derived from the file)` + (S.interp && f[i].time_s !== S.t ? `, playhead ${fmt(S.t, 3)} s` : "");
    modeLabel.textContent = S.interp ? "Interpolated render between saved states, not a saved state. Numbers below are the nearest saved state." : "Showing saved states only.";
    modeLabel.dataset.mode = S.interp ? "interp" : "saved";
    scrub.value = i;
    updateStatus(); updateReadout(); drawChart(); draw();
  }

  const add = (o) => { dyn.push(o); scene.add(o); return o; };       // everything buildScene creates, so a case switch removes exactly it
  function disposeScene() {
    cancelAnimationFrame(raf);
    dyn.forEach((root) => { scene.remove(root); root.traverse((o) => {
      if (o.geometry && !o.geometry.userData.shared) o.geometry.dispose();       // the baked mesh is shared by every fish and case
      [].concat(o.material || []).forEach((m) => m && m.dispose && m.dispose()); }); });
    dyn = []; fishObjs = []; trails = []; markers = ground = threatMesh = ring = null;
  }

  function buildScene() {
    const tr = S.traj, f = frames(), fins = finIds();
    fishObjs = f[0].fish.map((fi, k) => {
      const group = new T.Group(); group.matrixAutoUpdate = false;
      const mats = [], finGroups = {};
      fins.forEach((cid) => { const g = new T.Group(); g.matrixAutoUpdate = false; g.name = "hinge_" + cid; finGroups[cid] = g; group.add(g); });
      baked.forEach(({ name, geometry }) => {
        const col = name.startsWith("eye") ? LOOK.eye : (name === "body" || name.startsWith("operculum")) ? FISH_COLOR[k % FISH_COLOR.length] : LOOK.fin;
        const m = new T.MeshStandardMaterial({ color: col, roughness: 0.55, metalness: 0.05, side: T.DoubleSide, emissive: 0x000000 });
        mats.push(m);
        const mesh = new T.Mesh(geometry, m); mesh.userData.fish = fi.id; mesh.name = name;
        (finGroups[name] || group).add(mesh);
      });
      add(group); return { id: fi.id, group, mats, fins: finGroups };
    });
    trails = f[0].fish.map((_, k) => {
      const arr = new Float32Array(f.length * 3);
      f.forEach((fr, i) => arr.set(simToThree(fr.fish[k].position_m), i * 3));
      const g = new T.BufferGeometry(); g.setAttribute("position", new T.BufferAttribute(arr, 3)); g.setDrawRange(0, 1);
      const ln = new T.Line(g, new T.LineBasicMaterial({ color: FISH_COLOR[k % FISH_COLOR.length] })); ln.frustumCulled = false; add(ln); return ln;
    });
    const mg = new T.BufferGeometry(); mg.setAttribute("position", new T.BufferAttribute(new Float32Array(f[0].fish.length * 3), 3));
    markers = new T.Points(mg, new T.PointsMaterial({ color: 0xffffff, size: 7, sizeAttenuation: false, depthTest: false })); markers.frustumCulled = false; add(markers);
    let lo = [Infinity, Infinity], hi = [-Infinity, -Infinity];
    f.forEach((fr) => fr.fish.forEach((x) => { lo = [Math.min(lo[0], x.position_m[0]), Math.min(lo[1], x.position_m[1])]; hi = [Math.max(hi[0], x.position_m[0]), Math.max(hi[1], x.position_m[1])]; }));
    const span = Math.max(hi[0] - lo[0], hi[1] - lo[1], 2), cx = (lo[0] + hi[0]) / 2, cy = (lo[1] + hi[1]) / 2;
    ground = new T.GridHelper(Math.ceil(span * 1.4), Math.max(4, Math.round(span * 1.4)), 0x2f6f8f, 0x9fb8c8); ground.position.set(cx, 0, -cy);
    add(ground);
    if (tr.threat && vec(tr.threat.center_world_m, 3) && finite(tr.threat.radius_m)) {
      threatMesh = new T.Mesh(new T.SphereGeometry(tr.threat.radius_m, 24, 16), new T.MeshBasicMaterial({ color: 0xd04a2a, transparent: true, opacity: 0.12, depthWrite: false }));
      threatMesh.position.set(...simToThree(tr.threat.center_world_m)); add(threatMesh);
    } else threatMesh = null;
    if (finite(tr.neighbor_radius_m)) {
      const pts = []; for (let a = 0; a <= 64; a++) pts.push(new T.Vector3(Math.cos((a / 64) * 2 * Math.PI) * tr.neighbor_radius_m, 0, Math.sin((a / 64) * 2 * Math.PI) * tr.neighbor_radius_m));
      ring = new T.Line(new T.BufferGeometry().setFromPoints(pts), new T.LineBasicMaterial({ color: 0xd0a02a })); ring.visible = false; add(ring);
    } else ring = null;
  }

  function frameView() {
    const f = frames(), ps = f[0].fish.map((x) => x.position_m);
    let ext = 0; ps.forEach((a) => ps.forEach((b) => { ext = Math.max(ext, Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2])); }));
    const d = Math.max(0.8, ext * 1.6 + 0.6);
    const c = new T.Vector3(...simToThree(ps.reduce((s, p) => [s[0] + p[0] / ps.length, s[1] + p[1] / ps.length, s[2] + p[2] / ps.length], [0, 0, 0])));
    controls.target.copy(c); camera.position.set(c.x - d * 0.55, c.y + d * 0.35, c.z + d * 0.75);
    camera.near = 0.01; camera.far = 4000; camera.updateProjectionMatrix(); controls.minDistance = 0.15; controls.maxDistance = 600; controls.update();
  }
  function overview() {
    const f = frames(); const lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity];
    f.forEach((fr) => fr.fish.forEach((x) => x.position_m.forEach((v, i) => { lo[i] = Math.min(lo[i], v); hi[i] = Math.max(hi[i], v); })));
    const c = new T.Vector3(...simToThree([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2])), d = Math.max(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2], 1) * 1.1;
    controls.target.copy(c); camera.position.set(c.x - d * 0.2, c.y + d * 0.5, c.z + d * 1.1); controls.update();
  }
  function setView(v) {
    S.view = v; btnView.textContent = v === "follow" ? "View: follow school" : "View: whole track";
    if (v === "follow") frameView(); else overview();
    pose();
  }

  // ---- generic value display: whatever the file carries, verbatim
  function show(v) {
    if (v === null) return "null";
    if (typeof v === "number") return fmt(v);
    if (Array.isArray(v)) return v.every(finite) ? fmtV(v) : JSON.stringify(v);
    if (v && typeof v === "object") return Object.entries(v).map(([k, x]) => `${k}: ${show(x)}`).join("; ");
    return String(v);
  }
  function flatten(o, pre = "", out = []) {
    if (o && typeof o === "object" && !Array.isArray(o)) Object.entries(o).forEach(([k, v]) => flatten(v, pre ? pre + "." + k : k, out));
    else out.push([pre, o]);
    return out;
  }

  // ---- panels
  function buildPanels() {
    const tr = S.traj, f = frames();
    fishList.textContent = "";
    f[0].fish.forEach((fi, k) => {
      const li = el("li"); li.dataset.fish = fi.id;
      const b = el("button", null, fi.id); b.type = "button"; b.onclick = () => selectFish(S.selected === fi.id ? null : fi.id);
      const sw = el("span", "ev-sw"); sw.style.background = hex6(FISH_COLOR[k % FISH_COLOR.length]);
      li.append(sw, b, el("span", "ev-fs", "")); fishList.append(li);
    });
    // chart quantities: height, speed, every numeric scalar the file carries, each fin angle, and |force| where it is not null
    metric.textContent = "";
    const scal = Object.entries(f[0].fish[0]).filter(([, v]) => finite(v)).map(([k]) => k);
    [["height", "height z (m)"], ["speed", "speed |v| (m/s)"], ...scal.map((k) => [k, k]), ...finIds().map((c) => ["fin:" + c, `fin angle ${c} (rad)`]),
     ...FORCE_KEYS.filter((k) => k in f[0].fish[0]).map((k) => ["norm:" + k, `|${k}| (not drawn where null)`])].forEach(([v, l]) => { const o = el("option", null, l); o.value = v; metric.append(o); });
    metric.onchange = drawChart;
    receipt.textContent = ""; receipt.append(el("h4", null, "Run file"));
    const cs = tr.case && typeof tr.case === "object" ? tr.case : {};
    receipt.append(el("p", null, `${caseId(tr)}${tr.title ? " — " + tr.title : ""}${"feedback" in cs ? ` (feedback: ${cs.feedback}, neighbors: ${cs.neighbors})` : ""}${tr.scenario ? " — " + tr.scenario : ""}`));
    receipt.append(el("p", "mono", `from the file: ${f.length} saved states, ${f[0].fish.length} fish, ${fmt(f[f.length - 1].time_s - f[0].time_s, 3)} s` + (finite(tr.dt_s) ? `, integrator step ${tr.dt_s} s` : "") + (S.sha ? `, sha256 ${S.sha}` : "")));
    S.notes.forEach((n) => receipt.append(el("p", "ev-warn", n)));
    ["world_axes", "body_axes", "orientation_order", "angular_velocity_frame", "assumptions", "model_xml_sha256", "seed"].forEach((k) => { if (tr[k] !== undefined) receipt.append(el("p", "mono", `${k}: ${show(tr[k])}`)); });
    if (tr.provenance) Object.entries(tr.provenance).forEach(([k, v]) => receipt.append(el("p", "mono", `${k}: ${show(v)}`)));
    if (tr.summary && typeof tr.summary === "object") { receipt.append(el("h4", null, "Summary (from the run file)")); flatten(tr.summary).forEach(([k, v]) => receipt.append(el("p", "mono" + (v === false ? " ev-false" : ""), `${k}: ${show(v)}`))); }
    (S.receipts || []).forEach((r) => { const d = el("details", "ev-rcpt"); d.append(el("summary", null, `${r.label}${r.falseCount ? ` — ${r.falseCount} false flag(s)` : ""}`));
      r.rows.forEach(([k, v]) => d.append(el("p", "mono" + (v === false ? " ev-false" : ""), `${k}: ${show(v)}`))); if (r.falseCount) d.open = true; receipt.append(d); });
    links.textContent = "";
    (tr.equations || []).forEach((e) => { const li = el("li"); li.append(el("b", null, (e.id || "equation") + ": "), el("code", null, e.equation || ""));
      const h = e.source && safeHref((String(e.source).match(/https?:\/\/\S+/) || [""])[0]);
      li.append(document.createTextNode(" — "));
      if (h) { const a = el("a", null, e.source); a.href = h; a.target = "_blank"; a.rel = "noopener noreferrer"; li.append(a); } else li.append(document.createTextNode(e.source || "")); links.append(li); });
    (tr.sources || []).forEach((s) => { const li = el("li"), h = safeHref(s.url); if (h) { const a = el("a", null, s.url); a.href = h; a.target = "_blank"; a.rel = "noopener noreferrer"; li.append(a); } else li.append(el("span", null, s.url || "")); li.append(document.createTextNode(s.scope ? " — " + s.scope : "")); links.append(li); });
    scrub.max = f.length - 1; scrub.value = 0;
  }
  function updateStatus() {
    const f = frames(), last = f[f.length - 1], tr = S.traj, bits = [];
    const invalid = f[S.frame].fish.filter((x) => !x.force_model_valid).map((x) => x.id);
    const sm = tr.summary || {};
    if (sm.termination_reason) bits.push(`Run ended at t = ${fmt(last.time_s, 3)} s: ${sm.termination_reason}` + (sm.completed_duration === false ? " (did not complete the planned duration)" : ""));
    if (S.receiptFalse) bits.push(`False receipt flag(s), verbatim from the files: ${S.receipts.flatMap((r) => r.falsePaths.map((k) => `${r.label}: ${k}`)).join(", ")}. Read what each means; the viewer does not decide which are gates`);
    if (invalid.length) bits.push(`Out-of-domain / numerical-failure state at this saved state: ${invalid.join(", ")}; forces are null and this is not physics`);
    status.textContent = bits.join(" · "); status.hidden = !bits.length; status.dataset.state = invalid.length || S.receiptFalse ? "warn" : "info";
  }
  function updateReadout() {
    const f = frames(), i = S.frame;
    [...fishList.children].forEach((li, k) => { const a = f[i].fish[k];
      li.querySelector(".ev-fs").textContent = (a.active ? (a.escape_triggered ? "escape triggered" : "active") : "terminated: " + a.termination_reason) + (a.force_model_valid ? "" : " · force model invalid");
      li.setAttribute("aria-current", String(li.dataset.fish === S.selected)); });
    readout.textContent = "";
    if (!S.selected) { readout.append(el("p", "faint", "Select a fish (list or click) to read its saved state.")); return; }
    const k = fishIds().indexOf(S.selected), a = f[i].fish[k], fins = finIds();
    readout.append(el("h4", null, `${a.id} — saved state ${i + 1}, t = ${fmt(f[i].time_s, 3)} s`));
    if (!a.active) readout.append(el("p", "ev-warn", `Terminated: ${a.termination_reason}. Last actual state is retained; nothing is extrapolated.`));
    if (!a.force_model_valid) readout.append(el("p", "ev-warn", "Force model invalid at this state (domain exit or numerical failure): forces and torques are null, not zero, and nothing here is validated physics."));
    const rows = [], keys = [...FIELD_ORDER.filter((x) => x in a), ...Object.keys(a).filter((x) => x !== "id" && !FIELD_ORDER.includes(x))];
    keys.forEach((n) => {
      const v = a[n];
      if (n === "fin_angle_rad") fins.forEach((c) => rows.push([`fin_angle_rad[${c}]`, fmt(v[c])]));
      else if (["fin_command_rad", "fin_actuator_torque_Nm", "fin_effective_alpha_rad"].includes(n) && Array.isArray(v) && v.length === fins.length) v.forEach((x, j) => rows.push([`${n}[${fins[j]}]`, fmt(x)]));
      else rows.push([n, show(v) + (n === "linear_velocity_m_s" && vec(v, 3) ? `  |v| ${fmt(Math.hypot(...v))}` : "")]);
    });
    const t = el("table"); rows.forEach(([n, v]) => { const r = el("tr"); r.append(el("th", null, n), el("td", null, v)); t.append(r); }); readout.append(t);
    readout.append(el("p", "faint", "Per-fin arrays are labelled in fin_angle_rad key order (the file does not name them: confirm with native). " +
      (S.traj.angular_velocity_frame === "body" ? "Angular velocity is BODY frame; positions, velocities, forces and torques are WORLD frame." : "See the file's frame notes.")));
  }
  function series(k, key) {
    const f = frames();
    return f.map((fr) => { const a = fr.fish[k];
      if (key === "height") return a.position_m[2];
      if (key === "speed") return Math.hypot(...a.linear_velocity_m_s);
      if (key.startsWith("fin:")) return a.fin_angle_rad[key.slice(4)];
      if (key.startsWith("norm:")) { const v = a[key.slice(5)]; return v ? Math.hypot(...v) : NaN; }
      return a[key]; });
  }
  function drawChart() {
    const c = chart.getContext("2d"), W = chart.width, H = chart.height; c.clearRect(0, 0, W, H);
    if (!S.traj || !metric.value) return;
    const k = Math.max(0, fishIds().indexOf(S.selected)), key = metric.value, ys = series(k, key), f = frames(), ok = ys.filter(finite);
    const t0 = f[0].time_s, t1 = f[f.length - 1].time_s, lo = Math.min(...ok), hi = Math.max(...ok), pad = 34, span = hi - lo || 1;
    const X = (t) => pad + ((t - t0) / (t1 - t0 || 1)) * (W - pad - 8), Y = (v) => H - 22 - ((v - lo) / span) * (H - 34);
    c.strokeStyle = "#999"; c.lineWidth = 1; c.beginPath(); c.moveTo(pad, 6); c.lineTo(pad, H - 22); c.lineTo(W - 8, H - 22); c.stroke();
    c.fillStyle = "#333"; c.font = "11px sans-serif"; c.fillText(fmt(hi, 3), 2, 14); c.fillText(fmt(lo, 3), 2, H - 24); c.fillText(fmt(t0, 2) + " s", pad, H - 8); c.fillText(fmt(t1, 2) + " s", W - 52, H - 8);
    c.strokeStyle = hex6(FISH_COLOR[k % FISH_COLOR.length]); c.lineWidth = 2; c.beginPath(); let pen = false;
    f.forEach((fr, i) => { if (!finite(ys[i])) { pen = false; return; } if (pen) c.lineTo(X(fr.time_s), Y(ys[i])); else { c.moveTo(X(fr.time_s), Y(ys[i])); pen = true; } }); c.stroke();
    const e = f.findIndex((fr) => fr.fish[k].escape_triggered), deadIdx = f.findIndex((fr) => !fr.fish[k].active), bad = f.findIndex((fr) => !fr.fish[k].force_model_valid);
    S.chart = { metric: key, fish: fishIds()[k], escape_index: e, terminated_index: deadIdx, force_invalid_index: bad, points: ys.length, plotted: ok.length };
    const mark = (idx, col, txt, y) => { if (idx < 0) return; c.strokeStyle = col; c.lineWidth = 1; c.setLineDash([4, 3]); c.beginPath(); c.moveTo(X(f[idx].time_s), 6); c.lineTo(X(f[idx].time_s), H - 22); c.stroke(); c.setLineDash([]); c.fillStyle = col; c.fillText(txt, X(f[idx].time_s) + 3, y); };
    mark(e, "#d04a2a", "escape_triggered", 16); mark(deadIdx, "#555", "terminated", 28); mark(bad, "#9a1b1b", "force model invalid", 40);
    c.strokeStyle = "#0e7c86"; c.lineWidth = 1.5; c.beginPath(); c.moveTo(X(f[S.frame].time_s), 6); c.lineTo(X(f[S.frame].time_s), H - 22); c.stroke();
    chart.setAttribute("aria-label", `${metric.selectedOptions[0] ? metric.selectedOptions[0].textContent : key} for ${S.selected || fishIds()[0]} over time, from ${f.length} saved states`);
  }

  function selectFish(id) {
    if (id && !fishIds().includes(id)) return false;
    if (S.selected) { const o = fishObjs[fishIds().indexOf(S.selected)]; o && o.mats.forEach((m) => m.emissive.setHex(0x000000)); }
    S.selected = id || null;
    if (S.selected) { const o = fishObjs[fishIds().indexOf(id)]; o.mats.forEach((m) => { m.emissive.setHex(0x0e7c86); m.emissiveIntensity = 0.5; }); }
    pose(); emit("select", { id: S.selected }); return true;
  }

  // ---- loop / controls
  function loop(ts) {
    if (disposed || !renderer) return;
    raf = requestAnimationFrame(loop);
    const dt = last ? Math.min(0.1, (ts - last) / 1000) : 0; last = ts;
    if (S.playing && S.traj) {
      const f = frames(), end = f[f.length - 1].time_s;
      S.t = Math.min(end, S.t + dt * S.speed);
      if (S.t >= end) setPlaying(false);
      pose();
    }
    if (controls.update()) dirty = true;
    if (!dirty) return;
    dirty = false; renderer.render(scene, camera);
  }
  function setPlaying(p) {
    S.playing = !!p; btnPlay.textContent = S.playing ? "Pause" : "Play"; btnPlay.setAttribute("aria-pressed", String(S.playing)); last = 0;
    if (S.playing && S.traj && S.t >= frames()[frames().length - 1].time_s) S.t = frames()[0].time_s;
    emit("playing", { playing: S.playing });
  }
  function seek(t) { if (!S.traj) return; const f = frames(); S.t = Math.min(f[f.length - 1].time_s, Math.max(f[0].time_s, t)); pose(); }
  function seekIndex(i) { const f = frames(); seek(f[Math.max(0, Math.min(f.length - 1, i))].time_s); }
  btnPlay.onclick = () => setPlaying(!S.playing);
  speed.onchange = () => { S.speed = +speed.value; };
  interpCb.onchange = () => { S.interp = interpCb.checked; pose(); };
  scrub.oninput = () => { setPlaying(false); seekIndex(+scrub.value); };
  btnView.onclick = () => setView(S.view === "follow" ? "overview" : "follow");

  function wireInput(canvas) {
    canvas.tabIndex = 0; canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", "3D view of the saved-state trajectory. Space plays or pauses, left and right arrows step one saved state, 0 restarts. Drag to orbit, scroll to zoom.");
    let down = null;
    canvas.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; });
    canvas.addEventListener("pointerup", (e) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) { down = null; return; }
      down = null;
      if (!S.traj) return;
      const r = canvas.getBoundingClientRect(), rc = new T.Raycaster();
      rc.setFromCamera(new T.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
      const hit = rc.intersectObjects(fishObjs.map((o) => o.group), true)[0];
      if (hit) return void selectFish(hit.object.userData.fish);
      // the markers are the clickable stand-ins when the real-size mesh is a few pixels wide
      const pos = markers.geometry.attributes.position.array; let best = null;
      for (let k = 0; k < pos.length; k += 3) { const v = new T.Vector3(pos[k], pos[k + 1], pos[k + 2]).project(camera);
        const d = Math.hypot(((v.x + 1) / 2) * r.width - (e.clientX - r.left), ((1 - v.y) / 2) * r.height - (e.clientY - r.top)); if (d < 10 && (!best || d < best.d)) best = { d, id: fishIds()[k / 3] }; }
      selectFish(best ? best.id : null);
    });
    canvas.addEventListener("keydown", (e) => {
      if (!S.traj) return;
      if (e.key === " ") setPlaying(!S.playing);
      else if (e.key === "ArrowRight") { setPlaying(false); seekIndex(S.frame + 1); }
      else if (e.key === "ArrowLeft") { setPlaying(false); seekIndex(S.frame - 1); }
      else if (e.key === "0" || e.key === "Home") { setPlaying(false); seekIndex(0); }
      else return;
      e.preventDefault();
    });
    controls.addEventListener("change", draw);
    canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); unavailable("WebGL context lost"); });
  }

  function unavailable(reason, problems = []) {
    S.mode = "unavailable"; S.reason = String(reason); S.problems = problems; S.traj = null;
    setPlaying(false); if (scene) disposeScene();
    note.hidden = false; note.dataset.state = "unavailable";
    note.textContent = `Trajectory not available: ${S.reason}` + (problems.length ? " — " + problems.slice(0, 5).join("; ") : "");
    [btnPlay, btnView, speed, interpCb, scrub].forEach((x) => (x.disabled = true));
    clock.textContent = ""; modeLabel.textContent = ""; fishList.textContent = ""; readout.textContent = ""; links.textContent = ""; receipt.textContent = ""; status.hidden = true; metric.textContent = "";
    chart.getContext("2d").clearRect(0, 0, chart.width, chart.height);
    if (renderer) renderer.domElement.style.visibility = "hidden";
    emit("unavailable", { reason: S.reason });
    return false;
  }

  const sha256Of = async (buf) => (globalThis.crypto && crypto.subtle ? [...new Uint8Array(await crypto.subtle.digest("SHA-256", buf))].map((b) => b.toString(16).padStart(2, "0")).join("") : null);
  const getJson = async (url) => { const r = await fetch(new URL(url, document.baseURI).href); if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`); return r.json(); };

  async function setCase(id) {
    const c = cases.find((x) => x.id === id) || cases[0];
    if (!c || !libs) return false;
    setPlaying(false); S.caseId = c.id; S.selected = null; S.t = 0; S.chart = null; S.receipts = []; S.receiptFalse = 0; S.sha = null;
    [...caseBar.children].forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.case === c.id)));
    const t0 = performance.now();
    let traj;
    try {
      const r = await fetch(new URL(c.url, document.baseURI).href);
      if (!r.ok) return unavailable(`${c.url}: HTTP ${r.status}`);
      const buf = await r.arrayBuffer(); S.sha = await sha256Of(buf);
      traj = JSON.parse(new TextDecoder().decode(buf));
    } catch (e) { return unavailable(`${c.url}: ${e.message}`); }
    S.perf.fetch_ms = Math.round(performance.now() - t0);
    const v = validateTrajectory(traj);
    if (v.problems.length) return unavailable(`${c.url} does not satisfy the contract`, v.problems);
    const finsHere = Object.keys(traj.frames[0].fish[0].fin_angle_rad);
    const missing = finsHere.filter((k) => !(panels && panels.fins && panels.fins[k] && vec(panels.fins[k].fin_plane && panels.fins[k].fin_plane.origin_m, 3)));
    if (missing.length) return unavailable(`${panelsUrl} has no fin_plane.origin_m for ${missing.join(", ")}, so those fin hinges cannot be placed`);
    const missingMesh = finsHere.filter((k) => !protoSrc.some((m) => m.name === k));
    if (missingMesh.length) return unavailable(`the mesh ${meshUrl} has no component named ${missingMesh.join(", ")}`);
    // declared receipts are required: a listed file that fails is an error that names it
    const receipts = [];
    try {
      for (const rc of c.receipts || []) {
        const j = await getJson(rc.url), sel = rc.select ? j[rc.select] : j;
        if (sel === undefined) throw new Error(`${rc.url}: no entry ${rc.select}`);
        const rows = flatten(sel), fl = rows.filter(([, x]) => x === false).map(([k]) => k); receipts.push({ label: rc.label || rc.url, rows, falseCount: fl.length, falsePaths: fl });
      }
    } catch (e) { return unavailable(e.message); }
    disposeScene();
    S.traj = traj; S.mode = "ready"; S.problems = []; S.notes = v.notes; S.receipts = receipts; S.receiptFalse = receipts.reduce((s, r) => s + r.falseCount, 0);
    const dts = traj.frames.slice(1).map((fr, i) => fr.time_s - traj.frames[i].time_s).sort((a, b) => a - b); S.period = dts.length ? dts[dts.length >> 1] : 0;
    const cg = traj.geometry.cg_from_nose_m; hinge = {};
    finsHere.forEach((k) => { const o = panels.fins[k].fin_plane.origin_m; hinge[k] = [-(o[0] - cg), -o[1], o[2]]; });       // Rz(pi) * (origin - [cg,0,0])
    bake(cg); buildScene(); buildPanels();
    [btnPlay, btnView, speed, interpCb, scrub].forEach((x) => (x.disabled = false));
    renderer.domElement.style.visibility = "visible"; note.hidden = true;
    S.view = "follow"; btnView.textContent = "View: follow school"; frameView(); S.frame = 0;
    pose(); loop(0);
    emit("case", { id: c.id, frames: frames().length, fish: fishIds().length });
    return true;
  }

  async function load() {
    try {
      if (!(() => { try { const c = document.createElement("canvas"); return !!(c.getContext("webgl2") || c.getContext("webgl")); } catch { return false; } })()) return unavailable("WebGL is not available in this browser");
      const [Th, { GLTFLoader }, { OrbitControls }] = await Promise.all([import(THREE_URL), import(GLTF_URL), import(ORBIT_URL)]);
      T = Th; libs = { T };
      try { panels = await getJson(panelsUrl); } catch (e) { return unavailable(e.message); }
      const r = await fetch(meshUrl); if (!r.ok) return unavailable(`${meshUrl}: HTTP ${r.status}`);
      const gltf = await new Promise((ok, no) => r.arrayBuffer().then((buf) => new GLTFLoader().parse(buf, "", ok, no), no));
      protoSrc = [];
      gltf.scene.traverse((o) => { if (o.isMesh && !omit.has(o.name)) protoSrc.push({ name: o.name, src: o.geometry.clone() }); });
      S.meshComponents = protoSrc.map((m) => m.name); S.omitted = [...omit];
      renderer = new T.WebGLRenderer({ antialias: true, alpha: true }); renderer.setClearColor(0x000000, 0);
      const canvas = renderer.domElement; stage.insertBefore(canvas, note);
      scene = new T.Scene(); camera = new T.PerspectiveCamera(35, 16 / 10, 0.01, 4000);
      scene.add(new T.HemisphereLight(0xffffff, 0x6b7a88, 1.2)); const key = new T.DirectionalLight(0xffffff, 2.2); key.position.set(0.5, 1, 0.6); scene.add(key);
      controls = new OrbitControls(camera, canvas); controls.enableDamping = true; controls.dampingFactor = 0.12;
      const resize = () => { const w = Math.max(1, stage.clientWidth), h = Math.max(1, stage.clientHeight); renderer.setPixelRatio(Math.min(devicePixelRatio || 1, 2)); renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); draw(); };
      resize(); ro = new ResizeObserver(resize); ro.observe(stage); wireInput(canvas);
      cases.forEach((c) => { const b = el("button", null, c.label || c.id); b.type = "button"; b.dataset.case = c.id; b.setAttribute("aria-pressed", "false"); b.onclick = () => setCase(c.id); caseBar.append(b); });
      S.mode = "ready";
      await setCase(cases[0] && cases[0].id);
      emit("ready", { mode: S.mode });
    } catch (e) { unavailable(e && e.message ? e.message : e); }
  }

  const ready = new Promise((res) => {
    const start = () => load().then(res, res);
    if (!lazy || !("IntersectionObserver" in window)) start();
    else { io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); start(); } }, { rootMargin: "200px" }); io.observe(host); }
  });
  return {
    ready, state: () => ({ ...S, traj: undefined, frames: frames().length, fish: fishIds(), fins: S.traj ? finIds() : [], omitted: S.omitted, dynObjects: dyn.length }),
    setCase, play: () => setPlaying(true), pause: () => setPlaying(false), seek, seekIndex, setInterpolate: (b) => { interpCb.checked = !!b; S.interp = !!b; pose(); },
    selectFish, setView, setSpeed: (s) => { S.speed = s; speed.value = String(s); },
    screenOf: (id) => { const k = fishIds().indexOf(id), a = markers.geometry.attributes.position.array, r = renderer.domElement.getBoundingClientRect();
      const v = new T.Vector3(a[3 * k], a[3 * k + 1], a[3 * k + 2]).project(camera); return [r.left + ((v.x + 1) / 2) * r.width, r.top + ((1 - v.y) / 2) * r.height]; },
    // sim-frame world position of a rest-pose mesh point (metres, x snout->tail) from the contract formula, and of an actual vertex of the
    // scene graph (fins included, with their hinge rotation), so tests can check the rendered chain against an independent calculation
    fishPointWorld: (id, p, t, interp) => worldOf(fishIds().indexOf(id), p, t, interp),
    hingeBody: () => ({ ...hinge }),
    sceneVertexWorld: (id, comp, vi) => {
      const o = fishObjs[fishIds().indexOf(id)]; o.group.updateMatrixWorld(true);
      let m = null; o.group.traverse((c) => { if (c.isMesh && c.name === comp) m = c; });
      const v = new T.Vector3().fromBufferAttribute(m.geometry.attributes.position, vi).applyMatrix4(m.matrixWorld);
      return [v.x, -v.z, v.y];                                  // three axes -> sim axes
    },
    destroy() { disposed = true; cancelAnimationFrame(raf); io && io.disconnect(); ro && ro.disconnect(); if (scene) disposeScene(); if (renderer) { renderer.dispose(); renderer.domElement.remove(); } host.textContent = ""; host.classList.remove("ev"); },
  };
}
