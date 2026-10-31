/* Home (two entry paths), Studio (projects, Flying Fish featured) and the project studio with a subsystem-by-scale workspace.
 * Everything shown is from the snapshot or the live node; a gap is shown as a gap. Comments are local drafts, never silently submitted. */
(function () {
  const DF = window.DF; const { html, raw, esc, fmt } = DF; const U = DF.ui;

  const fish = (snap) => snap.projects.projects.find((p) => p.featured) || snap.projects.projects[0];
  const qOf = (snap, scale) => DF.questions(snap).filter((q) => DF.annotate(q, snap).scales.includes(scale));
  const modelOf = (snap, id) => (snap.coupling_manifest ? snap.coupling_manifest.models.find((m) => m.id === id) : null);
  const vidOf = (snap, id) => (snap.simulation_manifests || []).find((m) => m.id === id);
  const claimOf = (snap, id) => snap.claims.find((c) => c.id === id);
  const hasContent = (pan) => (pan.models.length || pan.videos.length || pan.forms || pan.claims.length || pan.equations.length);

  /* ---------------------------------------------------------------- text goal entry: routes a sentence to project, subsystem and open work. It generates nothing. */
  const KEYS = { "flying-fish": ["fish", "fin", "fins", "flying", "glide", "glider", "wing", "wings", "lift", "aerodynamic", "airborne", "exocoet", "halfbeak", "gliding"] };
  const SCALE_WORDS = { molecular: ["molecul", "gene", "genom", "protein", "dna", "rna", "sequence"], cellular: ["cell", "notch", "delta", "lateral"], tissue: ["tissue", "pattern", "turing", "reaction", "diffusion", "morphogen"], organ: ["organ", "fin ray", "beam", "stiff", "bend", "elastic"], organism: ["organism", "body", "mass", "wing loading", "aspect", "flight", "glide", "speed"], developmental: ["develop", "growth", "embryo", "ontogen"], ecological: ["evol", "ecolog", "ancest", "predator", "phylogen", "reachab"], neural: ["neural", "brain", "control", "nerve"], collective: ["school", "collective", "swarm"], macromolecular: ["structure", "binding", "affinity", "fold"], subcellular: ["organelle", "subcellular", "membrane"] };
  function goalForm(value) {
    return html`<form class="goalform" data-form="goal" role="search" aria-label="Describe a design goal"><label for="goalq"><b>Describe a goal or a question</b> <span class="faint small">in a sentence; it is routed to a project, a subsystem and open work, and nothing is generated</span></label>
      <div class="goalrow"><input id="goalq" name="goal" type="text" value="${value || ""}" placeholder="e.g. make a fin that can glide, or: how do fin proportions get set?" maxlength="300"><button class="btn" type="submit">Find where this lives</button></div></form>`;
  }
  async function goalResults(snap, goal) {
    const g = goal.toLowerCase(); const out = { project: null, reasons: [], scales: [], questions: [], claims: [] };
    snap.projects.projects.forEach((p) => { const ws = (KEYS[p.id] || []).filter((k) => g.includes(k)); if (ws.length && !out.project) { out.project = p; out.reasons = ws; } });
    Object.entries(SCALE_WORDS).forEach(([sc, ws]) => { const hit = ws.filter((w) => g.includes(w)); if (hit.length) out.scales.push({ scale: sc, words: hit }); });
    const toks = g.split(/[^a-z0-9]+/).filter((t) => t.length > 3);
    out.questions = DF.questions(snap).filter((q) => toks.some((t) => JSON.stringify([q.title, q.question, q.known || q.known_state]).toLowerCase().includes(t))).slice(0, 6);
    try { const r = await DF.api.catalog({ query: toks[0] || goal, kind: "Problem", limit: 6 }); out.liveQuestions = r.records; } catch (e) { out.liveQuestions = []; }
    try { const r = await DF.api.catalog({ query: toks[0] || goal, kind: "Claim", limit: 6 }); out.claims = r.records; } catch (e) { out.claims = []; }
    return out;
  }
  function goalPanel(snap, goal, res) {
    return html`<section class="panel" aria-labelledby="gr-h"><h2 id="gr-h">Where “${goal}” lives</h2>
      <p class="note small">This routes your sentence to existing work by keyword and text match. It does not design an organism, a genome or a model from text.</p>
      ${res.project ? html`<p><b>Project:</b> <a href="${DF.href("/studio/" + res.project.id, { scale: res.scales[0] ? res.scales[0].scale : "organism" })}">${res.project.title}</a> <span class="faint small">matched on: ${res.reasons.join(", ")}</span></p>` : html`<p class="empty">No project covers this goal. Projects exist only as records or authored entries; starting one needs a Project record and a credentialed submission that this page does not make.</p>`}
      ${res.scales.length ? html`<p><b>Subsystems:</b> ${res.scales.map((s) => html`<a class="pill" href="${DF.href("/studio/" + (res.project ? res.project.id : "flying-fish"), { scale: s.scale })}">${(snap.mission.scales.find((x) => x.key === s.scale) || { label: s.scale }).label}</a> `)}<span class="faint small">by words: ${res.scales.map((s) => s.words.join("/")).join("; ")}</span></p>` : ""}
      <h3>Open work</h3>${res.questions.length || (res.liveQuestions || []).length ? html`<ul>${res.questions.map((q) => html`<li><a href="${DF.href("/frontier/" + q.id)}"><b>${q.id}</b></a> ${q.title} <span class="faint small">(curated)</span></li>`)}${(res.liveQuestions || []).map((x) => html`<li><a href="${DF.href("/entity/Problem/" + x.ref.id, { v: x.ref.version })}">${x.title}</a> <span class="faint small">(${DF.api.isLive() ? "live node" : "snapshot"})</span></li>`)}</ul>` : html`<p class="empty">No open question matches these words.</p>`}
      <h3>Claims that mention it</h3>${(res.claims || []).length ? html`<ul>${res.claims.map((x) => html`<li><a href="${DF.href("/entity/Claim/" + x.ref.id, { v: x.ref.version })}">${x.title}</a></li>`)}</ul><p class="small"><a href="${DF.href("/knowledge", { tab: "browse", q: goal.split(/\s+/)[0] })}">Browse the claims</a></p>` : html`<p class="empty">No claim matches these words.</p>`}</section>`;
  }

  /* Zebrafish life-cycle source layer: what each stage has (size, growth, metabolism, locomotion, fins) and where it is unknown. Danio rerio only. */
  function lifecyclePanel(snap) {
    const L = snap.lifecycle;
    if (!L) return html`<section class="panel"><h3>Life cycle</h3><p class="empty">No life-cycle data is present in this snapshot.</p></section>`;
    const tone = { measured_in_fish: "ok", modelled_and_fit_to_fish_data: "warn", observed_qualitative: "st-unk", borrowed_nonfish: "warn", unknown: "no" };
    const pill = (v) => U.pill(String(v || "not stated").replace(/_/g, " "), tone[v] || "st-unk");
    const names = Object.fromEntries(L.stages.map((x) => [x.id, x.name]));
    const D = L.diffusion;
    return html`<section class="panel lifecycle" aria-labelledby="lc-h"><h3 id="lc-h">Life cycle (${L.organism}, not a flying fish)</h3>
      <p class="note warn small"><b>${L.status}.</b> ${L.claims_not_made.map((x) => "Not claimed: " + x + ".").join(" ")}</p>
      <p class="small">${L.stage_note}. Reference temperature ${L.temperature_c} °C.</p>
      <div class="tablewrap"><table><caption class="sr">Evidence status of each process at each stage</caption><thead><tr><th scope="col">Process</th>${L.stage_order.map((g) => html`<th scope="col">${names[g] || g}</th>`)}</tr></thead>
        <tbody>${Object.entries(L.processes).map(([k, v]) => html`<tr><th scope="row">${k.replace(/_/g, " ")}</th>${L.stage_order.map((g) => html`<td>${v[g] ? html`${pill(v[g].status)}<br><span class="small faint">${v[g].note}${v[g].sources ? " [" + v[g].sources + "]" : ""}</span>` : ""}</td>`)}</tr>`)}</tbody></table></div>
      <p class="small"><b>Gaps first:</b> ${L.gaps_first.join("; ")}.</p>
      <details><summary><b>${L.stages.length} stages</b> <span class="faint small">definitions quoted from the source</span></summary><ul class="small">${L.stages.map((x) => html`<li><b>${x.name}</b>${x.time ? html` (from ${x.time.start_hpf !== undefined ? x.time.start_hpf + " hpf" : "start not stated"})` : ""}: ${x.definition ? "“" + x.definition + "”" : "no definition quoted"}<br>${Object.entries(x.axes).map(([a, v]) => html`${a.replace(/_/g, " ")}: ${pill(v)} `)}</li>`)}</ul></details>
      <details><summary><b>${L.equations.length} named equations and parameters</b> <span class="faint small">forms as written; context and limits stated</span></summary><ul class="small">${L.equations.map((q) => html`<li><b>${q.name}</b>: <code>${q.form}</code><br>${q.context}${q.not_established_here ? html`<br><b>Not established here:</b> ${q.not_established_here}` : ""}</li>`)}</ul></details>
      <details><summary><b>Oxygen diffusion sizing aid</b> <span class="faint small">borrowed parameters, not a feasibility statement</span></summary><p class="note warn small">${D.status}</p><p class="small">${D.reading}</p>
        <p class="small">Derived one-sided slab limit ${Math.round(D.derived.slab_one_sided_limit_um)} µm; two faces ${Math.round(D.derived.slab_two_sided_range_um[0])} to ${Math.round(D.derived.slab_two_sided_range_um[1])} µm (total thickness ${Math.round(D.derived.slab_two_sided_total_thickness_um)} µm).</p>
        <div class="tablewrap"><table><thead><tr><th>Milestone</th><th>HAA (mm)</th><th>HAA / two-sided slab limit</th></tr></thead><tbody>${D.rows.map((r) => html`<tr><td>${r.milestone}</td><td>${r.haa_mm}</td><td>${r.ratio_haa_to_two_sided_slab_limit}</td></tr>`)}</tbody></table></div>
        <p class="small"><b>Not known:</b> ${D.not_known.join("; ")}.</p></details>
      <p class="small faint">Manifest ${L.manifest} · ${U.src("doc:fish-lifecycle", "Read the life-cycle document")}</p></section>`;
  }

  /* Home: sourced anatomy beside the actual 3D candidate. Statuses are the fish3d candidate's own; nothing is called validated. */
  const STATUS_WORDS = { derived: "derived from a sourced fit", functional: "set from a sourced relation or the design target", figure_read: "read from a published figure", aesthetic: "aesthetic choice", assumed: "assumed", numerical: "numerical setting", design_assumption: "design assumption", "assumed transfer": "assumed transfer" };
  /* Candidate-dependent statement about what the selected 3D model is. Status words are the candidate's own; nothing is called validated. */
  function groundNote(c, H) {
    const sc = c.status_counts || {}; const parts = Object.entries(sc).map(([k, n]) => n + " " + (STATUS_WORDS[k] || k)).join(", ");
    if (!c.knobs) return html`<b>Not biorealistic and not validated.</b> This baseline is an engineered candidate sized from published measurements. Its flat fin plates (${H.candidate.fin_thickness.value} mm), lattice scales and decorative eyes are assumptions. ${H.candidate.label}`;
    const rays = c.rays ? Object.entries(c.rays).map(([k, n]) => k + " " + n).join(", ") : "";
    return html`<b>Ray-supported fins and a scale map, not a validated fish.</b> Selected candidate ${c.label}: fins are modelled as individual rays with a membrane between them${rays ? " (" + rays + " rays)" : ""}; ray counts, attachments, outline and scales are sourced where the viewer's table says so and assumed otherwise. Recorded parameter statuses: ${parts || "not recorded"}. Eyes and gill covers are simplified, pigment is an appearance choice, and no biological or aerodynamic validation is claimed. The data panel and region cards below describe the N1 baseline reference.`;
  }

  function groundingSection(snap) {
    const H = snap.home_biology;
    if (!H) return html`<section class="panel"><h2>Start from real fish anatomy.</h2><p class="empty">No fish3d candidate or fish-control data is present in this snapshot.</p></section>`;
    const f = H.fitted[0]; const c = H.candidate; const sh = Object.entries(H.fish1990.pectoral_share_pct_mean_se).sort((x, y) => x[1][0] - y[1][0]); const lo = sh[0], hi = sh[sh.length - 1]; const cm = (snap.coupling_manifest || {}).counts; const SOFT = new Set(["aesthetic", "assumed", "numerical", "assumed transfer", "design_assumption"]);
    return html`<section class="panel grounding" aria-labelledby="gr-h"><h2 id="gr-h">Start from real fish anatomy.</h2>
      <p class="note warn small" id="grnote"></p>
      ${snap.fish3d_viewer ? html`<div class="fishchoose"><label for="fishcand"><b>Candidate</b></label> <select id="fishcand">${snap.fish3d_viewer.candidates.map((c, i) => html`<option value="${c.id}" ${i === (snap.fish3d_viewer.candidates.length > 1 ? 1 : 0) ? raw("selected") : ""}>${c.label}</option>`)}</select> <span class="small faint" id="fishknobs"></span></div>
        <h3 class="sr">Interactive 3D candidate</h3>
        <div id="fish-viewer" class="fishviewer" aria-label="Interactive 3D model of the candidate"></div><p class="small faint" id="fishnote">The 3D model is a candidate mesh. Colours and pigment bands are appearance choices, each marked sourced or assumed in the viewer. Not an organism and not an aerodynamic result. The schematic drawing and printable models are below.</p>` : ""}
      <div class="groundgrid"><div><div id="fishmini" class="fishmini"></div></div>
        <div><h3>What the body and fins are sized from <span class="faint small">(N1 baseline reference)</span></h3>
          <p>Candidate N1: standard length ${c.standard_length_mm.toFixed(1)} mm, wing span ${c.wing_span_mm.toFixed(1)} mm, wing area ${Math.round(c.wing_area_mm2)} mm², mass ${c.mass_kg} kg.</p>
          <ul>
            <li><b>Measured here:</b> pectoral fin length against standard length in ${f.n} preserved ${f.group} specimens (${f.species.join(", ")}; ${f.material}) follows length ∝ SL<sup>${f.b.toFixed(3)}</sup>, 95% bootstrap interval ${f.b_ci95[0].toFixed(3)} to ${f.b_ci95[1].toFixed(3)}, R² ${f.r2.toFixed(3)}. Species and sizes are pooled. Source: Daane et al. 2021, Data S1A, fit made in this repository.</li>
            <li><b>Published, raw data unavailable:</b> Fish 1990 reports the pectoral fins as ${lo[0]} (${lo[1][0]} ± ${lo[1][1]}%) to ${hi[0]} (${hi[1][0]} ± ${hi[1][1]}%) of wing area by genus, and ${H.fish1990.hypocaudal_share_pct_mean_se[0]}% ± ${H.fish1990.hypocaudal_share_pct_mean_se[1]} of caudal area in the lower lobe (pooled). ${H.fish1990.raw_data}.</li></ul>
          <p class="small"><b>Evidence kinds, kept apart:</b> ${Object.entries(H.evidence_counts).map(([k, n]) => html`${U.pill(n + " " + k.replace(/_/g, " "), "grp")} `)} ${H.no_cross_source_conversion} These are different kinds of record, not ${Object.values(H.evidence_counts).reduce((a, b) => a + b, 0)} empirically learned laws. ${H.knobs_status}.</p>
          <h3>Region by region: where each parameter comes from <span class="faint small">(the N1 baseline reference, not the candidate selected above)</span></h3>
          <div class="regiongrid">${H.regions.map((r) => { const soft = Object.entries(r.params).filter(([, v]) => SOFT.has(v)).map(([k, v]) => k.replace(/_/g, " ") + " (" + (STATUS_WORDS[v] || v) + ")"); const hard = Object.entries(r.params).filter(([, v]) => !SOFT.has(v)); return html`<article class="region"><h4>${r.id}</h4>
            <p class="small">${hard.length} parameter${hard.length === 1 ? "" : "s"} sourced, derived or read from a figure: ${[...new Set(hard.map(([, v]) => STATUS_WORDS[v] || v))].join("; ") || "none"}.</p>
            ${soft.length ? html`<p class="small assumed"><b>Assumed or chosen:</b> ${soft.join("; ")}.</p>` : ""}${r.notes.length ? html`<p class="small faint">${r.notes[0]}</p>` : ""}</article>`; })}</div>
          <p class="small">Parameter status words are the candidate's own (<code>components.json</code>); unknown biology is not filled in. <a href="${DF.href("/studio/flying-fish", { scale: "organ" })}">Modelled mechanics at the organ scale</a> · <a href="${DF.href("/simulations")}">All simulations</a>${cm ? html` · unsupported bridges: ${cm.refused} refused and ${cm.scenario} scenario-level of ${cm.refused + cm.scenario + cm.composable} couplings` : ""} · <a href="${DF.href("/evidence")}">Evidence status</a></p>
          <details><summary><b>${H.sources.length} sources</b> <span class="faint small">licences and read levels as recorded</span></summary><ul class="small">${H.sources.map((x) => html`<li>${x.citation}<br><span class="faint">Read: ${x.read_level}. Licence: ${x.licence}</span></li>`)}</ul><p class="small faint">Raw source files are not redistributed by this site. Manifest ${H.manifest}.</p></details></div></div></section>`;
  }

  /* ---------------------------------------------------------------- home */
  DF.views.home = function (snap) {
    const p = fish(snap); const forms = snap.print_forms ? snap.print_forms.forms : []; const vids = (snap.simulation_manifests || []).filter((m) => m.video_state === "present_verified" && m.poster_href);
    const openQ = DF.questions(snap).filter((q) => q.state === "open").length; const withModel = Object.values(p.panels).filter((x) => x.models.length).length;
    return {
      html: html`<section class="hero compact"><div><p class="eyebrow">MorphoSwarm Frontier</p><h1>Design together.<br>Know what's open.</h1></div>
        <div class="herotext"><p class="lede">Two ways in, one body of evidence. <b>Studio</b> is where a design goal is worked across scales, with the models, media and gaps in one place. <b>Frontier</b> is the shared list of open questions and who is working on them. Both read the same claims and evidence, kept in the Delphi foundation: what we know, what's next, who's working on it.</p></div></section>
      ${groundingSection(snap)}
      <p class="small aboutlink"><a href="${DF.href("/about")}">About this project</a> · <a href="${DF.href("/generative")}">Generative biology: from mechanistic simulation to equation-conditioned models</a></p>
      <section class="panel goalpanel">${goalForm("")}</section>

      <section class="paths" aria-label="Two entry paths">
        <article class="path studio"><p class="eyebrow">Studio · projects</p><h2>Work a design across scales</h2>
          <p>A project names a goal, breaks it into subsystems by scale, and shows for each the model that exists, its parameters and unknowns, equations, claims, media and open questions. Gaps stay visible.</p>
          <div class="featured"><span class="pill gen">featured project</span><h3>${p.title}</h3><p class="small">${p.summary}</p>
            <div class="mgrid mini">${forms.filter((f) => f.files.image).slice(0, 2).map((f) => html`<a class="mitem" href="${DF.href("/studio/" + p.id, { scale: "organ" })}"><img src="${f.files.image.href}" alt="${f.title}" loading="lazy"><span>${f.title}</span></a>`)}${vids.slice(0, 2).map((m) => html`<a class="mitem" href="${DF.href("/studio/" + p.id, { scale: m.scales[0] })}"><img src="${m.poster_href}" alt="${m.title}" loading="lazy"><span>▶ ${m.title}</span></a>`)}</div>
            <p class="small faint">${withModel} of 11 scales have a recorded model; the rest are stated gaps.</p></div>
          <p><a class="btn" href="${DF.href("/studio/" + p.id)}">Open the Flying fish studio</a> <a class="btn ghost" href="${DF.href("/studio")}">All projects</a></p></article>
        <article class="path frontier"><p class="eyebrow">Frontier · open work</p><h2>Find open questions and join them</h2>
          <p>Every question carries what is known, what would settle it, what it needs, and who holds a live lease. Direction filters separate top-down design questions from bottom-up theory and literature gaps.</p>
          <p class="facts-line"><b id="homeq">${openQ}</b> curated questions in the snapshot <span class="faint small">(live count appears when the node is reachable)</span></p>
          <p><a class="btn" href="${DF.href("/frontier")}">Open the Frontier</a> <a class="btn ghost" href="${DF.href("/knowledge")}">Claims and evidence</a></p></article></section>
      <section class="panel crosslinks"><h2>How they connect</h2><ul><li>Every open question names the scales it touches; from a question you can jump to that subsystem in the studio.</li><li>Every subsystem lists the open questions at its scale and links to them on the Frontier.</li><li>Claims, evidence and artifacts live once, in the Delphi foundation, and both paths link to the same entity pages.</li></ul>
        <p class="small faint">Projects other than Flying fish are added as Project records; none is invented here.</p></section>`,
      async after(root) {
        DF.mountFishMini(root.querySelector("#fishmini"), snap);
        if (snap.fish3d_viewer && root.querySelector("#fish-viewer")) {
          const host = root.querySelector("#fish-viewer"), sel = root.querySelector("#fishcand"); let viewer = null, gen = 0;
          const mount = async () => {
            const my = ++gen; const c = snap.fish3d_viewer.candidates.find((x) => x.id === sel.value);
            root.querySelector("#grnote").innerHTML = groundNote(c, snap.home_biology).toString();
            root.querySelector("#fishknobs").textContent = c.knobs ? Object.entries(c.knobs).map(([k, v]) => k.replace(/_/g, " ") + " " + v).join(" · ") : "baseline: flat fin plates, assumed thickness";
            try { const m = await import("./model-viewer.js"); if (my !== gen) return; if (viewer && viewer.destroy) viewer.destroy(); host.textContent = ""; host.className = "fishviewer";
              viewer = m.mountFishViewer(host, { base: c.base, layout: "hero", ...(c.variants.length ? { variants: c.variants } : {}) }); DF.fishViewer = viewer; }
            catch (e) { host.textContent = "The 3D viewer could not load (" + e.message + "). The turntable and drawing remain below."; }
          };
          sel.addEventListener("change", mount); DF.onLeave(() => { gen++; if (viewer && viewer.destroy) viewer.destroy(); viewer = null; DF.fishViewer = null; }); mount();
        }
        DF.bindForm(root, "goal", (v) => DF.href("/studio", { goal: v.goal }));
        try { const L = await DF.liveQuestionCount(); if (L) root.querySelector("#homeq").parentElement.innerHTML = `<b>${L.n}</b> questions in the live node <span class="faint small">(${esc(L.source)})</span>`; } catch (e) { /* the snapshot figure stays */ }
      },
    };
  };

  /* ---------------------------------------------------------------- projects list */
  DF.views.studio = function (snap, route) {
    const id = route.parts[1];
    if (id) return projectStudio(snap, route, id);
    const goal = (route.params.goal || "").trim();
    return {
      html: html`<section class="pagehead"><h1>Studio</h1><p class="lede">Design projects, each broken into subsystems by scale. ${snap.projects.note}</p></section>
        <section class="panel goalpanel">${goalForm(goal)}</section><div id="goalout"></div>
        <section class="panel"><h2 class="sr">Projects</h2>${snap.projects.projects.map((p) => html`<article class="card pform"><h3>${p.title} ${p.featured ? U.pill("featured", "gen") : ""} ${U.pill(p.status, "st-unk")}</h3><p><b>Goal.</b> ${p.goal}</p><p class="small">${p.summary}</p><p><a class="btn" href="${DF.href("/studio/" + p.id)}">Open studio</a></p></article>`)}
        <p class="note small">${snap.projects.other_projects_note}</p><p class="small faint">Starting a new project needs a Project record and a credentialed submission route; this page does not create one.</p></section>`,
      async after(root) {
        DF.bindForm(root, "goal", (v) => DF.href("/studio", { goal: v.goal }));
        if (goal) { const host = root.querySelector("#goalout"); host.innerHTML = '<p role="status" class="small">Looking…</p>'; host.innerHTML = goalPanel(snap, goal, await goalResults(snap, goal)).toString(); }
      },
    };
  };

  /* The Project record draft (guilds' schema): requirements and open questions as declared; a draft is not a store record and nothing here is accepted. */
  function projectDraftPanel(PD) {
    return html`<section class="panel" aria-labelledby="pd-h"><h2 id="pd-h">Project record draft</h2><p class="note small"><b>Validated but not submitted.</b> This is the project as a Project record would carry it (file <code>${PD.path}</code>, sha256 ${U.sha(PD.sha256)}). A Project is proposed until an independent operator reviews it; the page does not submit it.</p>
      <p class="small">${PD.members.length} pinned members; none declares a calibrated causal bridge${PD.members.some((m) => m.causal_bridge && m.causal_bridge !== "none_declared") ? "" : " (all say none declared)"}. ${PD.limitations.join(" ")}</p>
      <details><summary><b>${PD.requirements.length} requirements</b> <span class="faint small">all stage ${[...new Set(PD.requirements.map((r) => r.stage))].join(", ")}</span></summary><ul>${PD.requirements.map((r) => html`<li><b>${r.kind}</b> ${r.text}${r.quantity ? html` <code>${r.quantity.name} ${r.quantity.comparator} ${r.quantity.value} ${r.quantity.unit}</code>` : ""}</li>`)}</ul></details>
      <details><summary><b>${PD.open_questions.length} open questions</b></summary><ul>${PD.open_questions.map((q) => html`<li>${q.text} ${q.problem ? html`<a href="${DF.href("/frontier/" + q.problem)}">${q.problem}</a>` : ""}</li>`)}</ul></details></section>`;
  }

  /* Retrieved data slice (claude-11's connector). Identifiers and receipts only: no model output, no sequence design, no inference from absence. */
  function genomicsPanel(snap) {
    const G = snap.genomics;
    if (!G) return html`<h3>Genomic data</h3><p class="empty">No genomic data slice is present in this tree. No gene, sequence or designer output is shown or implied.</p>`;
    const ff = G.flyingfish;
    return html`<h3>Retrieved genomic data slice ${U.pill("data, not a model", "warn")}</h3><p class="small">${G.genes.length} zebrafish genes chosen for fin development, bioelectric proportion, mechanosensation and regeneration, with identifiers from ZFIN and NCBI. Each source retrieval is receipted below with its hash; nothing here is a prediction or a designed sequence.</p>
      <div class="tablewrap"><table><thead><tr><th>Gene</th><th>Description</th><th>ZFIN</th><th>Ensembl</th><th>NCBI Gene</th><th>Chr</th></tr></thead><tbody>${G.genes.map((g) => html`<tr><td><b>${g.symbol}</b></td><td class="small">${g.description || ""}</td><td class="small">${g.zfin || ""}</td><td class="small">${g.ensembl || ""}</td><td class="small">${g.ncbi_gene || ""}</td><td>${g.chromosome || ""}</td></tr>`)}</tbody></table></div>
      ${ff ? html`<p class="small"><b>Flying-fish annotation subset</b> (Hirundichthys speculiger, figshare ${ff.doi}, ${ff.license}, published ${ff.published}): ${ff.annotation_totals ? Object.entries(ff.annotation_totals).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`).join("; ") : ""}. ${ff.selected_genes} of the chosen genes were located by protein alignment (${ff.length_consistent} length-consistent). ${ff.mapping_note}. Symbols with no hit: ${Object.entries(ff.absent_symbols).map(([k, v]) => `${k} (${v} queries with any hit)`).join(", ") || "none"}.</p>` : ""}
      <details><summary class="small">${G.receipts.length} retrieval receipts</summary><div class="tablewrap"><table><thead><tr><th>Source</th><th>Retrieved</th><th>HTTP</th><th>Bytes</th><th>sha256</th></tr></thead><tbody>${G.receipts.map((r) => html`<tr><td class="small">${r.key}<br><a href="${r.url}" target="_blank" rel="noopener noreferrer">${r.url}</a>${r.license ? html`<br>licence ${r.license}` : ""}</td><td class="small">${r.retrieved_at}</td><td>${r.http_status}</td><td>${r.bytes}</td><td>${U.sha(r.sha256)}</td></tr>`)}</tbody></table></div><p class="small faint">Query strings are removed from the URLs shown. Receipts file sha256 ${U.sha(G.receipts_sha256)}.</p></details>`;
  }

  /* ---------------------------------------------------------------- one project */
  const DRAFT_KEY = (pid, scale) => `frontier-annotation-draft:${pid}:${scale}`;
  const drafts = (k) => { try { return JSON.parse(localStorage.getItem(k) || "[]"); } catch (e) { return []; } };
  const saveDrafts = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } };

  function projectStudio(snap, route, id) {
    const p = snap.projects.projects.find((x) => x.id === id);
    if (!p) return { html: html`<section class="pagehead"><h1>No such project</h1><p class="lede">There is no project “${id}” in this snapshot. <a href="${DF.href("/studio")}">See the projects</a>.</p></section>` };
    const m = snap.mission; const scale = route.params.scale && p.panels[route.params.scale] ? route.params.scale : "organism"; const pan = p.panels[scale]; const sc = m.scales.find((s) => s.key === scale);
    const sub = html`<nav class="subnav" aria-label="Project sections"><a href="${DF.href("/studio/" + p.id)}" aria-current="page">Studio</a><a href="${DF.href("/engineering")}">Engineering workspace</a><a href="${DF.href("/simulations")}">Simulations</a><a href="${DF.href("/belief")}">Belief</a><a href="${DF.href("/formalize")}">Proposal checker</a><a href="${DF.href("/frontier", { scale })}">Open questions at this scale</a></nav>`;
    const PD = (snap.project_drafts || {})[p.id]; const cov = (k) => (PD ? PD.scale_coverage.find((c) => c.scale === k || (k === "ecological" && c.scale === "evolutionary")) : null);
    const rail = m.scales.map((s, i) => { const pn = p.panels[s.key]; const c = cov(s.key); const st = c ? ({ implemented_model: "model", source_only: "partial" }[c.status] || "gap") : pn.models.length ? "model" : hasContent(pn) || (snap.simulation_manifests || []).some((x) => (x.scales || []).includes(s.key)) ? "partial" : "gap";
      return html`<li><a class="subsys ${st} ${s.key === scale ? "on" : ""}" href="${DF.href("/studio/" + p.id, { scale: s.key })}" aria-current="${s.key === scale ? "true" : "false"}"><span class="n">${i + 1}</span><b>${s.label}</b><small>${st === "model" ? "recorded model" : st === "partial" ? "partial" : "gap"}</small></a></li>`; });
    const models = pan.models.length ? html`<div class="cards">${pan.models.map((mid) => { const mm = modelOf(snap, mid); return mm ? html`<article class="card"><h4>${mm.name}</h4><p class="small">${U.pill(mm.status || "status not stated", "st-unk")} ${mm.engine ? U.pill(mm.engine, "grp") : ""} ports: ${mm.ports}</p><p class="small"><b>Scope.</b> ${mm.scope || ""}</p><p class="small"><b>Not established.</b> ${(mm.not_established || []).join("; ") || "not stated"}</p></article>` : html`<article class="card"><h4>${mid}</h4><p class="small faint">Named in the project but not in the coupling manifest.</p></article>`; })}</div>` : html`<p class="empty">No model is attached at this scale. ${pan.gap}</p>`;
    const vids = [...new Set([...pan.videos, ...(snap.simulation_manifests || []).filter((m) => (m.scales || []).includes(scale)).map((m) => m.id)])].map((v) => vidOf(snap, v)).filter(Boolean);
    const forms = pan.forms && snap.print_forms ? snap.print_forms.forms : [];
    const media = vids.length || forms.length ? html`<div class="artgrid">${vids.map((v) => html`<article class="artcard"><h4>${v.title}</h4>${v.video_state === "present_verified" ? html`<video class="embed" controls playsinline preload="metadata" ${v.poster_href ? html`poster="${v.poster_href}"` : ""} src="${v.video_href}" aria-label="${v.title}"></video>` : html`<p class="empty">No verified video file.</p>`}<p class="small faint">${v.evidence_kind}. ${(v.time && v.time.units) || ""}</p></article>`)}${forms.map((f) => html`<article class="artcard"><h4>${f.title}</h4>${f.files.image ? html`<img class="embed" src="${f.files.image.href}" alt="${f.title}" loading="lazy">` : ""}<p class="small">${U.pill("solver: " + f.solver, f.solver === "feasible" ? "warn" : "no")} ${f.files.stl ? html`<a href="${f.files.stl.href}" download>STL</a>` : ""}</p><p class="small faint">Illustrative print form, not a validated design.</p></article>`)}</div>` : html`<p class="empty">No media at this scale.</p>`;
    const eqs = pan.equations.map((eid) => m.equations.find((e) => e.id === eid)).filter(Boolean); const cls = pan.claims.map((c) => claimOf(snap, c)).filter(Boolean);
    const eqHtml = eqs.length || cls.length ? html`${eqs.map((e) => html`<div class="eqcard"><h4>${e.name}</h4><div class="eq-math">${DF.texSpan(e.latex, true)}</div><p class="small">${U.src("src:" + e.source, DF.sourceTitle(snap, e.source))} · ${e.context}</p></div>`)}${cls.map((c) => html`<div class="eqcard"><h4>${c.label}</h4>${DF.mixedSpan(c.math)}<p class="small">${U.pill(DF.CATEGORY[c.category].text, DF.CATEGORY[c.category].cls)} <a href="${DF.href("/entity/Claim/" + c.id)}">Open the claim page</a></p></div>`)}` : html`<p class="empty">No equation is attached at this scale.</p>`;
    const unknowns = [...vids.flatMap((v) => v.parameter_unknowns || []), ...(forms.length ? ["Print forms: aesthetic and print parameters are marked as such in each design file; none is a measurement."] : [])];
    const srcs = pan.sources.map((sid) => m.sources.find((x) => x.id === sid)).filter(Boolean);
    const qs = qOf(snap, scale);
    const cm = snap.coupling_manifest; const here = cm ? cm.couplings.filter((c) => [c.from, c.to].some((x) => snap.projects.model_scale[x.split(".")[0]] === scale)) : [];
    const mc = m.couplings.filter((c) => c.from === scale || c.to === scale);
    const dkey = DRAFT_KEY(p.id, scale);
    return {
      html: html`<section class="pagehead"><p class="eyebrow"><a href="${DF.href("/studio")}">Studio</a> / project</p><h1>${p.title}</h1><p class="lede">${p.goal}</p>${sub}</section>
        ${DF.designReviewPanel(snap, p)}
        ${PD ? projectDraftPanel(PD) : ""}
        <div id="assurance">${DF.assurancePanel(snap.assurance)}</div>
        <div class="studiogrid"><nav aria-label="Subsystems by scale" class="rail"><h2 class="small">Subsystems</h2><ol class="subsyslist">${rail}</ol></nav>
        <div class="studiomain"><section class="panel"><h2>${sc.label} scale</h2><p class="note small">${pan.gap}</p>${cov(scale) ? html`<p class="small"><b>Project record draft:</b> ${U.pill(cov(scale).status.replace(/_/g, " "), cov(scale).status === "implemented_model" ? "ok" : cov(scale).status === "source_only" ? "warn" : "st-unk")} ${cov(scale).note}</p>` : ""}
          <h3>Model</h3>${models}<h3>Media</h3>${media}<h3>Equations and claims</h3>${eqHtml}
          <h3>Parameters and unknowns</h3>${unknowns.length ? html`<ul>${unknowns.map((u) => html`<li>${u}</li>`)}</ul>` : html`<p class="faint small">No parameter list is attached at this scale.</p>`}
          ${srcs.length ? html`<h3>Sources</h3><ul>${srcs.map((s) => html`<li>${U.src("src:" + s.id, s.cite)} ${U.pill(s.read_level, "rl")}</li>`)}</ul>` : ""}
          ${scale === "molecular" ? genomicsPanel(snap) : ""}${scale === "developmental" ? lifecyclePanel(snap) : ""}<h3>Open questions at this scale</h3>${qs.length ? html`<ul>${qs.map((q) => html`<li><a href="${DF.href("/frontier/" + q.id)}"><b>${q.id}</b></a> ${q.title} ${U.pill(DF.annotate(q, snap).approach.replace(/_/g, " "), "ap-" + DF.annotate(q, snap).approach)}</li>`)}</ul>` : html`<p class="faint small">No curated question names this scale.</p>`}<p class="small"><a href="${DF.href("/frontier", { scale })}">Filter the Frontier to this scale</a></p>
          <h3>Couplings</h3>${here.length ? html`<ul>${here.map((c) => html`<li><code>${c.id}</code> ${U.pill(c.status, { composable: "ok", scenario: "warn", refused: "no" }[c.status] || "st-unk")} ${c.from} → ${c.to}</li>`)}</ul><p class="small"><a href="${DF.href("/simulations")}">Reasons and missing calibrations</a></p>` : mc.length ? html`<ul>${mc.map((c) => html`<li>${U.pill(c.status, c.status === "absent" ? "no" : "warn")} ${c.text}</li>`)}</ul>` : html`<p class="faint small">None recorded.</p>`}
        </section>
        <section class="panel" aria-labelledby="ann-h"><h2 id="ann-h">Comments and proposed edits for this subsystem</h2>
          <p class="note warn small"><b>Drafts stay on this browser.</b> Writing here stores a draft locally. Nothing is submitted, no agent is notified and nothing is regenerated. Submitting an annotation needs an operator credential and a route that is not available from this page.</p>
          <label for="annkind" class="small"><b>Kind</b></label> <select id="annkind"><option>comment</option><option>question</option><option>challenge</option><option>proposed_edit</option></select>
          <label for="annbody" class="small"><b>Comment or proposed change for the ${sc.label} subsystem</b></label><textarea id="annbody" rows="3" class="scen" placeholder="What should change, and why?"></textarea>
          <p><button type="button" class="btn small" id="annsave">Save as a local draft</button></p><ul id="annlist"></ul></section>
        <section class="panel" aria-labelledby="sp-h"><h2 id="sp-h">Run a bounded preview</h2><p class="note small"><b>A preview, not a result about a fish.</b> It runs a model with the parameters you set, for a short bounded time, on the node. The request is exactly <code>{model, parameters}</code>; values outside the preview limits are refused, not clamped. Nothing is stored or calibrated, and the plots are the returned numbers only.</p><div id="simwidget"></div></section>
        <section class="panel" aria-labelledby="pl-h"><h2 id="pl-h">Panels waiting for a contract</h2><p class="small">These will appear here when their owners deliver a file contract and data. Until then nothing is shown for them, and nothing is simulated.</p>
          <ul><li><b>Genomic designer.</b> Waiting for the genomic and cell/tissue data slice (claude-11). No genome, sequence or designer output exists on this site.</li><li><b>Autoformalization.</b> Waiting for bounded proposals and checks (director). A proposal would be shown with its check result; a proposal alone is not a verified statement.</li><li><b>Evo2 candidates.</b> Waiting for candidate outputs (bioservices). Model-generated sequence candidates, if shown, are labelled model output, not designs or observations.</li></ul></section>
        <section class="panel"><h2>Regenerating candidate geometry</h2><p class="small">The recorded STL files are outputs of earlier runs. The bounded solver returns an exact point in the encoded model, not a mesh, and this page generates no geometry. <a href="${DF.href("/engineering")}">Open the solver and the print forms</a> to request a solver run; a solver request and a generated artifact are different things.</p></section></div></div>`,
      after(root) {
        const list = root.querySelector("#annlist"); const draw = () => { const d = drafts(dkey); list.innerHTML = d.length ? d.map((x, i) => `<li class="small"><span class="pill st-unk">local draft, not submitted</span> <b>${esc(x.kind || "comment")}</b> ${esc(x.at)}: ${esc(x.body)} <button type="button" class="btn small ghost" data-exp="${i}">Download as Annotation JSON</button> <button type="button" class="btn small ghost" data-del="${i}">Delete</button></li>`).join("") : '<li class="faint small">No drafts for this subsystem.</li>'; list.querySelectorAll("[data-exp]").forEach((b) => b.addEventListener("click", () => { const x = drafts(dkey)[+b.dataset.exp]; const doc = { note: "LOCAL DRAFT in the shape of guilds' Annotation payload. Not submitted: submitting needs an operator credential and a route; anchor.record must be pinned to an exact record version first.", payload: { kind: x.kind || "comment", body: x.body, anchor: { record: null, region: { named_subsystem: { name: p.id + ":" + scale } }, frame: "ui_anchor" } }, drafted_at: x.at }; const url = URL.createObjectURL(new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" })); const a = document.createElement("a"); a.href = url; a.download = "annotation-draft.json"; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000); })); list.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => { const dd = drafts(dkey); dd.splice(+b.dataset.del, 1); saveDrafts(dkey, dd); draw(); })); };
        root.querySelector("#annsave").addEventListener("click", () => { const ta = root.querySelector("#annbody"); const body = ta.value.trim(); if (!body) return; const dd = drafts(dkey); dd.push({ at: new Date().toISOString().replace("T", " ").slice(0, 16), body, kind: root.querySelector("#annkind").value }); if (!saveDrafts(dkey, dd)) { list.insertAdjacentHTML("afterbegin", '<li class="small empty">This browser would not store the draft; nothing was saved.</li>'); return; } ta.value = ""; draw(); });
        draw(); DF.renderMath(root); DF.mountSimWidget(root.querySelector("#simwidget"));
        DF.designReviewWire(root, snap, p);
        DF.assuranceWire(root.querySelector("#assurance"), snap.assurance, (anchor) => { const sc = String(anchor).split(":").pop(); DF.go(DF.href("/studio/" + p.id, { scale: sc === "evolutionary" ? "ecological" : sc })); });
      },
    };
  }

  /* live question count for the landing page (attention layer or catalog), without throwing the snapshot figure away on failure */
  DF.liveQuestionCount = async function () {
    if (!DF.api.isLive()) return null;
    const a = await DF.api.attention();
    if (!a.unavailable && a.report && a.report.view) return { n: a.report.view.n_problems ?? (a.report.view.rows || []).length, source: "attention layer" };
    const r = await DF.api.catalog({ kind: "Problem", limit: 50 }); return { n: r.records.length + (r.next_cursor ? "+" : ""), source: "catalog first page" };
  };
})();
