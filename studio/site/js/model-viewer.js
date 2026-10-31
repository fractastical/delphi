// Reusable lazy-loaded viewer for the ACTUAL fish3d GLBs (not the schematic canvas in fish.js).
//
//   import { mountFishViewer } from "./model-viewer.js";
//   const v = mountFishViewer(el, {
//     base: "artifacts/fish3d/fish3d-v3a-fan/", layout: "hero",
//     variants: [{ id: "adult-fao", glb: "fish-adult-fao.glb", appearance: "appearance-adult-fao.json",
//                  poster: "preview-adult-fao.png" }, ...] });   // omit for the N1 baseline (fish.glb)
//   await v.ready;            // resolves once interactive OR once the static fallback is showing
//
// Materials: whatever the GLB carries is kept (glTF materials, COLOR_0 vertex colours, alpha modes,
// textures).  A flat appearance-only colour is used ONLY for a mesh with no material and no vertex
// colours, and the status line says so.  Normals are computed only when the GLB has none.
// Components are the GLB's own nodes (any names, any depth, several primitives per node); each is
// matched by name to components.json, and nodes without a record are shown as having none.
// The expected sha256 comes from opts/variant, the variant's appearance JSON, render.json or
// build.json (in that order); if none records one the status says "hash not recorded".
// three.js 0.170.0 is vendored (site/vendor/three/VENDOR.json).  All data text uses textContent.

const THREE_URL = new URL("../vendor/three/lib/three.module.js", import.meta.url).href;
const GLTF_URL = new URL("../vendor/three/examples/jsm/loaders/GLTFLoader.js", import.meta.url).href;
const ORBIT_URL = new URL("../vendor/three/examples/jsm/controls/OrbitControls.js", import.meta.url).href;

// Fallback colours for a mesh that carries neither a material nor vertex colours. Appearance only.
const LOOK = { body: 0x9fb4c4, scales: 0xb9c6d0, eye: 0x1c2630, operculum: 0xa9bccb, fin: 0xcfd9e0 };
const lookOf = (n) => (n === "body" ? LOOK.body : n.startsWith("scales") ? LOOK.scales : n.startsWith("eye") ? LOOK.eye
  : n.startsWith("operculum") ? LOOK.operculum : LOOK.fin);

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};
const fetchJson = async (url, optional = false) => {
  try {
    const r = await fetch(url);
    if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
    return await r.json();
  } catch (e) {
    if (optional) return null;
    throw e;
  }
};
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const short = (v) => {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s == null ? "" : s.length > 90 ? s.slice(0, 87) + "..." : s;
};
const cssClass = (s) => String(s || "unknown").toLowerCase().replace(/[^a-z0-9_]+/g, "_").replace(/^_|_$/g, "") || "unknown";
const ms = (t0) => Math.round(performance.now() - t0);

export function mountFishViewer(host, opts = {}) {
  const base = new URL(opts.base || "artifacts/fish3d/fish3d-N1-cypselurus-baseline/", document.baseURI).href;
  const lazy = opts.lazy !== false;
  const variants = (opts.variants && opts.variants.length ? opts.variants : [{ id: "default", glb: "fish.glb" }])
    .map((v) => ({ appearance: null, poster: "render/poster.png", video: "render/turntable.mp4", ...v }));
  const S = { mode: "pending", reason: null, selected: null, variant: variants[0].id, glbSha256: null,
              hashChecked: null, hashSource: null, dims: null, names: [], visible: {}, materials: null,
              perf: {}, noProvenance: [] };
  let three, scene, camera, renderer, controls, root, raycaster, dirty = true, raf = 0, ro, io, disposed = false;
  let nodes = {}, comps = {}, home = null;
  let ctx = { render: null, candidate: null, build: null, appearance: null };

  host.textContent = "";
  host.classList.add("mv");
  if (opts.layout === "hero") host.classList.add("mv-hero");
  const badges = el("ul", "mv-badges");
  const glbBadge = el("li", "mv-badge actual", "ACTUAL MESH, not the schematic canvas");
  badges.append(glbBadge);
  [["engineering candidate, not a validated organism", "warn"],
   ["modelled geometry: check each parameter's status (sourced / fitted / digitized / derived / assumed)", "warn"]]
    .forEach(([t, c]) => badges.append(el("li", "mv-badge " + c, t)));
  const grid = el("div", "mv-grid");
  const stage = el("div", "mv-stage");
  stage.dataset.mode = "pending";
  const poster = el("img");
  poster.alt = "Static render of the fish3d candidate mesh (not interactive)";
  const video = el("video");
  video.muted = true; video.loop = true; video.playsInline = true; video.preload = "none";
  video.setAttribute("aria-label", "Turntable of the fish3d candidate mesh (static render, not interactive)");
  video.hidden = true;
  const cap = el("div", "mv-cap", "Static render of the same mesh; not interactive.");
  stage.append(poster, video, cap);
  const side = el("div");
  const bar = el("div", "mv-bar");
  const btnReset = el("button", null, "Reset view"); btnReset.type = "button"; btnReset.disabled = true;
  const btnVideo = el("button", null, "Play turntable video"); btnVideo.type = "button";
  const btnAll = el("button", null, "Show all components"); btnAll.type = "button"; btnAll.disabled = true;
  bar.append(btnReset, btnAll, btnVideo);
  const vbar = el("div", "mv-bar mv-variants");
  vbar.setAttribute("role", "group"); vbar.setAttribute("aria-label", "Appearance variant");
  vbar.hidden = variants.length < 2;
  const status = el("p", "mv-status", "Interactive viewer loads when scrolled into view.");
  status.setAttribute("role", "status");
  const appear = el("div", "mv-appearance");
  const list = el("ul", "mv-list"); list.setAttribute("aria-label", "Mesh components");
  const detail = el("div", "mv-detail"); detail.setAttribute("aria-live", "polite");
  const notClaimed = el("p", "mv-not");
  side.append(status, bar, vbar, appear, list, detail, notClaimed);
  grid.append(stage, side);
  host.append(badges, grid);

  const emit = (name, d) => host.dispatchEvent(new CustomEvent("mv:" + name, { detail: d, bubbles: true }));
  const variantOf = (id) => variants.find((v) => v.id === id) || variants[0];
  const setPoster = (v) => { poster.src = base + v.poster; video.removeAttribute("src"); };
  setPoster(variants[0]);

  btnVideo.onclick = () => {
    if (S.mode === "interactive") return;
    const v = variantOf(S.variant);
    if (video.hidden) {
      if (!video.src) video.src = base + v.video;
      video.hidden = false; poster.hidden = true; video.play().catch(() => {});
      btnVideo.textContent = "Show still";
    } else {
      video.pause(); video.hidden = true; poster.hidden = false; btnVideo.textContent = "Play turntable video";
    }
  };
  btnVideo.hidden = !variants[0].video;

  function fallback(reason) {
    S.mode = "fallback"; S.reason = String(reason); stage.dataset.mode = "fallback";
    if (renderer) { cancelAnimationFrame(raf); renderer.dispose(); renderer.domElement.remove(); renderer = null; }
    poster.hidden = false; cap.hidden = false;
    status.dataset.state = "fallback";
    status.textContent = `Interactive viewer unavailable (${S.reason}). Showing the static render of the same mesh.`;
    btnReset.disabled = btnAll.disabled = true;
    emit("fallback", { reason: S.reason });
  }

  function webglOk() {
    try {
      const c = document.createElement("canvas");
      return !!(c.getContext("webgl2") || c.getContext("webgl"));
    } catch { return false; }
  }

  const draw = () => { dirty = true; };
  function loop() {
    if (disposed || !renderer) return;
    raf = requestAnimationFrame(loop);
    if (controls && controls.update()) dirty = true;      // damping keeps orbit smooth after release
    if (!dirty) return;
    dirty = false;
    renderer.render(scene, camera);
    if (S.perf.first_frame_ms == null && S.perf._t0 != null) { S.perf.first_frame_ms = ms(S.perf._t0); }
  }

  function frameHome() {
    const T = three, box = new T.Box3().setFromObject(root);
    const c = box.getCenter(new T.Vector3()), size = box.getSize(new T.Vector3());
    S.dims = { x_m: size.x, y_m: size.y, z_m: size.z, min_m: box.min.toArray(), max_m: box.max.toArray(),
               frame: "glTF: x snout->tail, y up (dorsal), z = -left; metres" };
    const r = size.length() / 2, d = r / Math.tan((camera.fov * Math.PI) / 360) * 0.6;
    const az = (-48 * Math.PI) / 180, el_ = (24 * Math.PI) / 180;
    home = { target: c.clone(),
             pos: new T.Vector3(c.x + d * Math.cos(el_) * Math.sin(az), c.y + d * Math.sin(el_), c.z + d * Math.cos(el_) * Math.cos(az)) };
    controls.minDistance = r * 0.35; controls.maxDistance = r * 12;
    camera.near = r / 100; camera.far = r * 40; camera.updateProjectionMatrix();
  }
  function reset() {
    if (!home) return;
    camera.position.copy(home.pos); controls.target.copy(home.target); controls.update(); draw();
  }

  function resize() {
    if (!renderer) return;
    const w = Math.max(1, stage.clientWidth), h = Math.max(1, stage.clientHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); draw();
  }

  const meshesOf = (n) => (nodes[n] ? nodes[n].meshes : []);
  function setEmissive(n, on) {
    meshesOf(n).forEach((m) => {
      if (!m.material || !m.material.emissive) return;
      m.material.emissive.setHex(on ? 0x0e7c86 : m.userData.mvEmissive ?? 0x000000);
      m.material.emissiveIntensity = on ? 0.55 : m.userData.mvEmissiveI ?? 1;
    });
  }
  function select(name) {
    if (name && !nodes[name]) return false;
    if (S.selected && nodes[S.selected]) setEmissive(S.selected, false);
    S.selected = name || null;
    if (S.selected) setEmissive(name, true);
    [...list.children].forEach((li) => (li.getAttribute("aria-current") === "true") && li.removeAttribute("aria-current"));
    const li = name && [...list.children].find((x) => x.dataset.comp === name);
    if (li) li.setAttribute("aria-current", "true");
    showDetail(name);
    draw(); emit("select", { name: S.selected });
    return true;
  }

  function showDetail(name) {
    detail.textContent = "";
    if (!name) { detail.append(el("p", "faint", "Click a part of the mesh or a list entry to see its provenance.")); return; }
    const c = comps[name];
    detail.append(el("h4", null, `${name}  (GLB node "${name}")`));
    if (!c) {
      detail.append(el("p", null, "No provenance record for this node in components.json. Nothing is claimed about how it was made."));
      return;
    }
    if (nodes[name] && nodes[name].extras) detail.append(el("p", "mono", `GLB node extras: ${nodes[name].extras.provenance} (candidate ${String(nodes[name].extras.candidate_sha256 || "").slice(0, 12)})`));
    const chk = c.check || {};
    detail.append(el("p", null, `Triangles ${chk.triangles ?? nodes[name].triangles}; closed 2-manifold ${chk.closed_two_manifold ?? "?"}; ` +
      `volume ${chk.volume_mm3 != null ? chk.volume_mm3.toFixed(1) + " mm³" : "?"}. See the parameter statuses for what is sourced, fitted, digitized, derived or assumed.`));
    if (c.stl) {
      const a = el("a", null, `Download exact component mesh (${c.stl})`);
      a.href = base + c.stl; a.download = name + ".stl";
      detail.append(el("p", null), a);
      detail.append(el("p", "mono", `sha256 ${c.stl_sha256 || "?"}`));
    }
    const t = el("table"), hd = el("tr");
    ["parameter", "status", "value / note"].forEach((h) => hd.append(el("th", null, h)));
    t.append(hd);
    Object.entries(c.params || {}).forEach(([k, p]) => {
      const obj = p && typeof p === "object" && !Array.isArray(p) ? p : { value: p };
      const tr = el("tr"), st = el("span", "mv-st " + cssClass(obj.status), obj.status || "unknown");
      const tdS = el("td"); tdS.append(st);
      tr.append(el("td", null, k), tdS, el("td", null, short(obj.value) + (obj.note ? " — " + obj.note : "") + (obj.locator ? " [" + obj.locator + "]" : "") + (obj.source ? " [" + obj.source + "]" : "")));
      t.append(tr);
    });
    detail.append(t);
  }

  function showAppearance(v, a) {
    appear.textContent = "";
    if (!a) return;
    const box = el("div", "mv-appear");
    box.append(el("h4", null, "Appearance (not biology): " + (a.title || v.id)));
    if (a.label) box.append(el("p", null, a.label));
    const ul = el("ul");
    (a.elements || []).forEach((e) => {
      const li = el("li"), st = el("span", "mv-st " + cssClass((e.status || "").split(/[ (]/)[0]), e.status || "unknown");
      li.append(st, document.createTextNode(" " + (e.element || "") + (e.source ? " [" + e.source + "]" : "")));
      ul.append(li);
    });
    const dt = el("details"), sm = el("summary", null, `Source and status of each appearance element (${(a.elements || []).length})`);
    dt.append(sm, ul); box.append(dt);
    appear.append(box);
  }

  function buildList() {
    list.textContent = "";
    S.names.forEach((n) => {
      const li = el("li"); li.dataset.comp = n;
      const lab = el("label"), cb = el("input"); cb.type = "checkbox"; cb.checked = true;
      cb.setAttribute("aria-label", "Show " + n);
      cb.onchange = () => setVisible(n, cb.checked);
      lab.append(cb, el("span", null, "show"));
      const b = el("button", "mv-name", n + (comps[n] ? "" : " (no record)")); b.type = "button";
      b.onclick = () => select(S.selected === n ? null : n);
      li.append(lab, b); list.append(li);
    });
  }
  function setVisible(n, v) {
    if (!nodes[n]) return false;
    nodes[n].group.visible = !!v; S.visible[n] = !!v;
    const li = [...list.children].find((x) => x.dataset.comp === n);
    const cb = li && li.querySelector("input"); if (cb) cb.checked = !!v;
    if (!v && S.selected === n) select(null);
    draw(); return true;
  }

  // Picking. three's Raycaster tests every triangle of a mesh whose bounding box the ray crosses; the
  // scales mesh has ~230k triangles, so a click cost 200-330 ms (measured, software GL). For heavy meshes
  // keep one axis-aligned box per triangle and run a cheap slab test first, then the exact triangle test
  // on the few survivors. Same hit as the Raycaster (checked in tests), a fraction of the time.
  const HEAVY_TRIS = 20000;
  function triBounds(mesh) {
    const g = mesh.geometry, pos = g.attributes.position, idx = g.index, n = (idx ? idx.count : pos.count) / 3;
    const bb = new Float32Array(n * 6), at = (i) => (idx ? idx.getX(i) : i);
    for (let t = 0; t < n; t++) {
      const a = at(3 * t), b = at(3 * t + 1), c = at(3 * t + 2);
      for (let k = 0; k < 3; k++) {
        const x = pos.getComponent(a, k), y = pos.getComponent(b, k), z = pos.getComponent(c, k);
        bb[t * 6 + k] = Math.min(x, y, z); bb[t * 6 + 3 + k] = Math.max(x, y, z);
      }
    }
    return bb;
  }
  function pickMesh(mesh, ray) {            // nearest hit {distance} in world units, or null
    const T = three, g = mesh.geometry;
    if (!(g.index ? g.index.count : g.attributes.position.count) / 3 > HEAVY_TRIS) {
      const h = new T.Raycaster(ray.origin, ray.direction).intersectObject(mesh, false)[0];
      return h ? { distance: h.distance } : null;
    }
    mesh.updateWorldMatrix(true, false);
    const inv = mesh.matrixWorld.clone().invert(), lr = ray.clone().applyMatrix4(inv);
    const bb = mesh.userData.mvTriBounds || (mesh.userData.mvTriBounds = triBounds(mesh));
    const o = lr.origin, d = lr.direction, n = bb.length / 6;
    const ix = [d.x ? 1 / d.x : Infinity, d.y ? 1 / d.y : Infinity, d.z ? 1 / d.z : Infinity], oo = [o.x, o.y, o.z];
    const pos = g.attributes.position, idx = g.index, at = (i) => (idx ? idx.getX(i) : i);
    const A = new T.Vector3(), B = new T.Vector3(), C = new T.Vector3(), hit = new T.Vector3();
    let best = Infinity;
    for (let t = 0; t < n; t++) {
      let t0 = 0, t1 = Infinity;
      for (let k = 0; k < 3; k++) {
        const lo = (bb[t * 6 + k] - oo[k]) * ix[k], hi = (bb[t * 6 + 3 + k] - oo[k]) * ix[k];
        t0 = Math.max(t0, Math.min(lo, hi)); t1 = Math.min(t1, Math.max(lo, hi));
        if (t0 > t1) break;
      }
      if (t0 > t1 || t1 < 0) continue;
      A.fromBufferAttribute(pos, at(3 * t)); B.fromBufferAttribute(pos, at(3 * t + 1)); C.fromBufferAttribute(pos, at(3 * t + 2));
      if (lr.intersectTriangle(A, B, C, false, hit)) {
        const dist = hit.sub(o).length();            // local distance; the ray was transformed, not renormalised
        const wd = dist * (ray.direction.length() / d.length() || 1);
        if (wd < best) best = wd;
      }
    }
    return best < Infinity ? { distance: best * 1 } : null;
  }
  function cpuPick(meshes) {
    const ray = raycaster.ray;
    let best = null;
    meshes.forEach((m) => { const h = pickMesh(m, ray); if (h && (!best || h.distance < best.distance)) best = { ...h, name: m.userData.mvName }; });
    return best ? best.name : null;
  }

  function wireInput(canvas) {
    let down = null;
    canvas.tabIndex = 0;
    canvas.setAttribute("role", "img");
    canvas.setAttribute("aria-label", "Interactive 3D fish mesh. Arrow keys rotate, plus and minus zoom, 0 resets. Use the component list to inspect parts.");
    controls.addEventListener("change", draw);
    canvas.addEventListener("pointerdown", (e) => { down = [e.clientX, e.clientY]; });
    canvas.addEventListener("pointerup", (e) => {
      if (!down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4) { down = null; return; }
      down = null;
      const t0 = performance.now(), r = canvas.getBoundingClientRect(), T = three;
      raycaster.setFromCamera(new T.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
      const pickable = S.names.filter((n) => nodes[n].group.visible).flatMap(meshesOf);
      const name = cpuPick(pickable); S.perf.pick_method = "cpu-triangle-bounds";
      S.perf.last_pick_ms = ms(t0);
      select(name);
    });
    canvas.addEventListener("keydown", (e) => {
      const T = three, off = camera.position.clone().sub(controls.target), up = new T.Vector3(0, 1, 0), st = Math.PI / 18;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") off.applyAxisAngle(up, e.key === "ArrowLeft" ? st : -st);
      else if (e.key === "ArrowUp" || e.key === "ArrowDown") {
        const ax = new T.Vector3().crossVectors(up, off).normalize();
        const next = off.clone().applyAxisAngle(ax, e.key === "ArrowUp" ? -st : st);
        if (Math.abs(next.clone().normalize().y) < 0.98) off.copy(next);
      } else if (e.key === "+" || e.key === "=") off.multiplyScalar(0.85);
      else if (e.key === "-" || e.key === "_") off.multiplyScalar(1 / 0.85);
      else if (e.key === "0" || e.key === "Home") { reset(); e.preventDefault(); return; }
      else return;
      e.preventDefault();
      off.setLength(Math.min(controls.maxDistance, Math.max(controls.minDistance, off.length())));
      camera.position.copy(controls.target).add(off); controls.update(); draw();
    });
    canvas.addEventListener("webglcontextlost", (e) => { e.preventDefault(); fallback("WebGL context lost"); });
  }

  // expected sha256 of this variant's GLB, and where it was recorded
  function expectedHash(v) {
    if (v.expectedSha256) return [v.expectedSha256, "variant option"];
    if (ctx.appearance && ctx.appearance.glb_sha256 && (!ctx.appearance.glb || ctx.appearance.glb === v.glb))
      return [ctx.appearance.glb_sha256, v.appearance];
    if (ctx.render && ctx.render.glb_sha256 && (!ctx.render.glb || ctx.render.glb === v.glb)) return [ctx.render.glb_sha256, "render/render.json"];
    const bf = ctx.build && ctx.build.files && ctx.build.files[v.glb];
    return bf ? [bf, "build.json"] : [null, null];
  }

  function disposeRoot() {
    if (!root) return;
    scene.remove(root);
    root.traverse((o) => {
      if (!o.isMesh) return;
      o.geometry.dispose();
      [].concat(o.material).forEach((m) => m && m.dispose && m.dispose());
    });
    root = null; nodes = {};
  }

  // Build components from the GLB's own nodes; keep source materials.
  function adopt(gltf, T) {
    const counts = { glb_material: 0, vertex_colors: 0, flat_default: 0 };
    nodes = {};
    // component = nearest ancestor-or-self that has a components.json record, else the glTF node that owns the
    // mesh (so a wrapper/root node never swallows the parts, and several primitives of one node stay together)
    const json = gltf.parser.json;
    const ownsMesh = (a) => { const as = gltf.parser.associations.get(a); return !!(as && as.nodes !== undefined && json.nodes[as.nodes].mesh !== undefined); };
    const key = (a) => (a.userData && a.userData.component_id) || a.name;   // node extras may name the component
    const owner = (o) => {
      const chain = []; for (let a = o; a && a !== gltf.scene; a = a.parent) chain.push(a);
      return chain.find((a) => key(a) && comps[key(a)]) || chain.find(ownsMesh) || o;
    };
    gltf.scene.traverse((o) => {
      if (!o.isMesh) return;
      const own = owner(o), name = key(own) || o.name || `node_${own.id}`;
      o.userData.mvName = name;
      const g = o.geometry;
      if (!g.attributes.normal) g.computeVertexNormals();   // POSITION-only GLBs render black without normals
      const hasColors = !!g.attributes.color;
      const srcMat = [].concat(o.material)[0];
      const assoc = gltf.parser.associations.get(o), prim = assoc && gltf.parser.json.meshes[assoc.meshes].primitives[assoc.primitives || 0];
      const hasMat = !!(prim && prim.material !== undefined);   // a material the GLB itself declares
      let m;
      if (hasColors || hasMat) {
        m = srcMat.clone();                                 // keep the source's colours, maps, alpha, metalness
        if (hasColors) { m.vertexColors = true; counts.vertex_colors++; }
        if (hasMat) counts.glb_material++;
        o.userData.mvKind = [hasMat && "glb_material", hasColors && "vertex_colors"].filter(Boolean).join("+");
        if (!hasMat) m.side = T.DoubleSide;                 // no declared material: thin plates are seen from both sides; a declared one keeps its own `side`
      } else {
        m = new T.MeshStandardMaterial({ color: lookOf(name), roughness: 0.55, metalness: 0.05, side: T.DoubleSide });
        counts.flat_default++; o.userData.mvKind = "flat_default";
      }
      if (m.emissive) { o.userData.mvEmissive = m.emissive.getHex(); o.userData.mvEmissiveI = m.emissiveIntensity; }
      o.material = m;
      const n = nodes[name] || (nodes[name] = { group: own, meshes: [], triangles: 0, extras: own.userData && own.userData.provenance ? own.userData : null });
      n.meshes.push(o);
      n.triangles += (g.index ? g.index.count : g.attributes.position.count) / 3;
    });
    S.materials = { ...counts,
      source: counts.flat_default && !counts.vertex_colors && !counts.glb_material ? "none in GLB: flat appearance-only colours"
        : counts.flat_default ? "mixed: GLB colours kept where present, flat colours elsewhere"
        : counts.vertex_colors && counts.glb_material ? "GLB materials with vertex colours (COLOR_0)"
        : counts.vertex_colors ? "GLB vertex colours (COLOR_0)" : "GLB materials" };
    S.names = Object.keys(nodes);
    S.noProvenance = S.names.filter((n) => !comps[n]);
    S.visible = Object.fromEntries(S.names.map((n) => [n, true]));
  }

  async function loadVariant(v, T, GLTFLoader) {
    const t0 = performance.now(); S.perf = { _t0: t0 };
    S.variant = v.id; S.hashChecked = null; S.hashSource = null;
    ctx.appearance = v.appearance ? await fetchJson(base + v.appearance, true) : null;
    const glbBuf = await fetch(base + v.glb).then((r) => { if (!r.ok) throw new Error(`${v.glb}: HTTP ${r.status}`); return r.arrayBuffer(); });
    S.perf.fetch_ms = ms(t0);
    const [want, src] = expectedHash(v);
    S.glbSha256 = null;
    if (globalThis.crypto && crypto.subtle) {
      const t1 = performance.now();
      S.glbSha256 = hex(await crypto.subtle.digest("SHA-256", glbBuf));
      S.perf.hash_ms = ms(t1);
      if (want) {
        S.hashChecked = S.glbSha256 === want; S.hashSource = src;
        if (!S.hashChecked) throw new Error(`${v.glb} sha256 ${S.glbSha256.slice(0, 12)} does not match ${src} (${String(want).slice(0, 12)})`);
      } else S.hashChecked = null;
    }
    const t2 = performance.now();
    const gltf = await new Promise((ok, no) => new GLTFLoader().parse(glbBuf, "", ok, no));
    S.perf.parse_ms = ms(t2);
    if (disposed) return null;
    return { gltf, bytes: glbBuf.byteLength, t0 };
  }

  function present(v, got, T) {
    const t3 = performance.now();
    const had = !!root;
    if (S.selected) select(null);
    disposeRoot();
    root = got.gltf.scene; scene.add(root);
    adopt(got.gltf, T);
    S.perf.build_ms = ms(t3);
    const prev = S.dims;
    frameHome();
    const refit = !had || !prev || Math.abs(prev.x_m - S.dims.x_m) > 1e-9 || Math.abs(prev.y_m - S.dims.y_m) > 1e-9;
    if (refit) reset();
    buildList(); showDetail(null); showAppearance(v, ctx.appearance);
    glbBadge.textContent = `ACTUAL MESH (${v.glb}), not the schematic canvas`;
    const d = S.dims;
    status.dataset.state = "interactive";
    status.textContent = `Interactive: actual ${v.glb}, ${(got.bytes / 1e6).toFixed(2)} MB, ` +
      `${(d.x_m * 1000).toFixed(1)} × ${(d.y_m * 1000).toFixed(1)} × ${(d.z_m * 1000).toFixed(1)} mm (length × height × width). ` +
      (S.hashChecked ? `sha256 matches ${S.hashSource}. ` : S.glbSha256 ? "sha256 hash not recorded, so not verified. " : "sha256 not checked (insecure context). ") +
      `Colours: ${S.materials.source}. ` + (S.noProvenance.length ? `${S.noProvenance.length} node(s) have no provenance record. ` : "") +
      "Drag to orbit, scroll to zoom.";
    S.perf.total_ms = ms(got.t0);
    dirty = true;
    // build the per-triangle bounds now (idle), so the first click is as fast as the rest
    const heavy = S.names.flatMap(meshesOf).filter((m) => (m.geometry.index ? m.geometry.index.count : m.geometry.attributes.position.count) / 3 > HEAVY_TRIS);
    const warm = (i) => { if (disposed || i >= heavy.length) return; const m = heavy[i]; if (m.geometry) m.userData.mvTriBounds = m.userData.mvTriBounds || triBounds(m); setTimeout(() => warm(i + 1), 0); };
    setTimeout(() => warm(0), 0);
  }

  function renderVariantButtons() {
    vbar.textContent = "";
    variants.forEach((v) => {
      const b = el("button", null, v.label || v.id); b.type = "button"; b.dataset.variant = v.id;
      b.setAttribute("aria-pressed", String(v.id === S.variant));
      b.onclick = () => setVariant(v.id);
      vbar.append(b);
    });
  }

  let libs = null;
  async function setVariant(id) {
    const v = variants.find((x) => x.id === id);
    if (!v || !libs || S.mode === "fallback") return false;
    if (v.id === S.variant && root) return true;
    try {
      const got = await loadVariant(v, libs.T, libs.GLTFLoader);
      if (!got) return false;
      setPoster(v); present(v, got, libs.T); renderVariantButtons();
      emit("variant", { id: v.id, glb: v.glb, sha256: S.glbSha256 });
      return true;
    } catch (err) { fallback(err && err.message ? err.message : err); return false; }
  }

  async function load() {
    try {
      if (!webglOk()) return fallback("WebGL is not available in this browser");
      const [T, { GLTFLoader }, { OrbitControls }] = await Promise.all([import(THREE_URL), import(GLTF_URL), import(ORBIT_URL)]);
      three = T; libs = { T, GLTFLoader };
      const v = variants[0];
      const [cj, rj, cand, bj] = await Promise.all([
        fetchJson(base + "components.json", true), fetchJson(base + "render/render.json", true),
        fetchJson(base + "candidate.json", true), fetchJson(base + "build.json", true)]);
      comps = (cj && cj.components) || {};
      ctx = { ...ctx, render: rj, candidate: cand, build: bj };
      const got = await loadVariant(v, T, GLTFLoader);
      if (!got) return;
      const nc = (rj && rj.not_claimed) || [];
      const lab = (cand && cand.label) || "";
      notClaimed.textContent = (lab ? lab + " " : "") + (nc.length ? "Not claimed by this artifact: " + nc.join("; ") + "." : "");
      renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setClearColor(0x000000, 0);
      const canvas = renderer.domElement;
      stage.insertBefore(canvas, poster);
      scene = new T.Scene();
      camera = new T.PerspectiveCamera(30, 16 / 10, 0.001, 10);
      scene.add(new T.HemisphereLight(0xffffff, 0x6b7a88, 1.1));
      const key = new T.DirectionalLight(0xffffff, 2.2); key.position.set(0.5, 1, 0.6); scene.add(key);
      const fill = new T.DirectionalLight(0xbcd2e4, 0.8); fill.position.set(-0.6, 0.2, -0.8); scene.add(fill);
      controls = new OrbitControls(camera, canvas);
      controls.enableDamping = true; controls.dampingFactor = 0.12; controls.screenSpacePanning = true;
      raycaster = new T.Raycaster();
      present(v, got, T);
      resize(); wireInput(canvas);
      ro = new ResizeObserver(resize); ro.observe(stage);
      btnReset.onclick = reset; btnReset.disabled = false;
      btnAll.onclick = () => S.names.forEach((n) => setVisible(n, true)); btnAll.disabled = false;
      btnVideo.hidden = true; poster.hidden = true; video.hidden = true; cap.hidden = true;
      S.mode = "interactive"; stage.dataset.mode = "interactive";
      renderVariantButtons();
      loop(); emit("ready", { mode: S.mode, dims: S.dims });
    } catch (err) {
      fallback(err && err.message ? err.message : err);
    }
  }

  const ready = new Promise((res) => {
    const start = () => load().then(res, res);
    if (!lazy || !("IntersectionObserver" in window)) start();
    else {
      io = new IntersectionObserver((es) => { if (es.some((e) => e.isIntersecting)) { io.disconnect(); start(); } }, { rootMargin: "200px" });
      io.observe(host);
    }
  });
  const api = {
    ready, state: () => ({ ...S, names: [...S.names], visible: { ...S.visible }, perf: { ...S.perf, _t0: undefined } }),
    dimensions: () => S.dims,
    // x extent (m) of one named component, measured from the loaded geometry
    bodyExtentX: (n = "body") => { if (!nodes[n]) return null; const b = new three.Box3().setFromObject(nodes[n].group); return b.max.x - b.min.x; },
    // per-component facts read from the loaded scene (triangles, the materials actually in use)
    componentInfo: (n) => nodes[n] && { triangles: nodes[n].triangles, record: !!comps[n],
      materials: nodes[n].meshes.map((m) => ({ kind: m.userData.mvKind, color: "#" + (m.material.color ? m.material.color.getHexString() : "none"),
        vertexColors: !!m.material.vertexColors, transparent: !!m.material.transparent, opacity: m.material.opacity,
        alphaTest: m.material.alphaTest, hasMap: !!m.material.map })) },
    // diagnostic: the fast pick and three's Raycaster at one NDC point, as component names (they must agree)
    _pickCompare: (nx, ny) => { const T = three; raycaster.setFromCamera(new T.Vector2(nx, ny), camera);
      const ms_ = S.names.filter((n) => nodes[n].group.visible).flatMap(meshesOf);
      const h = raycaster.intersectObjects(ms_, false)[0];
      return [cpuPick(ms_), h ? h.object.userData.mvName : null]; },
    componentNames: () => [...S.names], variantIds: () => variants.map((v) => v.id),
    appearance: () => ctx.appearance, setVariant, select, setVisible, reset,
    destroy() {
      disposed = true; cancelAnimationFrame(raf); io && io.disconnect(); ro && ro.disconnect();
      disposeRoot();
      if (renderer) { renderer.dispose(); renderer.domElement.remove(); }
      host.textContent = ""; host.classList.remove("mv", "mv-hero");
    },
  };
  return api;
}
