/* Recorded computational studies supplement the authored Project proposal.
 * Their manifest is checked during publication; they do not promote the Project's
 * biological claims or turn a generic engine benchmark into a tissue model. */
(function () {
  const DF = window.DF, { html } = DF, U = DF.ui;
  const cards = (snap, id) => ((snap.reuse_studies || {}).visuals || []).filter((v) => v.study === id);
  function brief(snap, p) {
    if (!cards(snap, p.id).length) return p.summary;
    if (p.id === "epithelial-repair") return "Use a cultured epithelial sheet as a bounded test of multiscale design. Recorded Cellular Potts runs compare motility and mechanics; calibrating them against tissue measurements remains an open problem.";
    if (p.id === "tissue-microcarrier") return "Explore how contraction, geometry and transport could shape a small tissue carrier. The numerical benchmark tests prescribed actuation in a generic soft body; linking it to living tissue remains an open problem.";
    return p.summary;
  }
  const num = (n) => Number.isFinite(n) ? n.toFixed(3) : "unknown";
  const pct = (n) => Number.isFinite(n) ? (100 * n).toFixed(2) + "%" : "unknown";

  function summary(s) {
    if (!s) return "";
    if (typeof s === "string") return html`<p>${s}</p>`;
    const g = s.gates && s.gates.strict;
    return html`${s.pair ? html`<div class="tablewrap"><table><caption>Gap closure within the recorded horizon (${s.pair.same})</caption><thead><tr><th>Condition</th><th>Gap fraction closed</th></tr></thead><tbody>
      <tr><th>Protrusion enabled</th><td>${pct(s.pair.closes.closed_fraction)}</td></tr>
      <tr><th>Protrusion disabled</th><td>${pct(s.pair.arrests.closed_fraction)}</td></tr>
      ${s.passive_floor ? html`<tr><th>Separate control: both drives off</th><td>${pct(s.passive_floor.closed_fraction)}</td></tr>` : ""}</tbody></table></div>` : ""}
      ${s.passive_floor ? html`<p class="small">${s.passive_floor.reading}</p>` : ""}
      ${g ? html`<p class="small"><b>Reviewed checks:</b> ${g.pass} pass; ${g.fail} fail; ${(g.descriptive || []).join(", ")} descriptive; ${(g.incomplete_or_unevaluable || []).join(", ")} incomplete or unevaluable. The original reported statuses remain in the source history.</p>` : ""}
      <details><summary>Threshold hypothesis, readout coverage and time limits</summary>
        ${s.j_scaling ? html`<p class="small"><b>Held-out comparison.</b> Predicted interval (${s.j_scaling.predicted_interval.join(", ")}); observed threshold bracket (${s.j_scaling.observed_bracket.join(", ")}). ${s.j_scaling.scope}.</p>` : ""}
        ${s.readout_check ? html`<p class="small">${s.readout_check.G1b}</p>` : ""}
        ${s.gap_size_scaling ? html`<p class="small"><b>Gap-size scaling:</b> ${s.gap_size_scaling}</p>` : ""}
        ${s.horizon ? html`<p class="small">${s.horizon}</p>` : ""}</details>`;
  }

  function oxygen(snap, id) {
    const f = ((snap.lean_gallery || {}).families || []).find((x) => x.id === "steady-oxygen-bound");
    if (!f || f.status !== "current" || !f.contextual_reuse) return "";
    const ctx = (f.contextual_reuse.contexts || []).find((x) => x.project_id === "project-" + id);
    if (!ctx) return "";
    const p = snap.projects.projects.find((x) => x.id === id);
    const live = p && ((snap.project_drafts || {})[p.draft_key] || {}).live_ref;
    if (!live || ["namespace", "kind", "id", "version"].some((k) => live[k] !== ctx.project_ref[k])) return "";
    return html`<section class="panel" aria-labelledby="rs-rule"><h2 id="rs-rule">A shared design constraint: oxygen transport</h2>
      <p>${ctx.use}</p><div class="reuse-equations"><div>${DF.texSpan("aR^2 \\leq 6DC_0 \\quad \\text{(sphere)}", true)}</div><div>${DF.texSpan("aL^2 \\leq 2DC_0 \\quad \\text{(slab)}", true)}</div></div>
      <p class="small">Steady diffusion with uniform positive consumption (a &gt; 0), D &gt; 0 and a fixed supplied boundary C₀ ≥ 0. R is sphere radius; L is the distance from a slab's centre to its supplied face. The bounds keep the model's centre concentration nonnegative.</p>
      <p class="note small">Project-specific diffusivity D, oxygen consumption a and boundary concentration C₀ are <b>unknown</b>. The proof is conditional mathematics; it does not establish tissue viability.</p>
      <p><a class="btn ghost" href="#/proofs?f=steady-oxygen-bound">Inspect Lean source and mutation checks</a></p>
      ${f.figure_href ? html`<details><summary>See the sphere and slab model</summary><img class="reuse-figure" src="${f.figure_href}" loading="lazy" alt="Idealised sphere and slab oxygen diffusion bounds"></details>` : ""}
      <details><summary>Applicability and exact reuse context</summary><ul class="small">${(ctx.not_established || []).map((x) => html`<li>${x}</li>`)}</ul>
        <p class="small"><a href="${f.rule_contract_href}">Rule contract and source context</a> · <a href="${f.reuse_context_href}">Exact Project attachment</a></p></details></section>`;
  }

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
      <div class="reuse-media${v.video_arrest_href ? " reuse-pair" : ""}">
      ${v.video_href ? html`<figure>${v.video_arrest_href ? html`<figcaption>Baseline: protrusion enabled</figcaption>` : ""}<video class="reuse-video" controls playsinline preload="metadata" poster="${v.poster_href || ""}" aria-label="${v.title}"><source src="${v.video_href}" type="video/mp4">Your browser cannot play this video. <a href="${v.video_href}">Download the recording</a>.</video></figure>` : ""}
      ${v.video_arrest_href ? html`<figure><figcaption>Control: protrusion disabled</figcaption><video class="reuse-video" controls playsinline preload="metadata" poster="${v.poster_arrest_href || ""}" aria-label="Protrusion-disabled control for ${v.title}"><source src="${v.video_arrest_href}" type="video/mp4"><a href="${v.video_arrest_href}">Download the control recording</a>.</video></figure>` : ""}</div>
      <p class="small faint">${v.labels.kind || ""} ${v.labels.time || ""}</p>
      ${v.labels.envelope_mm ? html`<p class="small">Toy envelope ${v.labels.envelope_mm.join(" × ")} mm; assumed mass ${v.labels.assumed_mass_g} g. These dimensions describe the numerical benchmark.</p>` : ""}
      ${v.biological_carrier ? html`<p class="note small"><b>Biological design: ${v.biological_carrier.status}.</b> ${v.biological_carrier.note}</p>` : ""}
      ${summary(v.summary)}
      <ul class="small">${(v.caveats || []).map((s) => html`<li>${s}</li>`)}</ul>
      ${v.records_kept && v.records_kept.length ? html`<div class="note warn"><h4>Checks and unresolved results</h4><ul class="small">${v.records_kept.map((s) => html`<li>${s}</li>`)}</ul></div>` : ""}
      ${v.errata_href ? html`<p class="note small"><b>Review corrections:</b> <a href="${v.errata_href}">Read the reporting and validation qualifications</a> alongside the original results.</p>` : ""}
      ${denominators(v.posthoc_denominators)}
      ${v.figure_href ? html`<details><summary>Compare trajectories and controls</summary><a href="${v.figure_href}"><img class="reuse-figure" src="${v.figure_href}" loading="lazy" alt="Recorded results and control comparisons for ${v.title}"></a></details>` : ""}
      <details><summary>Source files and recording provenance</summary><p class="small">Publication checked ${v.sources_verified} source files and ${v.renderer_verified} rendering files against the manifest. This establishes file identity, not biological validity.</p>
        ${v.engine_benchmark ? html`<p class="small">Engine: ${v.engine_benchmark.engine}. ${v.engine_benchmark.note || ""}</p>` : ""}
        <ul class="small">${files.map(([kind, f]) => html`<li><a href="${f.path}" download>${kind}</a> · ${f.bytes.toLocaleString()} bytes · ${U.sha(f.sha256)}</li>`)}</ul>
        ${(v.downloads || []).map((d) => html`<p class="small"><a href="${d.href}">${d.label || d.href}</a> · ${U.sha(d.sha256)}</p>`)}</details>
      </article>`;
  }

  function followup(snap, id) {
    const f = (snap.reuse_studies || {}).sweep_followup;
    if (!f || f.study !== id) return "";
    const proof = ((snap.lean_gallery || {}).families || []).find((x) => x.id === "scaled-threshold-intervals" && x.status === "current");
    return html`<details class="reuse-followup note warn" id="rs-followup"><summary><b>Later experiment: ${f.complete_arms} runs challenge the proposed scaling rule</b></summary>
      <h3>A local pass did not generalise across the tested range</h3>
      <p>The earlier single-doubling comparison remains a local pass. A subsequent, wider sweep completed ${f.complete_arms} model runs and returned <b>${f.verdict}</b> against its frozen scaling criterion. Its result concerns closure observed at logged times through ${f.horizon} model-time units.</p>
      <p>The hypothesis was that the operational threshold λ*<sub>V</sub>/J stays within a factor of two. Independent review checked the full threshold intervals: even the closest compatible choices exceed that tolerance.</p>
      <p class="small">In this two-dimensional model, J sets cell–medium contact energy and λ<sub>V</sub> penalises departures from target cell area. Mapping these parameters to a tissue intervention remains an open problem.</p>
      <div class="tablewrap"><table><caption>Recorded interval evidence; these are model results</caption><thead><tr><th>Gap setting k</th><th>Minimum feasible spread</th><th>Frozen tolerance</th><th>Original summary spread</th></tr></thead><tbody>
        ${f.rows.map((r) => html`<tr><th>${r.gap}</th><td>${r.minimum_spread}×</td><td>${r.tolerance}×</td><td>${r.native_summary_spread}×</td></tr>`)}</tbody></table></div>
      ${proof ? html`<p><a class="btn ghost" href="#/proofs?f=scaled-threshold-intervals">Inspect the conditional Lean certificate</a></p><p class="small">The certificate checks the interval implication using source-bound endpoints. It does not prove the simulator, extraction of the intervals, or biological validity.</p>` : ""}
      <figure><a href="${f.figure_href}"><img class="reuse-figure" src="${f.figure_href}" loading="lazy" alt="Recorded threshold intervals across the tested adhesion settings, compared with proportional scaling"></a>
        <figcaption class="small"><a href="${f.figure_href}">Open full-size figure</a>. Intervals from the returned simulation logs. The interval calculation is an additional review; it does not replace the frozen criterion.</figcaption></figure>
      <p class="small"><b>Design consequence:</b> do not use this proportional rule as a control knob over the tested range. Longer-horizon closure, untested parameter values, numerical refinement and transfer to living tissue remain unknown.</p>
      <p class="small">The videos below are the earlier 36-run study. This followup returned cell-centre and volume logs, but no lattice frames defining cell shapes or the wound boundary; no new tissue-shape movie is claimed.</p>
      <details><summary>Evidence, independent review and history</summary><p class="small">Source ${U.sha(f.source_commit)}. The independent review names ${U.sha(f.reviewed_source_commit)}; the published interval values were compared with that review. Later reporting corrections retain the original numerical result.</p>
        <ul class="small">${f.downloads.map((d) => html`<li><a href="${d.href}">${d.label}</a> · ${U.sha(d.sha256)}</li>`)}</ul>
        <p class="small"><a href="${f.manifest_href}">Exact publication inputs and hashes</a> · ${U.sha(f.manifest_sha256)}</p></details>
    </details>`;
  }

  function render(snap, id) {
    const vs = cards(snap, id);
    if (!vs.length) return "";
    const m = snap.reuse_studies;
    return html`<section class="panel reuse-results" aria-labelledby="rs-results"><h2 id="rs-results">Recorded computational studies</h2>
      <p>These experiments test mechanisms and numerical assumptions relevant to the proposal. Their outcomes and failed controls remain visible; transfer to living tissue is a separate question.</p>
      ${followup(snap, id)}
      ${vs.map(visual)}<p class="small"><a href="${m.manifest_href}">Recording manifest and source hashes</a> · ${U.sha(m.manifest_sha256)}</p>
      ${m.record_links && m.record_links.groups[id] ? html`<h3>Explore the shared frontier</h3><p class="small">Related versioned claims, evidence and open problems. These records remain unreviewed; the recorded mathematics and numerical checks retain their stated scope.</p>
        <ul class="small">${m.record_links.groups[id].map((r) => html`<li><a href="${DF.href("/entity/" + r.ref.kind + "/" + r.ref.id, {v: r.ref.version, ns: r.ref.namespace})}">${r.title}</a> ${U.pill(r.ref.kind, "grp")}</li>`)}</ul>
        <p class="small"><a href="${m.record_links.receipt_href}">Exact public readback receipt</a></p>` : ""}</section>`;
  }
  DF.reuseStudies = { cards, render, oxygen, brief };
})();
