/* Ecology scenarios: the saved-state trajectory viewer (js/ecology-viewer.js) plus the run's own receipts. States are played as saved; every number comes
 * from the published run files. Computed reduced-model scenarios, not CFD, not measured flying-fish performance, not a validated nervous system. */
(function () {
  const DF = window.DF; const { html, esc } = DF; const U = DF.ui;
  const LABEL = { "glide-passive": "Passive glide", "glide-feedback": "Feedback glide", "escape-neighbors": "Escape, with neighbours", "escape-no-neighbors": "Escape, no neighbours (ablation)" };
  const n = (x, d = 4) => (typeof x === "number" ? String(Number(x.toPrecision(d))) : "not stated");

  DF.views.ecology = function (snap) {
    const E = snap.ecology;
    if (!E) return { html: html`<section class="pagehead"><h1>Ecology scenarios</h1><p class="empty">The ecology run files are not in this snapshot, so nothing is shown.</p></section>` };
    const ok = E.cases.every((c) => c.trajectory) && E.mesh && E.panels;
    return {
      html: html`<section class="pagehead"><h1>Ecology scenarios</h1><p class="lede">Four bounded airborne scenarios of the v3a biological candidate, integrated by MuJoCo from per-fin quasi-steady forces and assumed drag. The viewer plays the states the solver saved.</p></section>
        <section class="panel"><p class="note warn small"><b>${U.pill("computed reduced model", "warn")} ${U.pill("empirical validation: " + (E.empirical_validation || "unknown"), "warn")}</b> ${esc(E.status)}. ${esc(E.engine)}. The mass, centre of gravity, inertia, drag, hinges and controller are engineering assumptions, not measurements of a fish or of the print resin. Biological success probability: ${E.biological_success_probability === null ? "null (none is claimed)" : esc(String(E.biological_success_probability))}. A school response flag is an encoded rule, not a neural circuit or measured survival. Mesh source units are metres (${esc(E.geometry.source_component_units)}).</p></section>
        <section class="panel" aria-labelledby="eco-v"><h2 id="eco-v">Saved-state viewer</h2>${ok ? html`<div id="eco-host" aria-label="Ecology trajectory viewer"></div>` : html`<p class="empty">A trajectory, the mesh or the panel file did not match its declared hash (${esc(E.refused.join(", "))}), so the viewer is not offered.</p>`}</section>
        <section class="panel" aria-labelledby="eco-r"><h2 id="eco-r">What each run ended on (from summary.json)</h2><div class="tablewrap"><table class="qtable"><caption class="sr">Per-scenario run receipts</caption><thead><tr><th scope="col">Scenario</th><th scope="col">Ended at (s)</th><th scope="col">Reason</th><th scope="col">Planned duration reached</th><th scope="col">Half-step: max position / orientation difference</th><th scope="col">Frozen bounds</th><th scope="col">Trajectory sha256</th></tr></thead><tbody>
          ${E.cases.map((c) => { const m = c.summary.main, d = c.summary.discrepancy; return html`<tr id="eco-${c.id}"><td data-label="Scenario"><b>${LABEL[c.id] || c.id}</b></td><td data-label="Ended at">${n(m.last_time_s)}</td><td data-label="Reason" class="small">${m.termination_reason}</td><td data-label="Planned duration">${m.completed_duration ? "yes" : "no"}</td><td data-label="Half-step">${n(d.max_position_difference_m)} m / ${n(d.max_orientation_angle_rad)} rad</td><td data-label="Frozen bounds">${d.passes_frozen_discrepancy_bounds ? "pass" : "fail"}</td><td data-label="sha256" class="small">${U.sha(c.trajectory_sha256)}</td></tr>`; })}</tbody></table></div>
          <p class="small faint">A run that ends at the water interface or at the edge of the reused VLM domain is a stop, not a result beyond it: no water physics follows and no force is extrapolated. Half-step columns compare only the common saved times.</p></section>
        <section class="panel" aria-labelledby="eco-m"><h2 id="eco-m">Rendered movies (from the same saved states)</h2><div class="mediagrid">${E.media.map((m) => html`<figure><video controls preload="none" poster="${m.poster}" width="640"><source src="${m.video}" type="video/mp4"></video><figcaption class="small">${m.id} · ${m.frames} frames. ${esc(m.frame_method || "")} Render receipt: <a href="${m.provenance}">${m.provenance.split("/").pop()}</a>. <a href="${m.video}" download>Download MP4</a></figcaption></figure>`)}</div></section>
        <section class="panel" aria-labelledby="eco-f"><h2 id="eco-f">Files, failures kept</h2><ul class="small"><li><a href="${E.receipts.summary}">summary.json</a> · <a href="${E.receipts.controls}">controls.json</a> · <a href="${E.receipts.receipt}">receipt.json</a> · <a href="artifacts/ecology/geometry-manifest.json">geometry-manifest.json</a> · <a href="artifacts/ecology/RESULTS.md">RESULTS.md</a></li>
          ${(E.history || []).map((h) => html`<li><code>${h.path}</code>: ${h.status}</li>`)}</ul>${(E.limits || []).length ? html`<h3>Limits stated by the interface</h3><ul class="small">${E.limits.map((l) => html`<li>${typeof l === "string" ? l : JSON.stringify(l)}</li>`)}</ul>` : ""}</section>`,
      async after(root) {
        const host = root.querySelector("#eco-host"); if (!host) return;
        try {
          const { mountEcologyViewer } = await import(new URL("js/ecology-viewer.js", document.baseURI).href);
          const rec = (id) => [{ label: "run summary", url: E.receipts.summary, select: id }, { label: "controls", url: E.receipts.controls }, { label: "simulation receipt", url: E.receipts.receipt }];
          const v = mountEcologyViewer(host, { cases: E.cases.map((c) => ({ id: c.id, label: LABEL[c.id] || c.id, url: c.trajectory, receipts: rec(c.id) })), meshUrl: E.mesh, panelsUrl: E.panels });
          window.addEventListener("hashchange", () => v.destroy(), { once: true });
        } catch (e) { host.textContent = "The viewer could not start: " + (e && e.message ? e.message : "unknown error") + ". The receipts below are unaffected."; }
      }
    };
  };
})();
