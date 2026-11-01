/* Fish design history: lineage read from the manifests that state it (never inferred), with sibling variants, chronological revisions and derivations
 * kept apart, and display props kept apart from launch prototypes (none exist yet). Dates are repository first-commit dates, labelled as such. */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;
  const COL = { "print form v1 (display scale)": 0, "print form v2 (display scale)": 1, "3D candidate (1:1)": 2, "display prop (print, not a launch prototype)": 3, "launch glider print set (a launch prototype, untested)": 4 };
  const EDGE_LABEL = { revision: "revised in v2", "built from": "sized from", "variant of": "v3 variant", "printed from": "printed as prop" };
  const day = (d) => (d ? d.slice(0, 10) : "no date");
  const short = (id) => id.replace(/^fish3d-/, "").replace(/-v2$/, " v2");

  DF.views.history = function (snap, route) {
    const H = snap.fish_history;
    if (!H) return { html: html`<section class="pagehead"><h1>Fish design history</h1><p class="empty">The manifests that carry the lineage are not in this snapshot, so no history is shown.</p></section>` };
    const sel = route.params.sel || ""; const byId = Object.fromEntries(H.nodes.map((n) => [n.id, n]));
    // Glider revisions are ordered by their manifests' parent_revision pins, never by their names.
    const gl = H.nodes.filter((n) => n.kind.startsWith("launch glider")); const chain = []; let cur0 = gl.find((n) => !n.parent_revision);
    while (cur0 && !chain.includes(cur0)) { chain.push(cur0); cur0 = gl.find((n) => n.parent_revision === cur0.revision); }
    const ordered = [...H.nodes.filter((n) => !n.kind.startsWith("launch glider")), ...chain, ...gl.filter((n) => !chain.includes(n))];
    const rows = {}; const nodes = ordered.map((n) => { const col = COL[n.kind] ?? 0; rows[col] = (rows[col] || 0); const row = rows[col]++; return { id: n.id, label: short(n.id), sub: n.kind.split(" (")[0], col, row, cls: n.known_defect ? "con st-fail" : n.kind.startsWith("display prop") ? "src" : n.kind.startsWith("3D") ? "claimnode" : n.kind.startsWith("launch") ? "gen" : "gen" }; });
    const edges = H.edges.map((e, i) => ({ id: "e" + i, from: e.to, to: e.from, kind: e.relation, label: EDGE_LABEL[e.relation] || e.relation }));   // drawn older to newer
    const node = byId[sel]; const parents = H.edges.filter((e) => e.from === sel), children = H.edges.filter((e) => e.to === sel);
    const detail = node ? html`<div class="detail"><p class="eyebrow">${node.kind}</p><h3>${node.id}</h3>
        <dl class="kv"><div><dt>Manifest</dt><dd><code class="small">${node.manifest}</code> ${node.manifest_sha256 ? U.sha(node.manifest_sha256) : ""}</dd></div><div><dt>First commit adding the manifest</dt><dd>${day(node.first_commit_date)} <span class="faint small">(${node.first_commit_date || "unavailable"})</span></dd></div>${node.set ? html`<div><dt>Set</dt><dd>${node.set}</dd></div>` : ""}${node.display_scale ? html`<div><dt>Display scale</dt><dd>${node.display_scale}</dd></div>` : ""}</dl>
        ${node.known_defect ? html`<p class="note warn small"><b>Known defect.</b> ${node.known_defect} ${node.fixed_in ? html`<br><b>Fixed in:</b> ${node.fixed_in}. The affected files are immutable and were not edited.` : ""}</p>` : ""}${node.parent_revision ? html`<p class="small"><b>Parent revision (named in the manifest):</b> <a href="${DF.href("/history", { sel: "glider-" + node.parent_revision })}">${node.parent_revision}</a></p>` : node.revision ? html`<p class="small"><b>Parent revision:</b> none (the first of this chain)</p>` : ""}${node.label ? html`<p class="small faint">${node.label}</p>` : ""}${node.knobs ? html`<p class="small"><b>Knobs:</b> ${Object.entries(node.knobs).map(([k, v]) => k.replace(/_/g, " ") + " " + v).join(" · ")}</p>` : ""}
        ${parents.length ? html`<h4>Derived from</h4><ul class="small">${parents.map((e) => html`<li>${U.pill(e.relation, "grp")} <a href="${DF.href("/history", { sel: e.to })}">${e.to}</a>: ${e.label}<br><span class="faint">${e.source}</span></li>`)}</ul>` : ""}
        ${children.length ? html`<h4>Led to</h4><ul class="small">${children.map((e) => html`<li>${U.pill(e.relation, "grp")} <a href="${DF.href("/history", { sel: e.from })}">${e.from}</a></li>`)}</ul>` : ""}</div>` : html`<div class="detail-empty"><h3>Select a node</h3><p>Each node names its manifest, its hash and the first commit that added it, and how it relates to what it came from.</p></div>`;
    return {
      html: html`<section class="pagehead"><h1>Fish design history</h1><p class="lede">Every candidate and print form that exists in the tree, with the relationships the manifests actually state. Nothing here is inferred: a link appears only where a manifest field names it.</p></section>
        <section class="panel"><h2>How to read it</h2><ul class="small"><li><b>Chronological revision</b>: a later file replaces an earlier one and says so (print v2 supersedes print v1; the v1 files stay as published).</li><li><b>Sibling variants</b>: alternatives at the same stage, listed together in one set or built from the same baseline; they differ only in the parameters named. A sibling is not a successor.</li><li><b>Derivation</b>: one artifact made from another (3D baseline from a print form, a display prop from a 3D candidate).</li><li><b>Display prop, not a launch prototype</b>: every print here is an illustrative display form. ${H.launch_prototype.note}</li></ul>
          <p class="small faint">Dates: ${H.date_basis}</p></section>
        <section class="panel board" aria-labelledby="fh-h"><h2 id="fh-h">Lineage</h2><p class="small faint">Left to right: print forms v1, their v2 revisions, 3D candidates, display props, launch glider print sets (ordered by their parent_revision pins, not by name). Select a node or an edge for its manifest.</p>
          <div class="split graphsplit"><div><div class="graphhost" id="fhgraph"></div></div><div class="detail-col" id="fhdetail" tabindex="-1">${detail}</div></div></section>
        <section class="panel"><h2>Sibling groups</h2><div class="tablewrap"><table class="qtable"><caption class="sr">Groups of sibling variants</caption><thead><tr><th scope="col">Group</th><th scope="col">Members</th><th scope="col">Why they are siblings</th></tr></thead><tbody>${H.siblings.map((g) => html`<tr><td data-label="Group">${g.group}</td><td data-label="Members" class="small">${g.members.map((m, i) => html`${i ? ", " : ""}<a href="${DF.href("/history", { sel: m })}">${short(m)}</a>`)}</td><td data-label="Why" class="small">${g.basis}</td></tr>`)}</tbody></table></div></section>
        <section class="panel"><h2>Every node, as a table</h2><div class="tablewrap"><table class="qtable"><thead><tr><th scope="col">Id</th><th scope="col">Kind</th><th scope="col">First commit of its manifest</th><th scope="col">Manifest</th></tr></thead><tbody>${H.nodes.map((n) => html`<tr><td data-label="Id"><a href="${DF.href("/history", { sel: n.id })}">${n.id}</a></td><td data-label="Kind" class="small">${n.kind}</td><td data-label="Date" class="small">${day(n.first_commit_date)}</td><td data-label="Manifest" class="small"><code>${n.manifest}</code></td></tr>`)}</tbody></table></div></section>`,
      async after(root) {
        DF.graph.draw(root.querySelector("#fhgraph"), {
          columns: [{ title: "Print forms v1" }, { title: "Print forms v2 (revisions)" }, { title: "3D candidates" }, { title: "Display props" }, { title: "Glider print sets" }],
          nodes, edges, selected: sel && byId[sel] ? { type: "node", id: sel } : { type: "node", id: null },
          ariaLabel: "Fish design lineage: print forms, revisions, 3D candidates and display props",
          legend: [{ cls: "gen", text: "print form or launch glider print set" }, { cls: "claimnode", text: "3D candidate" }, { cls: "src", text: "display prop (not a launch prototype)" }, { cls: "con st-fail", text: "revision with a known defect" }],
          onSelect(type, id) { if (type === "node") DF.go(DF.href("/history", { sel: id })); },
        });
      },
    };
  };
})();
