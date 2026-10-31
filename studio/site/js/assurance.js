/* Regional design assurance (frontier.design-assurance/1): a vector per named part, scale and model, never one score. Parts are UI anchors, not segmentation;
 * status is shown as text and colour; the interface matrix is a PAE-like display of scoped transfer checks, with no spatial error invented. */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;
  const TONE = (st) => { const s = String(st || "unknown").toLowerCase();
    if (/(^|_)(unsupported|refuted|failed?|refused|counterexample|contradict)/.test(s)) return "bad";
    if (/(^|_)(pass|passed|supported|calibrated|verified|implemented|established|composable|consistent)/.test(s)) return "good";
    if (/(partial|scoped|scenario|source_only|assumed|limited|descriptive|coverage|declared|proposed)/.test(s)) return "mid";
    return "unk"; };
  const LAB = { formal_properties: "Formal properties", numerical_fidelity: "Numerical fidelity", empirical_validation: "Empirical validation", parameter_coverage: "Parameter coverage", cross_scale_transfer: "Cross-scale transfer", ensemble_robustness: "Ensemble robustness" };
  const SHAPES = { body: '<ellipse cx="190" cy="130" rx="130" ry="34"/>', "caudal": '<path d="M318 130 L372 88 L350 130 L384 176 Z"/>', "pectoral-left": '<path d="M215 112 L150 40 L128 46 L176 118 Z"/>', "pectoral-right": '<path d="M215 148 L150 220 L128 214 L176 142 Z"/>', "pelvic-left": '<path d="M262 118 L236 82 L224 88 L246 122 Z"/>', "pelvic-right": '<path d="M262 142 L236 178 L224 172 L246 138 Z"/>' };
  const REG_LABEL = { body: "Body", caudal: "Caudal fin", "pectoral-left": "Pectoral, left", "pectoral-right": "Pectoral, right", "pelvic-left": "Pelvic, left", "pelvic-right": "Pelvic, right" };
  const ev = (list) => (list && list.length ? html`<ul class="small">${list.map((e) => html`<li><code>${e.path}</code> ${e.selector ? html`<span class="faint">[${e.selector}]</span>` : ""} sha256 ${U.sha(e.sha256)}</li>`)}</ul>` : html`<p class="small faint">No source artifact is cited for this status; missing data stays unknown.</p>`);

  DF.assurancePanel = function (A, onScale) {
    if (!A) return html`<section class="panel" aria-labelledby="as-h"><h2 id="as-h">Design assurance</h2><p class="empty">No design-assurance map is present in this tree (looked for <code>artifacts/assurance/map.json</code>). Nothing is shown in its place, and no confidence is implied.</p></section>`;
    if (A.error) return html`<section class="panel" aria-labelledby="as-h"><h2 id="as-h">Design assurance</h2><p class="empty">${A.error}.</p></section>`;
    const dims = A.dimensions || Object.keys(LAB); const node = (id) => (A.nodes || []).find((n) => n.id === id);
    return html`<section class="panel assure" aria-labelledby="as-h"><h2 id="as-h">Design assurance: where this design is supported and where it is not</h2>
      <p class="note warn"><b>No whole-organism success figure exists.</b> Project status: <b>${String(A.status).replace(/_/g, " ")}</b>. Biological success probability: <b>${A.biological_success_probability === null ? "not computed" : "see the map"}</b>; calibrated: <b>${String(A.probability_calibrated)}</b>. This is not an AlphaFold pLDDT or PAE equivalent: each part carries a vector of separate properties, and colours show one property at a time. Named parts are UI anchors, not measured segmentation or spatial error.</p>
      <fieldset class="dimpick"><legend>Colour parts by</legend>${dims.map((d, i) => html`<label><input type="radio" name="asdim" value="${d}" ${d === "empirical_validation" || (i === 0 && !dims.includes("empirical_validation")) ? raw("checked") : ""}> ${LAB[d] || d}</label>`)}</fieldset>
      <div class="aslegend" id="aslegend" role="status"></div>
      <div class="asgrid"><div><svg viewBox="0 0 420 260" class="fishmap" role="group" aria-label="Schematic fish with six named parts, coloured by the selected assurance dimension. A schematic, not a measured shape.">${raw(Object.entries(SHAPES).map(([id, d]) => `<g class="part" data-region="${id}" tabindex="0" role="button" aria-label="${esc(REG_LABEL[id])}">${d}<title>${esc(REG_LABEL[id])}</title></g>`).join("").replace(/<(ellipse|path)/g, '<$1 class="shape"'))}<text x="210" y="252" text-anchor="middle" class="tick">schematic of named parts, not a measured shape</text></svg>
        <h3 class="eh">Scales</h3><div class="scalestrip" id="asscales"></div></div>
        <div class="detail-col" id="asdetail" tabindex="-1"><div class="detail-empty"><h2 class="eh">Select a part or scale</h2><p>Each status carries its scope and the exact source artifact digest and selector it rests on.</p></div></div></div>
      <h3 class="eh">Interfaces between models</h3><p class="small">${(A.transfer_matrix || {}).axes ? "Rows are the source model, columns the target. A cell is a scoped transfer check, not a spatial error." : ""} Dimensional mismatches are refused; “unknown” is a valid cell.</p><div class="tablewrap" id="asmatrix"></div><div id="asmcell" class="note small" role="status"></div>
      <h3 class="eh">Next questions</h3>${nextBlock(A)}
      ${A.dependence_graph ? html`<p class="small faint"><b>Aggregation:</b> ${A.dependence_graph.aggregation}</p>` : ""}
      ${(A.notices || []).length ? html`<details><summary class="small">Notices (${A.notices.length})</summary><ul class="small">${A.notices.map((n) => html`<li>${typeof n === "string" ? n : JSON.stringify(n)}</li>`)}</ul></details>` : ""}
      ${(A.evidence_index || []).length ? html`<details><summary class="small">Evidence index (${A.evidence_index.length} files)</summary><div class="tablewrap"><table><thead><tr><th>Path</th><th>Bytes</th><th>sha256</th></tr></thead><tbody>${A.evidence_index.map((e) => html`<tr><td><code>${e.path}</code></td><td>${e.byte_size}</td><td>${U.sha(e.sha256)}</td></tr>`)}</tbody></table></div></details>` : ""}
      <p class="small faint">Map file sha256 ${U.sha(A.file_sha256 || "")}. Typed coupling “pass” means dimensional and interface consistency only. Repeated frames, seeds and shared priors are not independent biological confirmations.</p></section>`;
  };

  function nextBlock(A) {
    const P = A.project || {};
    const li = (x) => html`<li>${typeof x === "string" ? x : x.text || x.title || x.action || JSON.stringify(x)}${x && x.blocked_by ? html` <span class="faint small">blocked by ${[].concat(x.blocked_by).join(", ")}</span>` : ""}</li>`;
    return html`<div class="two"><article><h4>Unsupported essential bridges</h4>${(P.unsupported_essential_bridges || []).length ? html`<ul>${P.unsupported_essential_bridges.map(li)}</ul>` : html`<p class="faint small">None listed.</p>`}</article>
      <article><h4>Counterexamples</h4>${(P.counterexamples || []).length ? html`<ul>${P.counterexamples.map(li)}</ul>` : html`<p class="faint small">None listed.</p>`}</article></div>
      <h4>Next actions, ordered by declared blocker and dependency policy</h4>${(P.next_actions || []).length ? html`<ol>${P.next_actions.map(li)}</ol>` : html`<p class="faint small">None listed.</p>`}<p class="small faint">Expected information gain: <b>${P.expected_information_gain === null || P.expected_information_gain === undefined ? "not computed" : "see the map"}</b>. No utility or information number is invented.</p>`;
  }

  DF.assuranceWire = function (root, A, onScale) {
    if (!A || A.error) return; const dims = A.dimensions || Object.keys(LAB); let dim = (root.querySelector("input[name=asdim]:checked") || {}).value || dims[0]; let sel = null;
    const det = root.querySelector("#asdetail");
    const stat = (n, d) => (n && n.vector && n.vector[d]) || { status: "unknown", summary: "No entry for this dimension.", scope: "", evidence: [] };
    const regNode = (id) => (A.nodes || []).find((n) => n.kind === "region" && (n.region_ids || []).includes(id)) || (A.nodes || []).find((n) => n.id === id);
    const show = (n, title) => { if (!n) { det.innerHTML = `<h2 class="eh">${esc(title)}</h2><p class="empty">The map has no node for this part. Its status is unknown.</p>`; return; }
      det.innerHTML = html`<h2 class="eh">${n.label || title}</h2><p class="small faint">${n.kind}${(n.model_ids || []).length ? " · models " + n.model_ids.join(", ") : ""}</p><dl class="vec">${dims.map((d) => { const v = stat(n, d); return html`<div class="${"vrow t-" + TONE(v.status) + (d === dim ? " cur" : "")}"><dt>${LAB[d] || d}</dt><dd><b>${String(v.status).replace(/_/g, " ")}</b><br><span class="small">${v.summary || ""}</span>${v.scope ? html`<br><span class="small faint">Scope: ${v.scope}</span>` : ""}${ev(v.evidence)}</dd></div>`; })}</dl>`.toString(); };
    const paint = () => {
      root.querySelectorAll(".part").forEach((g) => { const n = regNode(g.dataset.region); const t = TONE(stat(n, dim).status); g.setAttribute("class", "part t-" + t + (sel === g.dataset.region ? " sel" : "")); const lab = `${REG_LABEL[g.dataset.region]}: ${String(stat(n, dim).status).replace(/_/g, " ")} (${LAB[dim] || dim})`; g.setAttribute("aria-label", lab); const ti = g.querySelector("title"); if (ti) ti.textContent = lab; });
      const sc = root.querySelector("#asscales"); const scaleNodes = (A.nodes || []).filter((n) => n.kind === "scale");
      sc.innerHTML = scaleNodes.map((n) => { const st = stat(n, dim).status; return `<button type="button" class="scalechip t-${TONE(st)}" data-node="${esc(n.id)}"><b>${esc(n.label || n.id)}</b><small>${esc(String(st).replace(/_/g, " "))}</small></button>`; }).join("") || '<p class="faint small">No scale node in the map.</p>';
      sc.querySelectorAll("[data-node]").forEach((b) => b.addEventListener("click", () => { const n = node(b.dataset.node); show(n, b.textContent); if (onScale && n && n.studio_anchor) onScale(n.studio_anchor); }));
      const seen = [...new Set((A.nodes || []).map((n) => String(stat(n, dim).status)))]; root.querySelector("#aslegend").innerHTML = `<b>${esc(LAB[dim] || dim)}</b>: ` + (seen.length ? seen.map((s) => `<span class="lg t-${TONE(s)}"><i></i>${esc(s.replace(/_/g, " "))}</span>`).join(" ") : "no statuses") + ` <span class="faint small">Gray means unknown. Colour is never the only signal: each status is also written out.</span>`;
    };
    root.querySelectorAll("input[name=asdim]").forEach((r) => r.addEventListener("change", () => { dim = r.value; paint(); if (sel) show(regNode(sel), REG_LABEL[sel]); }));
    root.querySelectorAll(".part").forEach((g) => { const go = () => { sel = g.dataset.region; paint(); show(regNode(sel), REG_LABEL[sel]); }; g.addEventListener("click", go); g.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); go(); } }); });
    // interface matrix
    const T = A.transfer_matrix || { axes: [], entries: [] }; const cell = (a, b) => (T.entries || []).find((e) => e.from === a && e.to === b);
    root.querySelector("#asmatrix").innerHTML = T.axes && T.axes.length ? `<table class="matrix"><thead><tr><th scope="col">from \\ to</th>${T.axes.map((b) => `<th scope="col">${esc(b)}</th>`).join("")}</tr></thead><tbody>${T.axes.map((a) => `<tr><th scope="row">${esc(a)}</th>${T.axes.map((b) => { if (a === b) return '<td class="diag" aria-label="same model">·</td>'; const c = cell(a, b); const st = c ? c.status : "unknown"; return `<td><button type="button" class="mcell t-${TONE(st)}" data-from="${esc(a)}" data-to="${esc(b)}" aria-label="${esc(a + " to " + b + ": " + String(st).replace(/_/g, " "))}">${esc(String(st).replace(/_/g, " "))}</button></td>`; }).join("")}</tr>`).join("")}</tbody></table>` : '<p class="empty">No interface matrix is present in the map.</p>';
    root.querySelectorAll(".mcell").forEach((b) => b.addEventListener("click", () => { const c = cell(b.dataset.from, b.dataset.to); const out = root.querySelector("#asmcell");
      out.innerHTML = c ? html`<b>${c.from} → ${c.to}</b>: ${String(c.status).replace(/_/g, " ")}. Unit check: ${c.unit_check === undefined || c.unit_check === null ? "not recorded" : typeof c.unit_check === "object" ? JSON.stringify(c.unit_check) : c.unit_check}. Quantitative error: <b>${c.quantitative_error === null || c.quantitative_error === undefined ? "not measured" : c.quantitative_error}</b>.
        ${(c.assumptions || []).length ? html`<br>Assumes: ${c.assumptions.map((x) => (typeof x === "string" ? x : JSON.stringify(x))).join("; ")}.` : ""}${(c.missing_calibrations || []).length ? html`<br>Missing calibrations: ${c.missing_calibrations.map((x) => (typeof x === "string" ? x : JSON.stringify(x))).join("; ")}.` : ""}${ev(c.evidence)}`.toString() : `<b>${esc(b.dataset.from)} → ${esc(b.dataset.to)}</b>: no transfer entry exists, so the interface is unknown.`; }));
    paint();
  };
})();
