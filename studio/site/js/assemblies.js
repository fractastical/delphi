/* Biodesign assembly comparison and history: the compiler's pinned assemblies for the fish3d variants, six separate axes (never one badge), shared
 * biological pins, layer diffs, retained failures and unresolved bridges, as the compiler's report.json states them. Not a whole-genome design, not a
 * claim that any variant is biologically valid, and an unresolved bridge is a gap, not a violated constraint. */
(function () {
  const DF = window.DF; const { html, esc } = DF; const U = DF.ui;
  const AXIS_LABEL = { structural_refs: "Structural references", units_context: "Units and context", model_domain: "Model domain", numerical: "Numerical", empirical: "Empirical", implementation: "Implementation" };
  const AXIS_ORDER = ["structural_refs", "units_context", "model_domain", "numerical", "empirical", "implementation"];
  const cls = (st) => (/fail|not converged|refused/i.test(st) ? "no" : /^pass/i.test(st) ? "ok" : "warn");
  const plain = (v) => (v === null || v === undefined ? "not stated" : Array.isArray(v) ? (v.length ? v.map(plain).join("; ") : "none") : typeof v === "object" ? Object.entries(v).map(([k, x]) => k.replace(/_/g, " ") + ": " + plain(x)).join("; ") : String(v));
  const short = (id) => id.replace(/^fish3d-/, "");
  const HOME = { "fish3d-v3a": "v3a ray-fan", "fish3d-v3b": "v3b glide pose", "fish3d-v3c": "v3c Daane length" };
  const num = (x) => (typeof x === "number" ? String(Number(x.toPrecision(4))) : "not stated");

  DF.views.assemblies = function (snap) {
    const B = snap.biodesign;
    if (!B || !B.report) return { html: html`<section class="pagehead"><h1>Biodesign assemblies</h1><p class="empty">The compiler's report is not in this snapshot${B && B.refused.length ? " (a file did not match its declared hash: " + B.refused.join(", ") + ")" : ""}, so no assembly is shown.</p></section>` };
    const R = B.report; const ids = R.compiled.map((c) => c.assembly); const ax = (c, k) => c.axes[k] || {};
    // One short line per axis; the full fields sit in a disclosure, as a readable tree, never as a block of prose.
    const pct = (x) => (typeof x === "number" ? (x * 100).toFixed(2) + "%" : "not stated");
    const cnt = (o) => Object.entries(o || {}).map(([k, v]) => v + " " + k.replace(/ \(.*\)/, "")).join(", ");
    const SUM = {
      structural_refs: (a) => `${(a.pinned_ok || []).length} pinned files match their hashes${(a.failures || []).length ? "; " + a.failures.length + " do not" : ""}`,
      units_context: (a) => `${cnt(a.counts)}; the registry models are not these variants`,
      model_domain: (a) => a.reading || "not stated",
      numerical: (a) => `CL change on refinement ${pct(a.CL_rel_change_48x16_to_72x24)}; ${a.frozen_threshold === null ? "no frozen threshold" : "threshold " + a.frozen_threshold}`,
      empirical: (a) => ((a.calibrations_registered || []).length ? a.calibrations_registered.length + " calibrations registered" : "no calibration registered"),
      implementation: (a) => "proposals only; no genome implied",
    };
    const tree = (v) => (v === null || v === undefined ? html`<span class="faint">not stated</span>` : Array.isArray(v) ? (v.length ? html`<ul class="astree">${v.map((x) => html`<li>${tree(x)}</li>`)}</ul>` : html`<span class="faint">none</span>`)
      : typeof v === "object" ? html`<dl class="astree">${Object.entries(v).map(([k, x]) => html`<dt>${k.replace(/_/g, " ")}</dt><dd>${tree(x)}</dd>`)}</dl>` : html`${String(v)}`);
    const cell = (c, k) => { const a = ax(c, k); const { status, reading, ...rest } = a; const line = (SUM[k] ? SUM[k](a) : reading) || "not stated";
      return html`<td data-label="${HOME[c.assembly] || c.assembly}">${U.pill(status || "not stated", cls(status || ""))}<p class="small asline">${line}</p>${(Object.keys(rest).length || (reading && SUM[k] && k !== "model_domain")) ? html`<details class="asinspect"><summary class="small">Inspect checks</summary>${reading && SUM[k] && k !== "model_domain" ? html`<p class="small">${reading}</p>` : ""}${Object.keys(rest).length ? tree(rest) : ""}</details>` : ""}</td>`; };
    return {
      html: html`<section class="pagehead"><p class="eyebrow"><a href="${DF.href("/studio/flying-fish")}">Studio</a> / assemblies</p><h1>Biodesign assemblies</h1><p class="lede">Three fish variants, each a bundle of pinned files: genetic blueprint, regulatory map, tissue interface, geometry, aerodynamics and behavior. The compiler checks six things about each bundle and keeps them apart.</p></section>
        <section class="panel"><p class="note warn small"><b>${U.pill("pinned files, not a genome", "warn")} ${U.pill("no single score", "warn")}</b> ${R.compiled[0].no_single_badge} No whole genome is designed here and no variant is shown to be biologically valid. ${B.assemblies[ids[0]].scope}.</p></section>
        <section class="panel" aria-labelledby="as-axes"><h2 id="as-axes">Six axes, kept separate</h2><div class="tablewrap"><table class="qtable asmatrix"><caption class="sr">Compiler axes for each assembly</caption><thead><tr><th scope="col">Axis</th>${R.compiled.map((c) => html`<th scope="col">${HOME[c.assembly] || c.assembly}</th>`)}</tr></thead><tbody>
          ${AXIS_ORDER.map((k) => html`<tr id="axis-${k}"><th scope="row">${AXIS_LABEL[k]}</th>${R.compiled.map((c) => cell(c, k))}</tr>`)}</tbody></table></div>
          ${R.retained_failures.length ? html`<p class="note warn small" id="as-retained"><b>Retained failure.</b> ${R.retained_failures.map((f) => HOME[f] || f).join(", ")} stays in the comparison with its failure visible: its aerodynamic refinement did not converge, so its lift is listed but unusable.</p>` : ""}</section>
        <section class="panel" aria-labelledby="as-cmp"><h2 id="as-cmp">Matched comparison</h2><p class="small">${R.comparison.matched_conditions}. ${R.comparison.note}.</p><div class="tablewrap"><table class="qtable"><caption class="sr">Matched aerodynamic comparison</caption><thead><tr><th scope="col">Assembly</th><th scope="col">CL (paired fins, alpha 4)</th><th scope="col">Change on refinement</th><th scope="col">Usable for comparison</th><th scope="col">Status</th></tr></thead><tbody>
          ${R.comparison.rows.map((r) => html`<tr><td data-label="Assembly"><b>${HOME[r.assembly] || r.assembly}</b></td><td data-label="CL">${num(r.CL_paired_fins_alpha4_S_lattice)}</td><td data-label="Refinement change">${num(r.refinement_CL_rel_change)}</td><td data-label="Usable">${r.usable_for_comparison ? "yes" : U.pill("no", "no")}</td><td data-label="Status" class="small">${r.aero_status}</td></tr>`)}</tbody></table></div></section>
        <section class="panel" aria-labelledby="as-br"><h2 id="as-br">Unresolved bridges, beside every variant</h2><p class="small">A bridge with no registered model is a gap to work on, not a violated constraint.</p><div class="asbridges">
          ${R.compiled.map((c) => html`<article class="card"><h3>${HOME[c.assembly] || c.assembly}</h3><ul class="small">${c.unresolved_bridges.map((b) => html`<li><b>${b.bridge}</b> ${U.pill(b.status, "st-unk")}<br>${b.reason}${b.coupling_id ? html` <span class="faint">(nearest registered coupling ${b.coupling_id}: ${b.coupling_label})</span>` : ""}</li>`)}</ul></article>`)}</div>
          <p class="small"><a href="${DF.href("/experimentation", { tab: "cross" })}">Measurements to consider across scales (Experimentation)</a> · <a href="${DF.href("/blueprints")}">Genetic blueprints</a> · <a href="${DF.href("/regulatory")}">Regulatory applicability</a></p></section>
        <section class="panel" aria-labelledby="as-pins"><h2 id="as-pins">What is pinned, and what is shared</h2><p class="small">${B.assemblies[ids[0]].shared_pins_note}.</p><div class="tablewrap"><table class="qtable"><caption class="sr">Pinned files per assembly</caption><thead><tr><th scope="col">Layer</th>${ids.map((i) => html`<th scope="col">${HOME[i] || i}</th>`)}</tr></thead><tbody>
          ${Object.keys(B.assemblies[ids[0]].components).map((layer) => { const shared = (B.assemblies[ids[0]].shared_pins || []).includes(layer); return html`<tr><th scope="row">${layer.replace(/_/g, " ")} ${shared ? U.pill("shared by all variants", "grp") : ""}</th>${ids.map((i) => { const c = B.assemblies[i].components[layer]; return html`<td data-label="${HOME[i] || i}"><code class="small">${c.path}</code><br>${U.sha(c.sha256)}</td>`; })}</tr>`; })}</tbody></table></div></section>
        <section class="panel" aria-labelledby="as-hist"><h2 id="as-hist">History: what changes between variants</h2><p class="small">For each pair, the layers whose pinned file changed, the stages that must be re-checked, the stages that carry over, and the geometry settings that differ.</p>
          ${R.layer_revision_diff.map((d) => html`<details class="asdiff" ${d.a === "fish3d-v3a" && d.b === "fish3d-v3b" ? "open" : ""}><summary><b>${HOME[d.a] || d.a} → ${HOME[d.b] || d.b}</b> <span class="small faint">changed: ${d.changed_layers.join(", ")}</span></summary>
            <p class="small"><b>Re-check:</b> ${d.invalidated_stages.map((x) => AXIS_LABEL[x] || x).join(", ")}. <b>Carries over:</b> ${d.kept_stages.map((x) => AXIS_LABEL[x] || x).join(", ")}.</p>
            <div class="tablewrap"><table class="qtable"><caption class="sr">Geometry settings that differ</caption><thead><tr><th scope="col">Setting</th><th scope="col">${short(d.a)}</th><th scope="col">${short(d.b)}</th></tr></thead><tbody>${d.geometry_knob_changes.map((k) => html`<tr><td data-label="Setting"><code class="small">${k.path}</code></td><td data-label="${short(d.a)}">${plain(k[d.a])}</td><td data-label="${short(d.b)}">${plain(k[d.b])}</td></tr>`)}</tbody></table></div></details>`)}
          <p class="small"><b>Change impact (hypothetical, in memory only):</b> altering the ${R.change_impact_example.changed_layers.join(", ")} pin would invalidate ${R.change_impact_example.invalidated_stages.map((x) => AXIS_LABEL[x] || x).join(", ")} and keep ${R.change_impact_example.kept_stages.map((x) => AXIS_LABEL[x] || x).join(", ")}. An unchanged second compile reused every stage.</p></section>
        <section class="panel" aria-labelledby="as-ctl"><h2 id="as-ctl">Typed failure controls</h2><ul class="small">
          ${Object.entries(R.controls).map(([k, c]) => html`<li><b>${k.replace(/_/g, " ")}</b>: expected ${c.expected}, got ${c.got}. ${(c.reason || []).map((r) => typeof r === "string" ? r : r.reason).join("; ")}</li>`)}</ul>
          <p class="small faint">Files: <a href="${B.report_path}">report.json</a> (sha256 ${U.sha(B.report_sha256)}) · ${ids.map((i) => html`<a href="${B.assemblies[i].path}">${short(i)}.json</a> `)}· <a href="${B.manifest}">manifest</a>${B.readme ? html` · <a href="${B.readme}">README</a>` : ""}</p></section>
        ${DF.genotype ? DF.genotype.panel(snap) : ""}`
    };
  };
})();
