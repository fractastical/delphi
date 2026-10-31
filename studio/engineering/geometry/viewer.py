"""Self-contained mesh viewer page (three.js from cdnjs; meshes, numbers and the graph image embedded)."""
from __future__ import annotations

import base64
import html
import json

G = 9.80665

PAGE = r"""<title>Flying-Fish Print Forms</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wght@400;600&family=JetBrains+Mono:wght@400;600&display=swap">
<style>
/* layout: one working column; viewer first, then the numbers that made it */
:root {
  --bg: #f3f6f7; --panel: #ffffff; --fg: #15232b; --muted: #536770; --line: #d5dee2;
  --accent: #1f6f8b; --warn: #a24b1c; --ok: #2c7a4b; --mesh: #3b7ea8; --stand: #a8a59a;
  --sans: "Instrument Sans", "Segoe UI", system-ui, sans-serif; --mono: "JetBrains Mono", ui-monospace, monospace;
}
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg: #0f171b; --panel: #16232a; --fg: #e3ecef; --muted: #93a9b2; --line: #2a3b43;
  --accent: #6cc0dd; --warn: #f0a273; --ok: #7fd3a0; --mesh: #6fb3d9; --stand: #8d8a80; color-scheme: dark } }
:root[data-theme="dark"] {
  --bg: #0f171b; --panel: #16232a; --fg: #e3ecef; --muted: #93a9b2; --line: #2a3b43;
  --accent: #6cc0dd; --warn: #f0a273; --ok: #7fd3a0; --mesh: #6fb3d9; --stand: #8d8a80; color-scheme: dark }
body { background: var(--bg); color: var(--fg); font: 15px/1.5 var(--sans);
  padding-left: max(16px, env(safe-area-inset-left, 0px)); padding-right: max(16px, env(safe-area-inset-right, 0px));
  padding-block: 20px 40px; }
main { max-width: 1060px; margin: 0 auto; display: grid; gap: 20px; }
h1 { font-size: 1.6rem; margin: 0; text-wrap: balance; }
h2 { font-size: 1.1rem; margin: 0 0 8px; text-wrap: balance; }
p { margin: 0; max-width: 72ch; }
.muted { color: var(--muted); }
.banner { border: 1px solid var(--warn); color: var(--fg); background: var(--panel); border-radius: 6px;
  padding: 10px 14px; display: grid; gap: 4px; }
.banner strong { color: var(--warn); }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; }
.tabs button, .ctl button { font: 600 0.9rem var(--sans); color: var(--fg); background: var(--panel);
  border: 1px solid var(--line); border-radius: 4px; padding: 6px 12px; cursor: pointer; }
.tabs button[aria-pressed="true"] { border-color: var(--accent); color: var(--accent); }
button:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.stage { display: grid; grid-template-columns: minmax(0, 1.6fr) minmax(0, 1fr); gap: 16px; }
@media (max-width: 760px) { .stage { grid-template-columns: minmax(0, 1fr); } }
.view { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; position: relative;
  aspect-ratio: 4 / 3; max-width: 100%; overflow: hidden; touch-action: none; }
.view canvas { width: 100%; height: 100%; display: block; }
.ctl { position: absolute; left: 8px; bottom: 8px; display: flex; gap: 6px; flex-wrap: wrap; }
.hint { position: absolute; right: 10px; top: 8px; font: 0.75rem var(--mono); color: var(--muted); }
.side { display: grid; gap: 10px; align-content: start; min-width: 0; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { font: 600 0.75rem var(--mono); border-radius: 999px; padding: 2px 10px; border: 1px solid var(--line); }
.chip.bad { color: var(--warn); border-color: var(--warn); }
.chip.good { color: var(--ok); border-color: var(--ok); }
.chip.neutral { color: var(--muted); }
.tbl { overflow-x: auto; }
table { border-collapse: collapse; width: 100%; font-size: 0.85rem; font-variant-numeric: tabular-nums; }
th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--line); vertical-align: top; }
th { color: var(--muted); font-weight: 600; font-size: 0.75rem; letter-spacing: 0.03em; text-transform: uppercase; }
td.num { font-family: var(--mono); white-space: nowrap; }
td.src { color: var(--muted); font-size: 0.75rem; }
.card { background: var(--panel); border: 1px solid var(--line); border-radius: 6px; padding: 14px; display: grid; gap: 10px; min-width: 0; }
.graph img { width: 100%; height: auto; background: #ffffff; border-radius: 4px; }
ul { margin: 0; padding-left: 1.2em; }
code { font-family: var(--mono); font-size: 0.8rem; overflow-wrap: anywhere; }
@media (prefers-reduced-motion: reduce) { * { transition: none !important; } }
</style>
<main>
  <header style="display:grid;gap:6px">
    <h1>Flying-fish print forms</h1>
    <p class="muted">Three parametric props at one biological mass (0.1 kg), drawn from the exported STL triangles. Biological values are in SI; the prop is 1 m = __K__ mm, with thickened fins.</p>
  </header>
  <div class="banner" role="note">
    <strong>Form studies pending a validated candidate.</strong>
    <span>__LABEL__</span>
  </div>
  <div class="tabs" role="group" aria-label="Form" id="tabs"></div>
  <section class="stage">
    <div class="view" id="view"><span class="hint">drag to rotate · wheel or pinch to zoom</span>
      <div class="ctl"><button id="standBtn" type="button" aria-pressed="false">Show stand</button><button id="resetBtn" type="button">Reset view</button></div>
    </div>
    <div class="side">
      <h2 id="ftitle"></h2>
      <div class="chips" id="chips"></div>
      <p id="frole" class="muted"></p>
      <p id="fnote" class="muted"></p>
    </div>
  </section>
  <section class="card"><h2>Biological design point and the prop made from it</h2><div class="tbl"><table id="tbl"></table></div>
    <p class="muted">Wing area follows Fish 1990's definition (pectoral + pelvic fins + body rectangles at the fin bases). Wing loading is m·g/S. The solver is dx-guilds' z3 model at commit __SOLVER__ (blob sha256 __BLOB__); "feasible" means an exact point satisfies the declared constraints in that model, nothing more.</p></section>
  <section class="card graph"><h2>Analogues and engineered forms</h2>
    <p class="muted">Sourced relationships are solid; conjectured routes between the engineered forms are dashed red and claim nothing about reachability.</p>
    <img alt="Graph separating extant, experimental and fossil analogues from the three engineered forms" src="data:image/png;base64,__GRAPH__"></section>
  <section class="card"><h2>Not checked</h2><ul>
    <li>Global self-intersection, slicing, supports, cups and minima. These depend on printer, resin and orientation, and PreForm checks them.</li>
    <li>No physical print and no PreForm run. Resin volume and print time come only from the slicer.</li>
    <li>Aerodynamics of the prop or the design. Visual likeness is not aerodynamic fidelity, and the glide simulation has not run on these candidates.</li>
    <li>Biological feasibility, ancestry and evolutionary reachability. None are claimed.</li>
  </ul></section>
  <p class="muted" style="font-size:0.8rem">Build code sha256 <code>__CODE__</code>. Sources: Fish 1990 J. Zool. 221:391-403 (full text, sha256 1efed334…); Daane et al. 2021 Curr. Biol. 31:5052 Data S1A (per-specimen fin lengths, recomputed); Formlabs Design Specs and PreForm API pages (read 2026-10-31).</p>
</main>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
const FORMS = __DATA__;
function dec(b64, T) { const s = atob(b64), u = new Uint8Array(s.length); for (let i = 0; i < s.length; i++) u[i] = s.charCodeAt(i); return new T(u.buffer); }
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const view = document.getElementById('view');
const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));
view.prepend(renderer.domElement);
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(32, 4 / 3, 1, 5000);
scene.add(new THREE.HemisphereLight(0xffffff, 0x445566, 0.9));
const sun = new THREE.DirectionalLight(0xffffff, 0.8); sun.position.set(60, -80, 120); scene.add(sun);
const root = new THREE.Group(); scene.add(root);
let fishMesh = null, standMesh = null, showStand = false, current = 0;
let rotX = -1.05, rotZ = -0.6, dist = 210;
function geom(v, t) { const g = new THREE.BufferGeometry(); g.setAttribute('position', new THREE.BufferAttribute(dec(v, Float32Array), 3));
  g.setIndex(new THREE.BufferAttribute(dec(t, Uint32Array), 1)); g.computeVertexNormals(); return g; }
function load(i) {
  current = i; const f = FORMS[i];
  root.clear();
  fishMesh = new THREE.Mesh(geom(f.v, f.t), new THREE.MeshStandardMaterial({ color: css('--mesh'), roughness: 0.55, metalness: 0.05 }));
  standMesh = new THREE.Mesh(geom(f.sv, f.st), new THREE.MeshStandardMaterial({ color: css('--stand'), roughness: 0.8 }));
  root.add(fishMesh); root.add(standMesh); standMesh.visible = showStand;
  const box = new THREE.Box3().setFromObject(fishMesh), c = box.getCenter(new THREE.Vector3());
  root.position.set(0, 0, 0); fishMesh.position.sub(c); standMesh.position.sub(c);
  document.querySelectorAll('#tabs button').forEach((b, j) => b.setAttribute('aria-pressed', String(j === i)));
  document.getElementById('ftitle').textContent = f.title;
  document.getElementById('frole').textContent = f.role;
  document.getElementById('fnote').textContent = f.note || '';
  const chips = document.getElementById('chips'); chips.replaceChildren();
  for (const [txt, cls] of f.chips) { const s = document.createElement('span'); s.className = 'chip ' + cls; s.textContent = txt; chips.append(s); }
  const tbl = document.getElementById('tbl'); tbl.replaceChildren();
  const hr = tbl.insertRow(); for (const h of ['Quantity', 'Biological (SI)', 'Prop', 'Basis']) { const th = document.createElement('th'); th.textContent = h; hr.append(th); }
  for (const r of f.rows) { const tr = tbl.insertRow(); r.forEach((c, k) => { const td = tr.insertCell(); td.textContent = c; if (k === 1 || k === 2) td.className = 'num'; if (k === 3) td.className = 'src'; }); }
  draw();
}
function size() { const w = view.clientWidth, h = view.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); draw(); }
function draw() {
  root.rotation.set(0, 0, 0); root.rotateX(rotX); root.rotateZ(rotZ);
  camera.position.set(0, 0, dist); camera.lookAt(0, 0, 0); renderer.render(scene, camera);
}
FORMS.forEach((f, i) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = f.short; b.addEventListener('click', () => load(i)); document.getElementById('tabs').append(b); });
document.getElementById('standBtn').addEventListener('click', e => { showStand = !showStand; e.currentTarget.setAttribute('aria-pressed', String(showStand)); e.currentTarget.textContent = showStand ? 'Hide stand' : 'Show stand'; if (standMesh) standMesh.visible = showStand; draw(); });
document.getElementById('resetBtn').addEventListener('click', () => { rotX = -1.05; rotZ = -0.6; dist = 210; draw(); });
let drag = null; const pts = new Map();
view.addEventListener('pointerdown', e => { if (e.target.closest('button')) return; view.setPointerCapture(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]); drag = [e.clientX, e.clientY]; });
view.addEventListener('pointermove', e => {
  if (!pts.has(e.pointerId)) return;
  if (pts.size === 2) { const [a, b] = [...pts.values()]; const d0 = Math.hypot(a[0] - b[0], a[1] - b[1]); pts.set(e.pointerId, [e.clientX, e.clientY]); const [a2, b2] = [...pts.values()]; const d1 = Math.hypot(a2[0] - b2[0], a2[1] - b2[1]); dist = Math.min(900, Math.max(80, dist * d0 / Math.max(d1, 1))); draw(); return; }
  pts.set(e.pointerId, [e.clientX, e.clientY]);
  rotZ += (e.clientX - drag[0]) * 0.01; rotX += (e.clientY - drag[1]) * 0.01; drag = [e.clientX, e.clientY]; draw(); });
const up = e => { pts.delete(e.pointerId); };
view.addEventListener('pointerup', up); view.addEventListener('pointercancel', up);
view.addEventListener('wheel', e => { e.preventDefault(); dist = Math.min(900, Math.max(80, dist * (1 + Math.sign(e.deltaY) * 0.08))); draw(); }, { passive: false });
new ResizeObserver(size).observe(view);
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => load(current));
load(0); size();
</script>
"""


def _fmt(x, nd=4):
    return f"{x:.{nd}g}"


def form_payload(design: dict, mesh_b64: dict) -> dict:
    bio = design["biological_design_SI"]
    b = design["prop_mm"]["built"]
    k = 1000 * design["prop_mm"]["display_scale"]
    st = design["engineering_status"]
    m, S, span = bio["mass_kg"]["value"], bio["wing_area_m2"]["value"], bio["wing_span_m"]["value"]
    sl = bio["standard_length_m"]["value"]
    lay = bio["fin_layout_bio"]["value"]
    v = design["validation"]
    chips = [("solver: " + st["solver"] + (" {" + ", ".join(st["solver_conflict"]) + "}" if st["solver_conflict"] else ""),
              "good" if st["solver"] == "feasible" else "bad"),
             ("glide sim: " + st["glide"]["status"].replace("_", " "), "neutral"),
             ("mesh checks: " + ("pass" if v["ok"] else "FAIL"), "good" if v["ok"] else "bad"),
             ("stand checks: " + ("pass" if design["stand"]["validation"]["ok"] else "FAIL"),
              "good" if design["stand"]["validation"]["ok"] else "bad"),
             ("resolution converged" if design["convergence"]["converged"] else "NOT converged",
              "good" if design["convergence"]["converged"] else "bad")]
    size = v["bounds_mm"]["size"]
    rows = [
        ["Mass", f"{_fmt(m)} kg", "solid resin, slicer reports", bio["mass_kg"].get("locator", "")],
        ["Standard length", f"{_fmt(sl)} m", f"{sl * k:.1f} mm", bio["standard_length_m"].get("locator", "")],
        ["Wing area S", f"{_fmt(S)} m²", f"{S * k * k:.0f} mm² (planform)", bio["wing_area_m2"].get("locator") or
         bio["wing_area_m2"].get("note", "")],
        ["Wing span", f"{_fmt(span)} m", f"{b['span_built_bbox_bio_m'] * k:.1f} mm built (dihedral, rounded tips)",
         bio["wing_span_m"].get("locator") or bio["wing_span_m"].get("note", "")],
        ["Wing loading m·g/S", f"{m * G / S:.0f} N/m²", "n/a", "derived; Fish 1990 measured 11.7-208.9 N/m²"],
        ["Pectoral length / SL", f"{lay['pectoral_length_over_sl']:.3f}", "same ratio",
         "Daane 2021 S1A halfbeak median" if "pectoral_length_over_sl" in bio else "from Fish 1990 span fit"],
        ["Pelvic length / SL", f"{lay['pelvic_length_over_sl']:.3f}", "same ratio",
         bio["pelvic_length_over_sl"].get("locator", "")],
        ["Pectoral share of S", f"{lay['pectoral_share']:.3f}", "same", bio["pectoral_share"].get("locator") or
         bio["pectoral_share"].get("note", "")],
        ["Body volume", f"{_fmt(bio['body_volume_m3']['value'])} m³", f"{b['body_loft_volume_mm3']:.0f} mm³ body loft",
         "mass / 1025 kg/m³ (design assumption)"],
        ["Fin thickness", "not modelled", f"{design['print_parameters']['fin_thickness_mm']['value']} mm plate",
         f"print choice (= {design['prop_mm']['fin_thickness_exaggeration']['equivalent_biological_mm']:.1f} mm at "
         "biological scale)"],
        ["Prop extent", "", f"{size[0]:.1f} × {size[1]:.1f} × {size[2]:.1f} mm", "fits a 120 mm box"],
        ["Prop solid volume", "", f"{v['signed_volume_mm3']:.0f} mm³", "solid, no internal cavity"],
        ["Sampled wall min", "", f"{v['wall_thickness']['min_mm']:.2f} mm", f"{v['wall_thickness']['samples']} inward rays"],
        ["Mesh sha256", "", v["mesh_sha256"][:16] + "…", "canonical vertex/face hash"],
    ]
    short = {"A": "A · short-fin precursor-inspired", "B": "B · two-wing", "C": "C · four-wing"}[design["id"][0]]
    return {"short": short, "title": design["title"], "role": design["role"], "note": design.get("status_note") or "",
            "chips": chips, "rows": rows, **mesh_b64}


def page(designs: list[dict], meshes: list[dict], graph_png: bytes, label: str, run: dict, scale: float) -> str:
    data = [form_payload(d, m) for d, m in zip(designs, meshes)]
    out = PAGE.replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    out = out.replace("__GRAPH__", base64.b64encode(graph_png).decode())
    out = out.replace("__LABEL__", html.escape(label.replace("Form study pending a validated candidate. ", ""))).replace("__K__", f"{1000 * scale:.0f}")
    out = out.replace("__SOLVER__", run["solver"]["commit"][:7]).replace("__BLOB__", run["solver"]["blob_sha256"][:16] + "…")
    return out.replace("__CODE__", run["code_sha256"])
