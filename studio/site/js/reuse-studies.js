/* Recorded computational studies supplement the authored Project proposal.
 * Their manifest is checked during publication; they do not promote the Project's
 * biological claims or turn a generic engine benchmark into a tissue model. */
(function () {
  const DF = window.DF, { html } = DF, U = DF.ui;
  const cards = (snap, id) => ((snap.reuse_studies || {}).visuals || []).filter((v) => v.study === id);
  const num = (n) => Number.isFinite(n) ? n.toFixed(3) : "unknown";

  function denominators(d) {
    if (!d) return "";
    return html`<details class="reuse-diagnostic"><summary>Resolution check: inspect both denominators</summary>
      <p class="small">${d.note}</p><div class="tablewrap"><table><caption class="sr">The same two displacements expressed in physical and normalised units</caption>
      <thead><tr><th>Grid</th><th>Displacement</th><th>Centre span</th><th>Displacement / centre span</th><th>Displacement / outer length</th></tr></thead>
      <tbody>${["coarse", "fine"].map((k) => html`<tr><th>${k}</th><td>${num(d[k].net_disp_mm)} mm</td><td>${d[k].centre_span_mm} mm</td><td>${num(d[k].stored_normalised)}</td><td>${num(d[k].normalised_by_outer_length)} (${d[k].outer_length_mm} mm)</td></tr>`)}</tbody></table></div>
      <p class="small">Physical displacement differs by ${num(d.raw_si_difference_pct_of_coarse)}% of the coarse result. This pair does not establish convergence.</p></details>`;
  }

  function visual(v) {
    const files = Object.entries(v.media || {});
    return html`<article class="reuse-result" id="study-result-${v.id}"><h3>${v.title}</h3>
      <p class="small">${U.pill("recorded simulation", "grp")} ${v.evidence_kind}</p>
      ${v.summary ? html`<p>${v.summary}</p>` : ""}
      ${v.video_href ? html`<video class="reuse-video" controls playsinline preload="metadata" poster="${v.poster_href || ""}" aria-label="${v.title}"><source src="${v.video_href}" type="video/mp4">Your browser cannot play this video. <a href="${v.video_href}">Download the recording</a>.</video>` : ""}
      <p class="small faint">${v.labels.kind || ""} ${v.labels.time || ""}</p>
      ${v.labels.envelope_mm ? html`<p class="small">Toy envelope ${v.labels.envelope_mm.join(" × ")} mm; assumed mass ${v.labels.assumed_mass_g} g. These dimensions describe the numerical benchmark.</p>` : ""}
      ${v.biological_carrier ? html`<p class="note small"><b>Biological design: ${v.biological_carrier.status}.</b> ${v.biological_carrier.note}</p>` : ""}
      <ul class="small">${(v.caveats || []).map((s) => html`<li>${s}</li>`)}</ul>
      ${v.records_kept && v.records_kept.length ? html`<div class="note warn"><h4>Checks and unresolved results</h4><ul class="small">${v.records_kept.map((s) => html`<li>${s}</li>`)}</ul></div>` : ""}
      ${denominators(v.posthoc_denominators)}
      ${v.figure_href ? html`<details><summary>Compare trajectories and controls</summary><a href="${v.figure_href}"><img class="reuse-figure" src="${v.figure_href}" loading="lazy" alt="Recorded results and control comparisons for ${v.title}"></a></details>` : ""}
      <details><summary>Source files and recording provenance</summary><p class="small">Publication checked ${v.sources_verified} source files and ${v.renderer_verified} rendering files against the manifest. This establishes file identity, not biological validity.</p>
        ${v.engine_benchmark ? html`<p class="small">Engine: ${v.engine_benchmark.engine}. ${v.engine_benchmark.note || ""}</p>` : ""}
        <ul class="small">${files.map(([kind, f]) => html`<li><a href="${f.path}" download>${kind}</a> · ${f.bytes.toLocaleString()} bytes · ${U.sha(f.sha256)}</li>`)}</ul>
        ${(v.documents || []).map((d) => html`<p class="small"><a href="${d.href}">${d.title || d.href}</a></p>`)}</details>
      </article>`;
  }

  function render(snap, id) {
    const vs = cards(snap, id);
    if (!vs.length) return "";
    const m = snap.reuse_studies;
    return html`<section class="panel reuse-results" aria-labelledby="rs-results"><h2 id="rs-results">Recorded computational studies</h2>
      <p>These experiments test mechanisms and numerical assumptions relevant to the proposal. Their outcomes and failed controls remain visible; transfer to living tissue is a separate question.</p>
      ${vs.map(visual)}<p class="small"><a href="${m.manifest_href}">Recording manifest and source hashes</a> · ${U.sha(m.manifest_sha256)}</p></section>`;
  }
  DF.reuseStudies = { cards, render };
})();
