/* Simulations gallery: manifest-only cards. A video element exists only when a video file is present and matches its declared sha256. */
(function () {
  const DF = window.DF; const { html, esc, fmt } = DF; const U = DF.ui;

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
    const vs = c.video_state; const hasV = vs === "present_verified" && c.video_href;
    const media = hasV ? html`<video controls preload="none" ${c.poster_href ? html`poster="${c.poster_href}"` : ""} src="${c.video_href}" aria-label="${c.title}"></video><p class="small faint">Video file verified against its declared sha256. ${c.video && c.video.note ? c.video.note : ""}</p>`
      : html`<div class="novideo">${c.poster_href ? html`<img src="${c.poster_href}" alt="${c.poster_is_figure ? "Recorded figure (not a video)" : "Poster frame"}" loading="lazy">` : ""}<p><b>No video file.</b> ${{ none: "None has been provided for this artifact.", declared_but_missing: "A video is declared in the manifest but the file is not present.", digest_mismatch: "A video file is present but does not match its declared sha256, so it is not offered." }[vs] || ""} ${c.poster_is_figure ? "The image is a recorded figure, not a frame of a video." : ""}</p></div>`;
    const list = (a, empty) => (a && a.length ? html`<ul>${a.map((x) => html`<li>${typeof x === "string" ? x : x.name ? html`<b>${x.name}</b>: ${x.result || ""}${x.tolerance !== undefined ? html` <span class="faint">(tolerance ${x.tolerance})</span>` : ""}` : JSON.stringify(x)}</li>`)}</ul>` : html`<p class="faint small">${empty}</p>`);
    return html`<article class="simcard" id="sim-${c.id}"><div class="simhead"><h3>${c.title}</h3><p>${(scl.length ? scl : ["scale not stated"]).map((x) => U.pill(x, "grp"))} ${U.pill(c.evidence_kind || "evidence kind not stated", "ev")} ${c.derived ? U.pill("derived from recorded results; no manifest file", "warn") : U.pill("manifest", "cur")}</p></div>
      ${c.error ? html`<p class="empty">${c.error} (${c.manifest})</p>` : html`<div class="simmedia">${media}</div>
      <dl class="kv"><div><dt>Model</dt><dd>${(c.model && c.model.name) || "not stated"}</dd></div><div><dt>Time units</dt><dd>${(c.time && c.time.units) || "not stated"}</dd></div></dl>
      <p class="small">${(c.model && c.model.context) || ""} ${(c.time && c.time.note) || ""}</p>
      <h4>Numerical checks</h4>${list(c.numerical_checks, "No numerical check is recorded.")}
      <h4>Parameter unknowns</h4>${list(c.parameter_unknowns, "None stated, which is not the same as none.")}
      <h4>Open questions</h4>${list(c.open_questions, "None stated.")}
      <h4>Coupling between scales</h4><div class="chainwrap">${DF.raw(chain(snap, c))}</div><p class="small faint">Filled circle: a scale this artifact runs at. Dashed link: unknown bridge (no executable coupling recorded).</p>
      ${c.files && c.files.length ? html`<p class="small">Files: ${c.files.map((f) => html`<a href="${f.href}">${f.name}</a> (${f.bytes} bytes, ${U.sha(f.sha256)}) `)}</p>` : ""}
      <p class="small faint">${c.manifest ? "Manifest: " + c.manifest : ""}</p>`}</article>`;
  }

  DF.views.simulations = function (snap) {
    const cards = [...(snap.simulation_manifests || []), glideCard(snap)].filter(Boolean);
    return {
      html: html`<section class="pagehead"><h1>Simulations</h1><p class="lede">Recorded simulations as manifest cards: what was run, in what time units, against which numerical checks, with which parameters still unknown, and which bridges between scales are still dashed. A card shows a player only when an actual video file is present and matches its declared digest.</p></section>
      <section class="panel"><p class="note small">Nothing here is a live run and nothing is animated by this page. Counts of cards are counts of artifacts in this snapshot (${snap.label}), not of independent observations.</p>
        ${cards.length ? html`<div class="simgrid">${cards.map((c) => card(snap, c))}</div>` : html`<p class="empty">No simulation artifact or manifest is present in this snapshot. Nothing is shown in its place. A manifest dropped at <code>site/artifacts/simulations/&lt;id&gt;/manifest.json</code> is picked up by the build.</p>`}</section>
      <section class="panel"><h2>Manifest format</h2><p class="small">Fields the build reads: <code>title</code>, <code>scales[]</code>, <code>evidence_kind</code>, <code>model{name,context}</code>, <code>time{units,note}</code>, <code>video{file,sha256,note}</code>, <code>poster</code>, <code>numerical_checks[]</code>, <code>parameter_unknowns[]</code>, <code>open_questions[]</code>, <code>couplings[{from,to,status}]</code>. The video file must sit beside the manifest. The runtime currently serves only the file types listed in its static allow-list under <code>site/artifacts/</code>; MP4 is not among them.</p></section>`,
    };
  };
})();
