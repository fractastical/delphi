/* Simulations gallery: manifest-only cards. A video element exists only when a video file is present and matches its declared sha256. */
(function () {
  const DF = window.DF; const { html, raw, esc, fmt } = DF; const U = DF.ui;
  const evidenceHref = (u) => typeof u === "string" && /^artifacts\/[A-Za-z0-9_./-]+$/.test(u) && !u.split("/").includes("..") ? u : DF.safeUrl(u);

  function glideCard(snap) {
    const S = snap.simulation; if (!S) return null; const m = S.summary; const f = S.findings || {}; const c = S.controls || {};
    const fig = (S.files || []).find((x) => x.name === "figure.png");
    return { id: "glide-pointmass", derived: true, title: `Glide of a point mass (${m.model_version})`, scales: ["organism"], evidence_kind: m.evidence_kind,
      model: { name: m.model_version, context: "Constant-coefficient point-mass glide from a 1 m release; designs sampled over wing loading and aspect ratio, ranges by Monte Carlo over coefficient priors." },
      time: { units: "not stated in the summary; see engineering/simulation/PROTOCOL.md", note: "The time series file is indexed but not read by this page." },
      video_state: "none", poster_href: fig ? fig.href : null, poster_is_figure: true,
      numerical_checks: [...Object.entries(c).filter(([k, v]) => v && typeof v === "object").map(([k, v]) => ({ name: k.replace(/_/g, " "), result: "within tolerance", tolerance: v.tol })), { name: "step-halving across all designs", result: `max range difference ${fmt(m.max_dt_half_rel_diff, 3)}; ${m.n_unconverged} unconverged` }],
      parameter_unknowns: Object.entries(m.priors || {}).map(([k, v]) => `${k}: unknown, sampled over ${v[0]} to ${v[1]}`).concat(["Air density and the nominal coefficients are assumptions, not measurements."]),
      open_questions: [f.interpretation || "See the findings file.", "Which sourced release speed and drag polar would replace the model's conventions?"],
      couplings: [], files: S.files };
  }

  function chain(snap, card) {
    const sc = snap.mission.scales; const have = new Set(card.scales || []); const links = card.couplings && card.couplings.length ? card.couplings : snap.mission.couplings;
    const stat = (a, b) => { const l = links.find((x) => (x.from === a && x.to === b) || (x.from === b && x.to === a)); return l ? l.status : "absent"; };
    const W = 70, H = 96; let g = "";
    sc.forEach((s, i) => {
      const x = 30 + i * W; const on = have.has(s.key);
      if (i) { const st = stat(sc[i - 1].key, s.key); g += `<line x1="${x - W + 9}" y1="30" x2="${x - 9}" y2="30" class="cl ${st === "absent" ? "unk" : "ok"}"><title>${esc(sc[i - 1].label)} to ${esc(s.label)}: ${st === "absent" ? "unknown bridge, no executable coupling" : st}</title></line>`; }
      g += `<g><circle cx="${x}" cy="30" r="9" class="cn ${on ? "on" : ""}"/><text x="${x}" y="34" text-anchor="middle" class="cnum">${i + 1}</text><text x="${x}" y="60" text-anchor="middle" class="clab">${esc(s.label.split(" /")[0].slice(0, 11))}</text></g>`;
    });
    return `<svg viewBox="0 0 ${30 + sc.length * W} ${H - 24}" class="chain" role="img" aria-label="The eleven scales in order. Filled circles are scales this simulation runs at; dashed links are unknown bridges with no executable coupling."><desc>Solid link: a coupling is recorded. Dashed link: unknown bridge.</desc>${g}</svg>`;
  }

  function card(snap, c) {
    const scl = (c.scales || []).map((k) => (snap.mission.scales.find((s) => s.key === k) || { label: k }).label);
    const vs = c.video_state; const hasV = (vs === "present_verified" || vs === "present_unpinned") && c.video_href;
    const media = hasV ? html`<video controls playsinline preload="none" ${c.poster_href ? html`poster="${c.poster_href}"` : ""} src="${c.video_href}" aria-label="${c.title}"></video>${c.caption ? html`<p class="small"><b>Caption burned into every frame:</b> ${c.caption}</p>` : ""}<p class="small faint">${vs === "present_unpinned" ? "No sha256 is declared for this file, so it is shown without a digest check." : "Verified against its declared sha256."} ${c.video && c.video.note ? c.video.note : ""} <a class="btn small ghost" href="${c.video_href}" download>Download video</a></p>`
      : html`<div class="novideo">${c.poster_href ? html`<img src="${c.poster_href}" alt="${c.poster_is_figure ? "Recorded figure (not a video)" : "Poster frame"}" loading="lazy">` : ""}<p><b>No video file.</b> ${{ none: "None has been provided for this artifact.", declared_but_missing: "A video is declared in the manifest but the file is not present.", digest_mismatch: "A video file is present but does not match its declared sha256, so it is not offered." }[vs] || ""} ${c.poster_is_figure ? "The image is a recorded figure, not a frame of a video." : ""}</p></div>`;
    const list = (a, empty) => (a && a.length ? html`<ul>${a.map((x) => html`<li>${typeof x === "string" ? x : x.name ? html`<b>${x.name}</b>: ${x.result || ""}${x.tolerance !== undefined ? html` <span class="faint">(tolerance ${x.tolerance})</span>` : ""}` : JSON.stringify(x)}</li>`)}</ul>` : html`<p class="faint small">${empty}</p>`);
    return html`<article class="simcard" id="sim-${c.id}"><div class="simhead"><h3>${c.title}</h3><p>${(scl.length ? scl : ["scale not stated"]).map((x) => U.pill(x, "grp"))} ${U.pill(c.evidence_kind || "evidence kind not stated", "ev")} ${c.derived ? U.pill("derived from recorded results; no manifest file", "warn") : U.pill("manifest", "cur")}</p></div>
      ${c.error ? html`<p class="empty">${c.error} (${c.manifest})</p>` : html`<div class="simmedia">${media}</div>
      <dl class="kv"><div><dt>Model</dt><dd>${(c.model && c.model.name) || "not stated"}</dd></div><div><dt>Time units</dt><dd>${(c.time && c.time.units) || "not stated"}</dd></div></dl>
      <p class="small">${(c.model && c.model.context) || ""} ${(c.time && c.time.note) || ""}</p>
      ${evidenceHref(c.plot_href) || evidenceHref(c.provenance_href) ? html`<p class="small sim-artifacts">${evidenceHref(c.plot_href) ? html`<a href="${evidenceHref(c.plot_href)}">View result chart</a>` : ""}${evidenceHref(c.plot_href) && evidenceHref(c.provenance_href) ? " · " : ""}${evidenceHref(c.provenance_href) ? html`<a href="${evidenceHref(c.provenance_href)}">Inspect rendering provenance</a>` : ""}</p>` : ""}
      ${(c.figures || []).filter((f) => evidenceHref(f.href)).map((f) => html`<details class="simdet"><summary>${f.label}${f.posthoc ? " · posthoc" : ""}</summary><a href="${evidenceHref(f.href)}"><img src="${evidenceHref(f.href)}" alt="${f.label}" loading="lazy" style="max-width:100%;height:auto"></a><p class="small faint">${f.bytes.toLocaleString()} bytes · ${U.sha(f.sha256)}</p></details>`)}
      ${(c.reports || []).length ? html`<details class="simdet"><summary>Reports and recorded data</summary><ul class="small">${c.reports.filter((f) => evidenceHref(f.href)).map((f) => html`<li><a href="${evidenceHref(f.href)}">${f.label}</a>${f.posthoc ? " · posthoc" : ""} · ${U.sha(f.sha256)}</li>`)}</ul></details>` : ""}
      <details class="simdet"><summary><b>Checks, unknowns, open questions and couplings</b> <span class="faint small">${(c.numerical_checks || []).length} check${(c.numerical_checks || []).length === 1 ? "" : "s"} · ${(c.parameter_unknowns || []).length} unknown${(c.parameter_unknowns || []).length === 1 ? "" : "s"} · ${(c.open_questions || []).length} open</span></summary>
      <h4>Numerical checks</h4>${list(c.numerical_checks, "No numerical check is recorded.")}
      <h4>Parameter unknowns</h4>${list(c.parameter_unknowns, "None stated, which is not the same as none.")}
      <h4>Open questions</h4>${list(c.open_questions, "None stated.")}
      <h4>Coupling between scales</h4><div class="chainwrap">${DF.raw(chain(snap, c))}</div><p class="small faint">Filled circle: a scale this artifact runs at. Dashed link: unknown bridge (no executable coupling recorded).</p></details>
      ${(c.limitations || []).length ? html`<div class="note small warn"><b>Limitations.</b><ul>${c.limitations.map((x) => html`<li>${x}</li>`)}</ul></div>` : ""}
      ${(c.equations || []).length || (c.sources || []).length ? html`<details class="simdet sim-sources"><summary><b>${(c.equations || []).length ? "Equations and sources" : "Sources and provenance"}</b> <span class="faint small">${(c.equations || []).length} equations · ${(c.sources || []).length} source${(c.sources || []).length === 1 ? "" : "s"}</span></summary>
        ${(c.equations || []).map((q) => html`<div class="eqcard"><h4>${q.label}</h4><div class="eq-math">${DF.texSpan(q.tex, true)}</div><p class="small faint">${q.source}</p></div>`)}
        <h4>Sources</h4><ul class="small">${(c.sources || []).map((x) => html`<li>${evidenceHref(x.href) ? html`<a href="${evidenceHref(x.href)}">${x.label}</a>` : x.label}<br><span class="faint">${x.locator}</span></li>`)}</ul></details>` : ""}
      ${c.files && c.files.length ? html`<p class="small">Files: ${c.files.map((f) => html`<a href="${f.href}">${f.name}</a> (${f.bytes} bytes, ${U.sha(f.sha256)}) `)}</p>` : ""}
      <p class="small faint">${evidenceHref(c.manifest_href) ? html`<a href="${evidenceHref(c.manifest_href)}">Inspect model manifest</a>` : c.manifest ? "Manifest: " + c.manifest : ""}</p>`}</article>`;
  }

  function couplingSection(snap) {
    const M = snap.coupling_manifest;
    if (!M) return html`<section class="panel"><h2>Couplings between the models</h2><p class="empty">No coupling manifest is present in this tree (looked for <code>engineering/COUPLING_MANIFEST.json</code>). Nothing is shown in its place.</p></section>`;
    const tone = { composable: "ok", scenario: "warn", refused: "no" };
    const mdl = Object.fromEntries(M.models.map((m) => [m.id, m]));
    return html`<section class="panel" aria-labelledby="cp-h"><h2 id="cp-h">Couplings between the models</h2>
      <p class="note warn"><b>${M.scope}</b></p>
      <p class="small">${U.pill(M.counts.composable + " composable", "ok")} ${U.pill(M.counts.scenario + " scenario (assumption-level)", "warn")} ${U.pill(M.counts.refused + " refused", "no")} ${U.pill("registered calibrations: " + (M.calibrations_registered.length || "none"), "st-unk")} · timescale separation threshold ${M.timescale_separation}</p>
      <div class="tablewrap"><table><thead><tr><th>Coupling</th><th>From → to</th><th>Mapping</th><th>Verdict</th><th>Why</th></tr></thead><tbody>${M.couplings.map((c) => html`<tr><td><code>${c.id}</code></td><td class="small">${c.from}<br>→ ${c.to}</td><td class="small">${c.mapping_kind || "none"}; time ${c.time_relation}; uncertainty ${c.uncertainty_kind}</td><td>${U.pill(c.status, tone[c.status] || "st-unk")}<br><span class="small">${c.label}</span></td>
        <td class="small">${(c.reasons || []).length ? html`<ul>${c.reasons.map((x) => html`<li>${x}</li>`)}</ul>` : "none"}${(c.assumption_ids || []).length ? html`<b>Assumes</b> ${c.assumption_ids.join(", ")}.` : ""}${(c.missing_calibrations || []).length ? html`<details><summary>Missing calibrations (${c.missing_calibrations.length})</summary><ul>${c.missing_calibrations.map((x) => html`<li>${x}</li>`)}</ul></details>` : ""}</td></tr>`)}</tbody></table></div>
      <h3>Assumptions behind the scenario rows</h3><ul>${M.assumptions.map((a) => html`<li><b>${a.id}</b> (${a.level}, ${a.owner}): ${a.text}</li>`)}</ul>
      <h3>Models in the manifest</h3><div class="tablewrap"><table><thead><tr><th>Model</th><th>Status</th><th>Ports</th><th>Not established</th></tr></thead><tbody>${M.models.map((m) => html`<tr><td>${m.name}<br><code class="small">${m.id}</code></td><td>${m.status || ""}</td><td>${m.ports}</td><td class="small">${(m.not_established || []).join("; ")}</td></tr>`)}</tbody></table></div>
      <details><summary><b>${M.proposals.length} proposed calibration questions</b> <span class="faint small">proposals only, not claims</span></summary><ul>${M.proposals.map((p) => html`<li><b>${p.title}</b> ${U.pill(p.status, "st-unk")}<br><span class="small"><b>Settled by:</b> ${p.success}<br><b>Falsifier:</b> ${p.falsifier}</span></li>`)}</ul></details>
      <p class="small"><b>The manifest states these must be displayed and must not be said:</b></p><ul class="small">${M.must_display.map((x) => html`<li>${x}</li>`)}</ul><p class="small faint">Not to be said: ${M.must_not_say.map((x) => "“" + x + "”").join("; ")}.</p>
      <p class="small">Manifest sha256 ${U.sha(M.file_sha256)} · ${U.src("doc:model-coupling", "Read the coupling document")}</p></section>`;
  }

  DF.views.simulations = function (snap, route) {
    const all = [...(snap.simulation_manifests || []), glideCard(snap)].filter(Boolean);
    const P = (route && route.params) || {}; const f = { scale: P.scale || "", media: P.media || "", q: (P.q || "").trim() };
    const scaleKeys = [...new Set(all.flatMap((c) => c.scales || []))]; const scaleLabel = (k) => (snap.mission.scales.find((x) => x.key === k) || { label: k }).label;
    const hasVideo = (c) => (c.video_state === "present_verified" || c.video_state === "present_unpinned") && c.video_href;
    const cards = all.filter((c) => (!f.scale || (c.scales || []).includes(f.scale)) && (!f.media || (f.media === "video" ? hasVideo(c) : !hasVideo(c))) && (!f.q || JSON.stringify([c.title, c.model, c.evidence_kind]).toLowerCase().includes(f.q.toLowerCase())));
    const nav = html`<section class="panel simtools" aria-label="Find a simulation"><form class="filters" data-form="sg" role="search">
        <label>Scale <select name="scale"><option value="">all scales</option>${scaleKeys.map((k) => html`<option value="${k}" ${k === f.scale ? raw("selected") : ""}>${scaleLabel(k)}</option>`)}</select></label>
        <label>Media <select name="media"><option value="">any</option><option value="video" ${f.media === "video" ? raw("selected") : ""}>has a verified video</option><option value="none" ${f.media === "none" ? raw("selected") : ""}>no video</option></select></label>
        <label>Search <input type="search" name="q" value="${f.q}" placeholder="title, model or evidence kind"></label>
        <button class="btn" type="submit">Apply</button>${f.scale || f.media || f.q ? html`<a class="btn ghost" href="${DF.href("/simulations")}">Clear</a>` : ""}</form>
      <p class="count" role="status">Showing ${cards.length} of ${all.length} simulation cards${f.scale || f.media || f.q ? " (filtered)" : ""}. ${all.filter(hasVideo).length} of ${all.length} have a player.</p>
      ${cards.length > 1 ? html`<nav aria-label="Jump to a simulation"><ul class="sjump">${cards.map((c) => html`<li><button type="button" class="btn small ghost" data-jump="sim-${c.id}">${c.title.length > 46 ? c.title.slice(0, 45) + "…" : c.title}</button></li>`)}</ul></nav>` : ""}</section>`;
    return {
      html: html`<section class="pagehead"><h1>Simulations</h1><p class="lede">Recorded simulations and observed-data analyses as manifest cards: what was run, in what time units, against which numerical checks, with which parameters still unknown, and which bridges between scales are still dashed. A card shows a player only when an actual video file is present and matches its declared digest.</p></section>
      ${nav}
      <section class="panel"><h2 class="sr">Recorded simulations</h2><p class="note small">Nothing here is a live run and nothing is animated by this page. Counts of cards are counts of artifacts in this snapshot (${snap.label}), not of independent observations.</p>
        ${cards.length ? html`<div class="simgrid">${cards.map((c) => card(snap, c))}</div>` : html`<p class="empty">${all.length ? "No simulation card matches these filters." : "No simulation artifact or manifest is present in this snapshot."} Nothing is shown in its place. A manifest dropped at <code>site/artifacts/simulations/&lt;id&gt;/manifest.json</code> is picked up by the build.</p>`}</section>
      ${couplingSection(snap)}
      <section class="panel"><h2>Manifest format</h2><p class="small">Fields the build reads: <code>title</code>, <code>scales[]</code>, <code>evidence_kind</code>, <code>model{name,context}</code>, <code>time{units,note}</code>, <code>video{file,sha256,note}</code>, <code>poster</code>, <code>numerical_checks[]</code>, <code>parameter_unknowns[]</code>, <code>open_questions[]</code>, <code>couplings[{from,to,status}]</code>. The video file must sit beside the manifest. The runtime serves <code>.mp4</code> and <code>.webm</code> under <code>site/artifacts/</code> with range requests; the build copies a video there only when its bytes match the declared sha256.</p></section>`,
      after(root) {
        DF.bindForm(root, "sg", (v) => DF.href("/simulations", v));
        root.querySelectorAll("[data-jump]").forEach((b) => b.addEventListener("click", () => {
          const el = root.querySelector("#" + b.dataset.jump); if (!el) return; el.scrollIntoView({ block: "start" });
          const h = el.querySelector("h3"); if (h) { h.setAttribute("tabindex", "-1"); h.focus({ preventScroll: true }); }
        }));
      },
    };
  };
})();
