/* Neighbourhood graph (route /graph/<Kind>/<id>?v=&ns=): /api/graph when the runtime serves it, otherwise a neighbourhood derived client-side from
 * the typed references in the record (target, produced_by, inputs, dependencies) and from records that target it. The page says which one it is. */
(function () {
  const DF = window.DF; const { html, esc } = DF; const U = DF.ui;
  const NS = "http://www.w3.org/2000/svg"; const svgEl = (n, a = {}, t) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); if (t !== undefined) e.textContent = t; return e; };
  const EDGE_LEGEND = { targets: "targets (evidence or action points at it)", produced_by: "produced by (artifact-producing action)", uses: "uses (action input)", depends_on: "depends on (question dependency)", related: "related (reported by the runtime)" };

  async function derive(ref, rec) {
    const nodes = new Map(); const edges = []; const key = (r) => `${r.namespace}/${r.kind}/${r.id}`;
    const add = (r, title) => { const k = key(r); if (!nodes.has(k)) nodes.set(k, { id: k, type: r.kind, kind: r.kind, ref: r, title: title || r.id }); return k; };
    const me = add(ref, rec.title); const p = rec.payload || {};
    const out = (r, kind, label) => { if (r && r.kind && r.id) { const t = add({ namespace: r.namespace || ref.namespace, kind: r.kind, id: r.id, version: r.version }); edges.push({ id: `${me}>${t}:${kind}`, from: me, to: t, kind, label }); } };
    out(p.target, "targets", "this record targets it"); out(p.produced_by, "produced_by", "produced by this action"); (p.inputs || []).forEach((x) => out(x, "uses", "uses this input")); (p.dependencies || []).forEach((x) => out(x, "depends_on", "depends on this question"));
    let more = [];
    try { more = (await DF.api.catalog({ query: ref.id, limit: 50 })).records.filter((x) => x.ref.id !== ref.id && x.payload && [x.payload.target, x.payload.produced_by, ...(x.payload.inputs || []), ...(x.payload.dependencies || [])].some((r) => r && r.id === ref.id)); } catch (e) { /* the graph stands without incoming edges */ }
    more.forEach((x) => { const o = add(x.ref, x.title); const pl = x.payload; const kind = pl.target && pl.target.id === ref.id ? "targets" : pl.produced_by && pl.produced_by.id === ref.id ? "produced_by" : (pl.inputs || []).some((r) => r.id === ref.id) ? "uses" : "depends_on"; edges.push({ id: `${o}>${me}:${kind}`, from: o, to: me, kind, label: `${x.ref.kind} ${x.ref.id} points here` }); });
    return { nodes: [...nodes.values()], edges, truncated: false, scope: "derived in this browser from typed references in the record and in records found by a text lookup of its id; not exhaustive", counts: { nodes: nodes.size, edges: edges.length }, source: "client" };
  }

  DF.views.graph = function (snap, route) {
    const kind = route.parts[1] || "", id = route.parts.slice(2).join("/");
    return {
      html: html`<section class="pagehead"><p class="eyebrow"><a href="${DF.href("/entity/" + kind + "/" + id, { v: route.params.v, ns: route.params.ns })}">${kind} ${id}</a> / neighbourhood</p><h1>Neighbourhood graph</h1><div id="gwrap" role="status">Loading…</div></section>`,
      async after(root) {
        const host = root.querySelector("#gwrap");
        try {
          const cands = (await DF.api.catalog({ query: id, kind, limit: 50 })).records.filter((x) => x.ref.id === id); const v = route.params.v;
          const hit = (v ? cands.find((x) => x.ref.version === v) : null) || cands[0]; if (!hit) throw new Error(`no ${kind} “${id}” is visible`);
          const rec = await DF.api.record(hit.ref); const ref = hit.ref;
          let G = null; try { G = await DF.api.graph(ref, { depth: 1, limit: 120 }); } catch (e) { G = null; }
          if (G && Array.isArray(G.nodes)) G.source = "runtime"; else G = await derive(ref, rec);
          draw(host, snap, ref, G);
        } catch (e) { host.removeAttribute("role"); host.innerHTML = html`<p class="empty">The graph could not be built: ${e.message}. Nothing is drawn in its place.</p>`.toString(); }
      },
    };
  };

  function draw(host, snap, ref, G) {
    host.removeAttribute("role");
    const centre = G.nodes.find((n) => n.ref && n.ref.id === ref.id && n.ref.kind === ref.kind) || G.nodes[0]; const others = G.nodes.filter((n) => n !== centre);
    const R = Math.max(150, 40 + others.length * 14); const W = 2 * R + 340, H = 2 * R + 140; const cx = W / 2, cy = H / 2; const pos = new Map([[centre.id, [cx, cy]]]);
    others.forEach((n, i) => { const a = (2 * Math.PI * i) / Math.max(1, others.length) - Math.PI / 2; pos.set(n.id, [cx + R * Math.cos(a), cy + R * Math.sin(a)]); });
    const kinds = [...new Set(G.edges.map((e) => e.kind))]; const hue = (k) => ["#0e7c86", "#a6c936", "#d97b29", "#7a5ea8", "#c0392b", "#3a7bd5"][kinds.indexOf(k) % 6];
    host.innerHTML = html`<p class="note small"><b>${G.source === "runtime" ? "From the runtime's /api/graph." : "Derived in this browser."}</b> ${G.scope || ""} ${G.truncated ? "The runtime truncated this neighbourhood." : ""} Pins: namespace <code>${ref.namespace}</code>, version ${U.sha(ref.version)}. ${G.counts ? `${G.counts.nodes} nodes, ${G.counts.edges} edges.` : ""}</p>
      <div class="gtools" role="group" aria-label="Graph view controls"><button class="btn small" type="button" data-z="in">Zoom in</button><button class="btn small" type="button" data-z="out">Zoom out</button><button class="btn small ghost" type="button" data-z="reset">Reset view</button><span class="small faint">Drag to pan, wheel to zoom. Focus a node and use the arrow keys to move between nodes; Enter opens it.</span></div>
      <div class="split graphsplit"><div class="graphhost gview" id="gv" tabindex="-1"></div><div class="detail-col" id="gdetail" tabindex="-1"><div class="detail-empty"><h2 class="eh">Select a node</h2><p>Hover to highlight its links; click or press Enter to see it here.</p></div></div></div>
      <h2 class="eh">Legend</h2><ul class="legend inline">${kinds.length ? kinds.map((k) => html`<li><i class="sw" style="background:${hue(k)}"></i>${EDGE_LEGEND[k] || k}</li>`) : html`<li class="faint">No relationships are recorded for this record.</li>`}</ul>
      <h2 class="eh">The same neighbourhood as a list</h2><div class="tablewrap"><table><thead><tr><th>From</th><th>Relationship</th><th>To</th></tr></thead><tbody>${G.edges.map((e) => { const a = G.nodes.find((n) => n.id === e.from), b = G.nodes.find((n) => n.id === e.to); const l = (n) => n && n.ref ? html`<a href="${DF.href("/entity/" + n.ref.kind + "/" + n.ref.id, { v: n.ref.version, ns: n.ref.namespace })}">${n.title || n.ref.id}</a>` : html`${n ? n.title : e.from}`; return html`<tr><td>${l(a)}</td><td>${e.label || e.kind}</td><td>${l(b)}</td></tr>`; })}</tbody></table></div>`.toString();
    const box = host.querySelector("#gv"); const svg = svgEl("svg", { viewBox: `0 0 ${W} ${H}`, class: "graph gsvg", role: "group", "aria-label": `Neighbourhood of ${ref.kind} ${ref.id}` }); svg.style.minWidth = "0";
    const vp = svgEl("g"); svg.appendChild(vp); let sc = 1, tx = 0, ty = 0; const apply = () => vp.setAttribute("transform", `translate(${tx} ${ty}) scale(${sc})`);
    const eg = svgEl("g"), ng = svgEl("g"); vp.appendChild(eg); vp.appendChild(ng); const edgeEls = [];
    G.edges.forEach((e) => { const a = pos.get(e.from), b = pos.get(e.to); if (!a || !b) return; const l = svgEl("line", { x1: a[0], y1: a[1], x2: b[0], y2: b[1], stroke: hue(e.kind), "stroke-width": 2.2, "stroke-opacity": 0.8 }); l.appendChild(svgEl("title", {}, e.label || e.kind)); eg.appendChild(l); edgeEls.push([e, l]); });
    const order = [centre, ...others]; const nodeEls = [];
    const select = (n) => { nodeEls.forEach(([m, g]) => g.classList.toggle("sel", m === n)); host.querySelector("#gdetail").innerHTML = html`<article class="detail"><p class="eyebrow">${n.kind || n.type}</p><h2 class="eh">${n.title || (n.ref && n.ref.id)}</h2><p>${n.local_status ? U.pill("local status: " + String(n.local_status).replace(/_/g, " "), "st-unk") : ""}</p><p class="small"><code>${n.ref ? n.ref.namespace + "/" + n.ref.kind + "/" + n.ref.id : n.id}</code>${n.ref && n.ref.version ? html`<br>version ${U.sha(n.ref.version)}` : ""}</p>${n.scale ? html`<p class="small">Scale: ${n.scale}</p>` : ""}
      <p>${n.ref ? html`<a class="btn small" href="${DF.href("/entity/" + n.ref.kind + "/" + n.ref.id, { v: n.ref.version, ns: n.ref.namespace })}">Open the page</a> <a class="btn small ghost" href="${DF.href("/graph/" + n.ref.kind + "/" + n.ref.id, { v: n.ref.version, ns: n.ref.namespace })}">Centre the graph here</a>` : ""}</p>
      <h3>Links</h3><ul class="small">${G.edges.filter((e) => e.from === n.id || e.to === n.id).map((e) => html`<li>${e.label || e.kind}</li>`)}</ul></article>`.toString(); };
    order.forEach((n, i) => { const [x, y] = pos.get(n.id); const g = svgEl("g", { class: "g-node " + (n === centre ? "goal" : "src"), tabindex: 0, role: "button", "aria-label": `${n.kind || n.type} ${n.title || n.id}. Press Enter to see detail.` });
      g.appendChild(svgEl("circle", { cx: x, cy: y, r: n === centre ? 26 : 18, class: "g-box" })); const t = (n.title || n.id); g.appendChild(svgEl("text", { x, y: y + (n === centre ? 44 : 34), "text-anchor": "middle", class: "g-label" }, t.length > 26 ? t.slice(0, 25) + "…" : t)); g.appendChild(svgEl("text", { x, y: y + 4, "text-anchor": "middle", class: "g-sub" }, (n.kind || n.type || "").slice(0, 3)));
      const hov = (on) => edgeEls.forEach(([e, l]) => l.setAttribute("stroke-width", on && (e.from === n.id || e.to === n.id) ? 4.5 : 2.2));
      g.addEventListener("mouseenter", () => hov(true)); g.addEventListener("mouseleave", () => hov(false)); g.addEventListener("focus", () => hov(true)); g.addEventListener("blur", () => hov(false));
      g.addEventListener("click", () => select(n));
      g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); select(n); } else if (["ArrowRight", "ArrowDown", "ArrowLeft", "ArrowUp"].includes(ev.key)) { ev.preventDefault(); const d = ev.key === "ArrowRight" || ev.key === "ArrowDown" ? 1 : -1; nodeEls[(i + d + nodeEls.length) % nodeEls.length][1].focus(); } });
      ng.appendChild(g); nodeEls.push([n, g]); });
    box.appendChild(svg); apply(); select(centre);
    const zoom = (f) => { sc = Math.max(0.4, Math.min(4, sc * f)); apply(); };
    host.querySelectorAll("[data-z]").forEach((b) => b.addEventListener("click", () => { if (b.dataset.z === "in") zoom(1.25); else if (b.dataset.z === "out") zoom(0.8); else { sc = 1; tx = 0; ty = 0; apply(); } }));
    box.addEventListener("wheel", (e) => { e.preventDefault(); zoom(e.deltaY < 0 ? 1.1 : 0.9); }, { passive: false });
    let drag = null; svg.addEventListener("pointerdown", (e) => { if (e.target.closest(".g-node")) return; drag = { x: e.clientX, y: e.clientY, tx, ty }; svg.setPointerCapture(e.pointerId); });
    svg.addEventListener("pointermove", (e) => { if (!drag) return; tx = drag.tx + (e.clientX - drag.x) * (W / svg.clientWidth); ty = drag.ty + (e.clientY - drag.y) * (W / svg.clientWidth); apply(); }); svg.addEventListener("pointerup", () => (drag = null)); svg.addEventListener("pointercancel", () => (drag = null));
  }
})();
