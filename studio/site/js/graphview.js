/* Neighbourhood graph (route /graph/<Kind>/<id>?v=&ns=): /api/graph when the runtime serves it, otherwise a neighbourhood derived client-side from
 * the typed references in the record (target, produced_by, inputs, dependencies) and from records that target it. The page says which one it is. */
(function () {
  const DF = window.DF; const { html, esc } = DF; const U = DF.ui;
  const NS = "http://www.w3.org/2000/svg"; const svgEl = (n, a = {}, t) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); if (t !== undefined) e.textContent = t; return e; };
  const EDGE_LEGEND = { targets: "targets (evidence or action points at it)", produced_by: "produced by (artifact-producing action)", uses: "uses (action input)", depends_on: "depends on (question dependency)", related: "related (reported by the runtime)" };

  DF.views.graph = function (snap, route) {
    const kind = route.parts[1] || "", id = route.parts.slice(2).join("/");
    if (!kind || !id) return { html: html`<section class="pagehead"><h1>Neighbourhood graph</h1><p class="lede">A neighbourhood graph belongs to one exact record. Open a record from <a href="${DF.href("/knowledge")}">Knowledge</a> or the <a href="${DF.href("/search", { tab: "catalog" })}">catalog</a> and choose its neighbourhood from there. No record is selected, so no graph is drawn.</p></section>` };
    return {
      html: html`<section class="pagehead"><p class="eyebrow"><a href="${DF.href("/entity/" + kind + "/" + id, { v: route.params.v, ns: route.params.ns })}">${kind} ${id}</a> / neighbourhood</p><h1>Neighbourhood graph</h1><div id="gwrap" role="status">Loading…</div></section>`,
      async after(root) {
        const host = root.querySelector("#gwrap");
        try {
          const R = await DF.resolveRecord(kind, id, { ns: route.params.ns || "", v: route.params.v || "" });
          if (R.ambiguous) { host.removeAttribute("role"); host.innerHTML = html`<p class="lede">More than one namespace or version holds this id and none is pinned. Choose one; nothing is picked for you.</p><ul>${R.ambiguous.map((r) => html`<li><a href="${DF.href("/graph/" + r.kind + "/" + r.id, { v: r.version, ns: r.namespace })}">${r.namespace} · version ${String(r.version).slice(0, 12)}…</a></li>`)}</ul>`.toString(); return; }
          if (R.error) throw new Error(R.error);
          const ref = R.ref; const rec = R.rec; let G = null;
          try { G = await DF.api.graph(ref, { depth: 1, limit: 120 }); } catch (e) { host.removeAttribute("role"); host.innerHTML = html`<p class="empty">The graph service answered with an error (${e.message}). Nothing is drawn in its place.</p>${declared(ref, rec)}`.toString(); return; }
          if (!G || !Array.isArray(G.nodes)) { host.removeAttribute("role"); host.innerHTML = html`<p class="empty">The graph service is not available on this node, so the neighbourhood cannot be drawn. This page does not guess one. What the exact record version declares itself is listed below.</p>${declared(ref, rec)}`.toString(); return; }
          G.source = "runtime"; draw(host, snap, ref, G);
        } catch (e) { host.removeAttribute("role"); host.innerHTML = html`<p class="empty">The graph could not be built: ${e.message}. Nothing is drawn in its place.</p>`.toString(); }
      },
    };
  };

  /* Outgoing typed references declared in this exact record version. Not the neighbourhood: incoming links need the graph service. */
  function declared(ref, rec) {
    const p = rec.payload || {}; const rows = []; const add = (kind, r) => { if (r && r.kind && r.id) rows.push([kind, r]); };
    add("targets", p.target); add("produced by", p.produced_by); (p.inputs || []).forEach((x) => add("uses", x)); (p.dependencies || []).forEach((x) => add("depends on", x));
    return html`<h2 class="eh">References declared in this exact version (outgoing only)</h2>${rows.length ? html`<ul>${rows.map(([k, r]) => html`<li>${k}: <a href="${DF.href("/entity/" + r.kind + "/" + r.id, { v: r.version, ns: r.namespace })}">${r.kind} ${r.id}</a> <span class="faint small">${r.namespace}, version ${String(r.version).slice(0, 12)}…</span></li>`)}</ul>` : html`<p class="faint">This version declares no typed reference.</p>`}`;
  }

  const scopeText = (s) => (typeof s === "string" ? s : s && typeof s === "object" ? Object.entries(s).map(([k, v]) => `${k.replace(/_/g, " ")}: ${Array.isArray(v) ? v.length + " listed" : v && typeof v === "object" ? Object.entries(v).map(([a, b]) => `${a} ${typeof b === "object" ? "…" : b}`).join(", ") : String(v)}`).join("; ") : "");

  function draw(host, snap, ref, G) {
    host.removeAttribute("role");
    const centre = G.nodes.find((n) => n.ref && n.ref.id === ref.id && n.ref.kind === ref.kind) || G.nodes[0]; const others = G.nodes.filter((n) => n !== centre);
    const R = Math.max(150, 40 + others.length * 14); const W = 2 * R + 340, H = 2 * R + 140; const cx = W / 2, cy = H / 2; const pos = new Map([[centre.id, [cx, cy]]]);
    others.forEach((n, i) => { const a = (2 * Math.PI * i) / Math.max(1, others.length) - Math.PI / 2; pos.set(n.id, [cx + R * Math.cos(a), cy + R * Math.sin(a)]); });
    const kinds = [...new Set(G.edges.map((e) => e.kind))]; const hue = (k) => ["#0e7c86", "#a6c936", "#d97b29", "#7a5ea8", "#c0392b", "#3a7bd5"][kinds.indexOf(k) % 6];
    host.innerHTML = html`<p class="note small"><b>From the runtime's /api/graph.</b> ${scopeText(G.scope)} ${G.truncated ? "The runtime truncated this neighbourhood." : ""} Pins: namespace <code>${ref.namespace}</code>, version ${U.sha(ref.version)}. ${G.counts ? `${G.counts.nodes} nodes, ${G.counts.edges} edges.` : ""}</p>
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
