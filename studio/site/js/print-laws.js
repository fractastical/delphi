/* Exact print files -> governing equations, executed checks and unresolved assumptions. */
(function () {
  const DF = window.DF, { html } = DF, U = DF.ui;
  const number = (x, digits = 2) => typeof x === "number" && Number.isFinite(x) ? x.toFixed(digits) : "unknown";
  const words = (s) => String(s || "unknown").replace(/_/g, " ");
  const status = (s) => U.pill(words(s), /fail|withdrawn|not_cleared/.test(s) ? "no" : s === "pass" ? "ok" : "warn");
  const repoLink = (p) => "https://github.com/kganjam/delphi-frontier/blob/main/" + String(p).split("/").map(encodeURIComponent).join("/");
  const checks = (rows) => html`<ul class="print-checks">${(rows || []).map((c) => html`<li>${status(c.status)} <b>${words(c.id)}</b><p>${c.detail}</p></li>`)}</ul>`;

  function assemblyView(a) {
    if (!a) return html`<p class="note">This is a display or support artifact. No flight-mass budget or launch validation is assigned to it.</p>`;
    return html`<section class="panel" aria-labelledby="print-assembly"><h2 id="print-assembly">Whole assembly · ${a.revision}</h2>
      <p class="note warn">${status(a.launch_status.status)} ${a.launch_status.detail}</p>
      <div class="print-metrics"><div><b>${number(a.dry.mass_g)} g</b><span>Calculated dry assembly</span></div><div><b>${number(a.ballasted.total_mass_g)} g</b><span>With modeled ballast</span></div><div><b>${number(a.ballasted.ballast_g)} g</b><span>Ballast to CG x ${number(a.ballasted.target_cg_x_mm, 1)} mm</span></div></div>
      <p class="small">${a.dry.basis} ${a.ballasted.basis}</p>
      <div class="tablewrap"><table class="qtable"><caption>Mass budgets and their exact assumptions</caption><thead><tr><th scope="col">Budget</th><th scope="col">Limit</th><th scope="col">Compared mass</th><th scope="col">Result</th><th scope="col">Basis</th></tr></thead><tbody>${a.budgets.map((b) => html`<tr><th scope="row">${words(b.id)}</th><td data-label="Limit">${number(b.value_g)} g</td><td data-label="Compared mass">${number(b.compared_mass_g)} g</td><td data-label="Result">${status(b.verdict)}</td><td data-label="Basis">${b.basis}</td></tr>`)}</tbody></table></div>
      <details><summary>Inspect nominal parts and assembly checks</summary><ul>${a.nominal_file_paths.map((p) => html`<li><a href="${DF.href("/print-laws", { file: p })}">${p.split("/").pop()}</a></li>`)}</ul>${checks(a.checks)}<p>${a.flight_status}</p></details></section>`;
  }

  DF.views["print-laws"] = function (snap, route) {
    const P = snap.print_laws;
    const header = html`<section class="pagehead"><p class="eyebrow"><a href="${DF.href("/home")}">Studio</a> / printable models</p><h1>Print laws & checks</h1><p class="lede">Trace a particular file to the equations, material assumptions and checks behind it. A law can explain why a design fails.</p></section>`;
    if (!P || !P.data) return { html: html`${header}<p class="empty">The checked print-law index is unavailable. No grounding or pass result is inferred.${P && P.refused.length ? " File integrity checks refused this index." : ""}</p>` };
    const D = P.data;
    const wanted = route.params.file || "artifacts/glider/r4-daane-printfix/stl/body.stl";
    const f = D.files.find((x) => x.path === wanted);
    if (!f) return { html: html`${header}<p class="empty">This file is not in the checked index: ${wanted}. <a href="${DF.href("/print-laws")}">Open the current prototype</a>.</p>` };
    const a = D.assemblies.find((x) => x.revision === f.revision);
    const revisions = [...new Set(D.files.map((x) => x.revision))];
    const laws = new Map(D.laws.map((l) => [l.id, l]));
    const findings = D.findings.filter((x) => x.applies_to.includes(f.revision) || x.applies_to.includes(f.path) || x.applies_to.includes(f.family));
    return {
      html: html`${header}<section class="panel print-picker"><label for="print-file"><b>Inspect a file</b></label><select id="print-file">${revisions.map((rev) => html`<optgroup label="${rev}">${D.files.filter((x) => x.revision === rev).map((x) => html`<option value="${x.path}" ${x.path === f.path ? DF.raw("selected") : ""}>${x.path.split("/").pop()}${x.withdrawn ? " · withdrawn" : ""}</option>`)}</optgroup>`)}</select><p class="small">${D.files.length} exact files indexed. ${D.grounding_note}</p></section>
        ${assemblyView(a)}
        <section class="panel" aria-labelledby="print-file-title"><h2 id="print-file-title">${f.path.split("/").pop()}</h2><p>${words(f.kind)} · ${f.revision}</p>
          ${f.withdrawn ? html`<p class="note warn"><b>Withdrawn.</b> ${f.withdrawn}</p>` : html`<p><a class="btn" href="${f.path}" download>Download this file</a></p>`}
          <p class="print-file-hash"><b>SHA-256</b> <code>${f.sha256}</code></p>
          <div class="print-metrics"><div><b>${number(f.volume_mm3)} mm³</b><span>Calculated mesh volume</span></div><div><b>${number(f.mass_g)}${f.mass_g === null ? "" : " g"}</b><span>Calculated part mass</span></div><div><b>${number(f.material.density_kg_m3, 0)} kg/m³</b><span>Scenario material density</span></div></div>
          <p>${f.mass_basis}</p><p class="small">${f.material.status}${DF.safeUrl(f.material.source_url) ? html` <a href="${DF.safeUrl(f.material.source_url)}" target="_blank" rel="noopener noreferrer">Manufacturer source</a>` : ""}</p>
          <h3>Checks on this file</h3>${checks(f.checks)}</section>
        ${findings.length ? html`<section class="panel"><h2>Unresolved findings and revision context</h2><ul>${findings.map((x) => html`<li><b>${words(x.status)}:</b> ${x.detail}</li>`)}</ul></section>` : ""}
        <section class="panel"><h2>Equations and design rules</h2><p>Each relationship says whether a law computed a result, a check ran, or an idea only informed the shape.</p><div class="print-law-grid">${f.law_relations.map((r) => { const l = laws.get(r.law_id); return l ? html`<article class="card"><h3>${l.title}</h3>${status(r.relation)} <span class="small">${words(l.kind)}</span><div class="print-equation">${DF.texSpan(l.latex, true)}</div><p>${r.detail}</p><p class="small">${l.scope}</p><details><summary>Sources and implementation</summary><ul>${l.source_urls.filter(DF.safeUrl).map((url) => html`<li><a href="${url}" target="_blank" rel="noopener noreferrer">${new URL(url).hostname}</a></li>`)}${l.code_paths.map((p) => html`<li><a href="${repoLink(p)}" target="_blank" rel="noopener noreferrer">${p}</a></li>`)}</ul></details></article>` : ""; })}</div></section>
        <section class="panel"><h2>Evidence and lineage</h2><ul class="print-sources">${f.source_artifacts.map((s) => html`<li><b>${s.role}</b> · <a href="${repoLink(s.path)}" target="_blank" rel="noopener noreferrer">${s.path}</a>${s.sha256 ? html`<code>${s.sha256}</code>` : ""}</li>`)}</ul><p><a href="${P.href}">Download the complete law/check index</a> · <a href="${DF.href("/assemblies")}">Biological assembly gaps</a> · <a href="${DF.href("/experimentation")}">Plan the next measurement</a></p></section>`,
      after(root) { root.querySelector("#print-file").addEventListener("change", (e) => DF.go(DF.href("/print-laws", { file: e.target.value }))); }
    };
  };
})();
