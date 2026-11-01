/* Layered SVG graph with selectable nodes and labelled, selectable edges. Deterministic layout from
 * the data (column/row given by the caller): position never encodes anything it is not told to. */
(function () {
  const DF = window.DF; const { esc } = DF;
  const NS = "http://www.w3.org/2000/svg";
  const node = (n, a = {}, text) => { const e = document.createElementNS(NS, n); for (const k in a) e.setAttribute(k, a[k]); if (text !== undefined) e.textContent = text; return e; };

  function wrap(text, max) {
    const words = String(text).split(/\s+/); const lines = []; let cur = "";
    words.forEach((w) => { if ((cur + " " + w).trim().length > max && cur) { lines.push(cur); cur = w; } else cur = (cur + " " + w).trim(); });
    if (cur) lines.push(cur);
    if (lines.length > 3) { lines.length = 3; lines[2] = lines[2].replace(/.{0,2}$/, "…"); }
    return lines;
  }

  /* spec: {columns:[{title}], nodes:[{id,label,col,row,cls,sub}], edges:[{id,from,to,kind,label}], selected:{type,id}, onSelect(type,id), legend:[{cls,text}], ariaLabel} */
  function draw(host, spec) {
    host.innerHTML = "";
    const colW = 262, nodeW = 176, nodeH = 52, gapY = 22, padX = 18, padTop = 34;
    const rows = Math.max(1, ...spec.nodes.map((n) => n.row + 1));
    const W = padX * 2 + colW * spec.columns.length - (colW - nodeW);
    const H = padTop + rows * (nodeH + gapY);
    const svg = node("svg", { viewBox: `0 0 ${W} ${H}`, class: "graph", role: "group", "aria-label": spec.ariaLabel || "Graph" });
    svg.style.minWidth = Math.min(W, 800) + "px";
    spec.columns.forEach((c, i) => svg.appendChild(node("text", { x: padX + i * colW, y: 16, class: "g-col" }, c.title)));
    const pos = {}; spec.nodes.forEach((n) => { pos[n.id] = { x: padX + n.col * colW, y: padTop + n.row * (nodeH + gapY) }; });
    const eg = node("g"); const ng = node("g"); const placed = [];
    const sel = spec.selected || {};
    const defs = node("defs"); defs.innerHTML = '<marker id="arr" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L8,4 L0,8 z" class="g-arrow"/></marker>';
    svg.appendChild(defs); svg.appendChild(eg); svg.appendChild(ng);
    const activate = (el, fn) => { el.addEventListener("click", fn); el.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); fn(); } }); };
    spec.edges.forEach((e, k) => {
      const a = pos[e.from], b = pos[e.to]; if (!a || !b) return;
      const sameCol = Math.abs(a.x - b.x) < 2;
      const x1 = sameCol ? a.x + nodeW / 2 : (a.x < b.x ? a.x + nodeW : a.x), y1 = a.y + (sameCol ? (a.y < b.y ? nodeH : 0) : nodeH / 2);
      const x2 = sameCol ? b.x + nodeW / 2 : (a.x < b.x ? b.x : b.x + nodeW), y2 = b.y + (sameCol ? (a.y < b.y ? 0 : nodeH) : nodeH / 2);
      const mx = (x1 + x2) / 2, my = (y1 + y2) / 2 + (sameCol ? 0 : (k % 3 - 1) * 6);
      const d = sameCol ? `M${x1},${y1} L${x2},${y2}` : `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
      const g = node("g", { class: "g-edge " + (e.kind || "") + (sel.type === "edge" && sel.id === e.id ? " sel" : ""), tabindex: 0, role: "button", "aria-label": `Edge ${e.kind || ""}: ${e.label || e.id}. Select for detail.` });
      g.appendChild(node("path", { d, class: "g-line", "marker-end": "url(#arr)" }));
      g.appendChild(node("path", { d, class: "g-hit" }));
      const kind = e.kind || ""; const lw = 8 + kind.length * 6.2;
      // Place the label on the first spot along the edge that touches no node box and no earlier label; if none is free it is hidden until the edge is hovered, focused or selected (its kind stays in the aria-label and the list below).
      const bez = (t) => { if (sameCol) return [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]; const u = 1 - t; return [u * u * u * x1 + 3 * u * u * t * mx + 3 * u * t * t * mx + t * t * t * x2, u * u * u * y1 + 3 * u * u * t * y1 + 3 * u * t * t * y2 + t * t * t * y2]; };
      const hit = (r) => placed.some((q) => r.x < q.x + q.w && r.x + r.w > q.x && r.y < q.y + q.h && r.y + r.h > q.y) || Object.values(pos).some((q) => r.x < q.x + nodeW && r.x + r.w > q.x && r.y < q.y + nodeH && r.y + r.h > q.y);
      let spot = null; for (const t of [0.5, 0.42, 0.58, 0.34, 0.66, 0.26, 0.74, 0.18, 0.82]) { const [px, py] = bez(t); const r = { x: px - lw / 2, y: py - 7, w: lw, h: 14 }; if (!hit(r)) { spot = r; break; } }
      const lx = spot ? spot.x + lw / 2 : mx, ly = spot ? spot.y + 11 : my - 4; if (spot) placed.push(spot);
      const hid = spot ? "" : " g-hid";
      g.appendChild(node("rect", { x: lx - lw / 2, y: ly - 11, width: lw, height: 14, rx: 7, class: "g-elabel-bg" + hid }));
      g.appendChild(node("text", { x: lx, y: ly, class: "g-elabel" + hid, "text-anchor": "middle" }, kind));
      activate(g, () => spec.onSelect("edge", e.id));
      eg.appendChild(g);
    });
    spec.nodes.forEach((n) => {
      const p = pos[n.id]; const on = sel.type === "node" && sel.id === n.id;
      const g = node("g", { class: "g-node " + (n.cls || "") + (on ? " sel" : ""), tabindex: 0, role: "button", "aria-label": `${n.label}${n.sub ? ", " + n.sub : ""}. Select for detail.`, "aria-pressed": on ? "true" : "false" });
      g.appendChild(node("rect", { x: p.x, y: p.y, width: nodeW, height: nodeH, rx: 9, class: "g-box" }));
      const lines = wrap(n.label, 26);
      lines.forEach((l, i) => g.appendChild(node("text", { x: p.x + 10, y: p.y + 18 + i * 14, class: "g-label" }, l)));
      if (n.sub && lines.length < 3) { const maxc = Math.max(8, Math.floor((nodeW - 20) / 6)); const sub = n.sub.length > maxc ? n.sub.slice(0, maxc - 1) + "…" : n.sub;   // a long sub-label is cut to the box, the full text stays in the aria-label
        g.appendChild(node("text", { x: p.x + 10, y: p.y + 18 + lines.length * 14, class: "g-sub" }, sub)); }
      activate(g, () => spec.onSelect("node", n.id));
      ng.appendChild(g);
    });
    host.appendChild(svg);
    if (spec.legend) {
      const l = document.createElement("div"); l.className = "legend";
      l.innerHTML = spec.legend.map((x) => `<span><i class="sw ${esc(x.cls)}"></i>${esc(x.text)}</span>`).join("");
      host.appendChild(l);
    }
  }
  DF.graph = { draw };
})();
