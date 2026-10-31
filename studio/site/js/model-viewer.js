// Reusable lazy-loaded viewer for the ACTUAL fish3d GLB (not the schematic canvas in fish.js).
//
//   import { mountFishViewer } from "./model-viewer.js";
//   const v = mountFishViewer(el, { base: "artifacts/fish3d/fish3d-N1-cypselurus-baseline/", layout: "hero" });
//   await v.ready;            // resolves once interactive OR once the static fallback is showing
//
// Loads <base>fish.glb (metres), components.json (per-component provenance), render/render.json
// (hash + not_claimed) and shows render/poster.png + render/turntable.mp4 whenever WebGL, the
// fetch or the hash check fails.  three.js 0.170.0 is vendored (site/vendor/three/VENDOR.json).
// All text from the data files is inserted with textContent.

const THREE_URL = new URL("../vendor/three/lib/three.module.js", import.meta.url).href;
const GLTF_URL = new URL("../vendor/three/examples/jsm/loaders/GLTFLoader.js", import.meta.url).href;
const ORBIT_URL = new URL("../vendor/three/examples/jsm/controls/OrbitControls.js", import.meta.url).href;

// Appearance only: the GLB carries no materials. Colours say nothing about real pigmentation.
const LOOK = { body: 0x9fb4c4, scales: 0xb9c6d0, eye: 0x1c2630, operculum: 0xa9bccb, fin: 0xcfd9e0 };
const lookOf = (n) => (n === "body" ? LOOK.body : n === "scales" ? LOOK.scales : n.startsWith("eye") ? LOOK.eye
  : n.startsWith("operculum") ? LOOK.operculum : LOOK.fin);

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};
const j = async (url) => {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
  return r.json();
};
const hex = (buf) => [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, "0")).join("");
const short = (v) => {
  const s = typeof v === "string" ? v : JSON.stringify(v);
  return s.length > 90 ? s.slice(0, 87) + "..." : s;
};

export function mountFishViewer(host, opts = {}) {
  const base = new URL(opts.base || "artifacts/fish3d/fish3d-N1-cypselurus-baseline/", document.baseURI).href;
  const lazy = opts.lazy !== false;
  const S = { mode: "pending", reason: null, selected: null, glbSha256: null, hashChecked: null,
              dims: null, names: [], visible: {} };
  let three, scene, camera, renderer, controls, root, raycaster, dirty = true, raf = 0, ro, io, disposed = false;
  const nodes = {};
  let comps = {}, home = null;

  host.textContent = "";
  host.classList.add("mv");
  if (opts.layout === "hero") host.classList.add("mv-hero");
  const badges = el("ul", "mv-badges");
  [["ACTUAL MESH (fish.glb), not the schematic canvas", "actual"],
   ["engineering candidate, not a validated organism", "warn"],
   ["derived and assumed geometry: flat fins, lattice scales, decorative eyes", "warn"]]
    .forEach(([t, c]) => badges.append(el("li", "mv-badge " + c, t)));
  const grid = el("div", "mv-grid");
  const stage = el("div", "mv-stage");
  stage.dataset.mode = "pending";
  const poster = el("img");
  poster.alt = "Static path-traced render of the fish3d candidate mesh (not interactive)";
  poster.src = base + "render/poster.png";
  const video = el("video");
  video.muted = true; video.loop = true; video.playsInline = true; video.preload = "none";
  video.setAttribute("aria-label", "Turntable of the fish3d candidate mesh (static render, not interactive)");
  video.hidden = true;
  const cap = el("div", "mv-cap", "Static render of the same mesh (Blender Cycles); not interactive.");
  stage.append(poster, video, cap);
  const side = el("div");
  const bar = el("div", "mv-bar");
  const btnReset = el("button", null, "Reset view"); btnReset.type = "button"; btnReset.disabled = true;
  const btnVideo = el("button", null, "Play turntable video"); btnVideo.type = "button";
  const btnAll = el("button", null, "Show all components"); btnAll.type = "button"; btnAll.disabled = true;
  bar.append(btnReset, btnAll, btnVideo);
  const status = el("p", "mv-status", "Interactive viewer loads when scrolled into view.");
  status.setAttribute("role", "status");
  const list = el("ul", "mv-list"); list.setAttribute("aria-label", "Mesh components");
  const detail = el("div", "mv-detail"); detail.setAttribute("aria-live", "polite");
  const notClaimed = el("p", "mv-not");
  side.append(status, bar, list, detail, notClaimed);
  grid.append(stage, side);
  host.append(badges, grid);

  const emit = (name, d) => host.dispatchEvent(new CustomEvent("mv:" + name, { detail: d, bubbles: true }));

  btnVideo.onclick = () => {
    if (S.mode === "interactive") return;
    if (video.hidden) {
      if (!video.src) video.src = base + "render/turntable.mp4";
      video.hidden = false; poster.hidden = true; video.play().catch(() => {});
      btnVideo.textContent = "Show still";
    } else {
      video.pause(); video.hidden = true; poster.hidden = false; btnVideo.textContent = "Play turntable video";
    }
  };

  function fallback(reason) {
    S.mode = "fallback"; S.reason = String(reason); stage.dataset.mode = "fallback";
    if (renderer) { cancelAnimationFrame(raf); renderer.dispose(); renderer.domElement.remove(); renderer = null; }
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
    if (!dirty) return;
    dirty = false;
    renderer.render(scene, camera);
  }

  function frameHome() {
    const T = three, box = new T.Box3().setFromObject(root);
    const c = box.getCenter(new T.Vector3()), size = box.getSize(new T.Vector3());
    S.dims = { x_m: size.x, y_m: size.y, z_m: size.z, min_m: box.min.toArray(), max_m: box.max.toArray(),
               frame: "glTF: x snout->tail, y up (dorsal), z = -left; metres" };
    const r = size.length() / 2, d = r / Math.tan((camera.fov * Math.PI) / 360) * 0.72;
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

  function select(name) {
    if (name && !nodes[name]) return false;
    const T = three;
    if (S.selected && nodes[S.selected]) nodes[S.selected].material.emissive.setHex(0x000000);
    S.selected = name || null;
    if (S.selected) { nodes[name].material.emissive.setHex(0x0e7c86); nodes[name].material.emissiveIntensity = 0.55; }
    [...list.children].forEach((li) => (li.getAttribute("aria-current") === "true") && li.removeAttribute("aria-current"));
    const li = list.querySelector(`[data-comp="${name}"]`);
    if (li) li.setAttribute("aria-current", "true");
    showDetail(name);
    draw(); emit("select", { name: S.selected });
    return !!T;
  }

  function showDetail(name) {
    detail.textContent = "";
    if (!name) { detail.append(el("p", "faint", "Click a part of the mesh or a list entry to see its provenance.")); return; }
    const c = comps[name] || {};
    detail.append(el("h4", null, `${name}  (GLB node "${name}")`));
    const chk = c.check || {};
    detail.append(el("p", null, `Triangles ${chk.triangles ?? "?"}; closed 2-manifold ${chk.closed_two_manifold ?? "?"}; ` +
      `volume ${chk.volume_mm3 != null ? chk.volume_mm3.toFixed(1) + " mm³" : "?"}. Geometry is derived or assumed (see parameter statuses), not scanned.`));
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
      const tr = el("tr"), st = el("span", "mv-st " + (p.status || "unknown"), p.status || "unknown");
      const tdS = el("td"); tdS.append(st);
      tr.append(el("td", null, k), tdS, el("td", null, short(p.value) + (p.note ? " — " + p.note : "") + (p.locator ? " [" + p.locator + "]" : "")));
      t.append(tr);
    });
    detail.append(t);
  }

  function buildList() {
    S.names.forEach((n) => {
      const li = el("li"); li.dataset.comp = n;
      const lab = el("label"), cb = el("input"); cb.type = "checkbox"; cb.checked = true;
      cb.setAttribute("aria-label", "Show " + n);
      cb.onchange = () => setVisible(n, cb.checked);
      lab.append(cb, el("span", null, "show"));
      const b = el("button", "mv-name", n); b.type = "button";
      b.onclick = () => select(S.selected === n ? null : n);
      li.append(lab, b); list.append(li);
    });
  }
  function setVisible(n, v) {
    if (!nodes[n]) return false;
    nodes[n].visible = !!v; S.visible[n] = !!v;
    const cb = list.querySelector(`[data-comp="${n}"] input`); if (cb) cb.checked = !!v;
    if (!v && S.selected === n) select(null);
    draw(); return true;
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
      const r = canvas.getBoundingClientRect(), T = three;
      raycaster.setFromCamera(new T.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
      const hit = raycaster.intersectObjects(S.names.map((n) => nodes[n]).filter((m) => m.visible), false)[0];
      select(hit ? hit.object.name : null);
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

  async function load() {
    try {
      if (!webglOk()) return fallback("WebGL is not available in this browser");
      const [T, { GLTFLoader }, { OrbitControls }] = await Promise.all([import(THREE_URL), import(GLTF_URL), import(ORBIT_URL)]);
      three = T;
      const [cj, rj, glbBuf] = await Promise.all([
        j(base + "components.json"), j(base + "render/render.json"),
        fetch(base + "fish.glb").then((r) => { if (!r.ok) throw new Error(`fish.glb: HTTP ${r.status}`); return r.arrayBuffer(); })]);
      comps = cj.components || {};
      S.glbSha256 = null;
      if (globalThis.crypto && crypto.subtle) {
        S.glbSha256 = hex(await crypto.subtle.digest("SHA-256", glbBuf));
        S.hashChecked = S.glbSha256 === rj.glb_sha256;
        if (!S.hashChecked) return fallback(`fish.glb sha256 ${S.glbSha256.slice(0, 12)} does not match render.json ${String(rj.glb_sha256).slice(0, 12)}`);
      } else S.hashChecked = null;
      (rj.not_claimed || []).length && (notClaimed.textContent = "Not claimed by this artifact: " + rj.not_claimed.join("; ") + ".");
      const gltf = await new Promise((ok, no) => new GLTFLoader().parse(glbBuf, "", ok, no));
      if (disposed) return;
      renderer = new T.WebGLRenderer({ antialias: true, alpha: true });
      renderer.setClearColor(0x000000, 0);
      const canvas = renderer.domElement;
      stage.insertBefore(canvas, poster);
      scene = new T.Scene();
      camera = new T.PerspectiveCamera(30, 16 / 10, 0.001, 10);
      scene.add(new T.HemisphereLight(0xffffff, 0x6b7a88, 1.1));
      const key = new T.DirectionalLight(0xffffff, 2.2); key.position.set(0.5, 1, 0.6); scene.add(key);
      const fill = new T.DirectionalLight(0xbcd2e4, 0.8); fill.position.set(-0.6, 0.2, -0.8); scene.add(fill);
      root = gltf.scene; scene.add(root);
      root.traverse((o) => {
        if (!o.isMesh) return;
        // the GLB carries POSITION only (no normals, no materials): without normals the lit material renders black
        if (!o.geometry.attributes.normal) o.geometry.computeVertexNormals();
        o.material = new T.MeshStandardMaterial({ color: lookOf(o.name), roughness: 0.55, metalness: 0.05,
                                                  side: T.DoubleSide, emissive: 0x000000 });
        nodes[o.name] = o;
      });
      S.names = Object.keys(nodes);
      S.names.forEach((n) => (S.visible[n] = true));
      controls = new OrbitControls(camera, canvas);
      controls.enableDamping = false; controls.screenSpacePanning = true;
      raycaster = new T.Raycaster();
      frameHome(); reset(); resize(); wireInput(canvas); buildList(); showDetail(null);
      ro = new ResizeObserver(resize); ro.observe(stage);
      btnReset.onclick = reset; btnReset.disabled = false;
      btnAll.onclick = () => S.names.forEach((n) => setVisible(n, true)); btnAll.disabled = false;
      btnVideo.hidden = true; poster.hidden = true; video.hidden = true; cap.hidden = true;
      S.mode = "interactive"; stage.dataset.mode = "interactive";
      status.dataset.state = "interactive";
      const d = S.dims;
      status.textContent = `Interactive: actual fish.glb, ${(glbBuf.byteLength / 1e6).toFixed(2)} MB, ` +
        `${(d.x_m * 1000).toFixed(1)} × ${(d.y_m * 1000).toFixed(1)} × ${(d.z_m * 1000).toFixed(1)} mm (length × height × width), ` +
        (S.hashChecked ? "sha256 matches render.json." : "sha256 not checked (insecure context).") +
        " Colours are appearance only. Drag to orbit, scroll to zoom.";
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
    ready, state: () => ({ ...S, names: [...S.names], visible: { ...S.visible } }),
    dimensions: () => S.dims,
    // x extent (m) of one named mesh, measured from the loaded geometry
    bodyExtentX: (n = "body") => { if (!nodes[n]) return null; const b = new three.Box3().setFromObject(nodes[n]); return b.max.x - b.min.x; },
    componentNames: () => [...S.names],
    select, setVisible, reset,
    destroy() {
      disposed = true; cancelAnimationFrame(raf); io && io.disconnect(); ro && ro.disconnect();
      if (renderer) { renderer.dispose(); renderer.domElement.remove(); }
      host.textContent = ""; host.classList.remove("mv", "mv-hero");
    },
  };
  return api;
}
