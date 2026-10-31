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

  /* ---------------------------------------------------------------- home */
  DF.views.home = function (snap) {
    const p = fish(snap); const forms = snap.print_forms ? snap.print_forms.forms : []; const vids = (snap.simulation_manifests || []).filter((m) => m.video_state === "present_verified" && m.poster_href);
    const openQ = DF.questions(snap).filter((q) => q.state === "open").length; const withModel = Object.values(p.panels).filter((x) => x.models.length).length;
    return {
      html: html`<section class="hero compact"><div><p class="eyebrow">MorphoSwarm Frontier</p><h1>Design together.<br>Know what's open.</h1></div>
        <div class="herotext"><p class="lede">Two ways in, one body of evidence. <b>Studio</b> is where a design goal is worked across scales, with the models, media and gaps in one place. <b>Frontier</b> is the shared list of open questions and who is working on them. Both read the same claims and evidence, kept in the Delphi foundation: what we know, what's next, who's working on it.</p></div></section>
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
        try { const L = await DF.liveQuestionCount(); if (L) root.querySelector("#homeq").parentElement.innerHTML = `<b>${L.n}</b> questions in the live node <span class="faint small">(${esc(L.source)})</span>`; } catch (e) { /* the snapshot figure stays */ }
      },
    };
  };

  /* ---------------------------------------------------------------- projects list */
  DF.views.studio = function (snap, route) {
    const id = route.parts[1];
    if (id) return projectStudio(snap, route, id);
    return {
      html: html`<section class="pagehead"><h1>Studio</h1><p class="lede">Design projects, each broken into subsystems by scale. ${snap.projects.note}</p></section>
        <section class="panel"><h2 class="sr">Projects</h2>${snap.projects.projects.map((p) => html`<article class="card pform"><h3>${p.title} ${p.featured ? U.pill("featured", "gen") : ""} ${U.pill(p.status, "st-unk")}</h3><p><b>Goal.</b> ${p.goal}</p><p class="small">${p.summary}</p><p><a class="btn" href="${DF.href("/studio/" + p.id)}">Open studio</a></p></article>`)}
        <p class="note small">${snap.projects.other_projects_note}</p><p class="small faint">Starting a new project needs a Project record and a credentialed submission route; this page does not create one.</p></section>`,
    };
  };

  /* ---------------------------------------------------------------- one project */
  const DRAFT_KEY = (pid, scale) => `frontier-annotation-draft:${pid}:${scale}`;
  const drafts = (k) => { try { return JSON.parse(localStorage.getItem(k) || "[]"); } catch (e) { return []; } };
  const saveDrafts = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } };

  function projectStudio(snap, route, id) {
    const p = snap.projects.projects.find((x) => x.id === id);
    if (!p) return { html: html`<section class="pagehead"><h1>No such project</h1><p class="lede">There is no project “${id}” in this snapshot. <a href="${DF.href("/studio")}">See the projects</a>.</p></section>` };
    const m = snap.mission; const scale = route.params.scale && p.panels[route.params.scale] ? route.params.scale : "organism"; const pan = p.panels[scale]; const sc = m.scales.find((s) => s.key === scale);
    const sub = html`<nav class="subnav" aria-label="Project sections"><a href="${DF.href("/studio/" + p.id)}" aria-current="page">Studio</a><a href="${DF.href("/engineering")}">Engineering workspace</a><a href="${DF.href("/simulations")}">Simulations</a><a href="${DF.href("/belief")}">Belief</a><a href="${DF.href("/frontier", { scale })}">Open questions at this scale</a></nav>`;
    const rail = m.scales.map((s, i) => { const pn = p.panels[s.key]; const st = pn.models.length ? "model" : hasContent(pn) ? "partial" : "gap";
      return html`<li><a class="subsys ${st} ${s.key === scale ? "on" : ""}" href="${DF.href("/studio/" + p.id, { scale: s.key })}" aria-current="${s.key === scale ? "true" : "false"}"><span class="n">${i + 1}</span><b>${s.label}</b><small>${st === "model" ? "recorded model" : st === "partial" ? "partial" : "gap"}</small></a></li>`; });
    const models = pan.models.length ? html`<div class="cards">${pan.models.map((mid) => { const mm = modelOf(snap, mid); return mm ? html`<article class="card"><h4>${mm.name}</h4><p class="small">${U.pill(mm.status || "status not stated", "st-unk")} ${mm.engine ? U.pill(mm.engine, "grp") : ""} ports: ${mm.ports}</p><p class="small"><b>Scope.</b> ${mm.scope || ""}</p><p class="small"><b>Not established.</b> ${(mm.not_established || []).join("; ") || "not stated"}</p></article>` : html`<article class="card"><h4>${mid}</h4><p class="small faint">Named in the project but not in the coupling manifest.</p></article>`; })}</div>` : html`<p class="empty">No model is attached at this scale. ${pan.gap}</p>`;
    const vids = pan.videos.map((v) => vidOf(snap, v)).filter(Boolean);
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
        <div class="studiogrid"><nav aria-label="Subsystems by scale" class="rail"><h2 class="small">Subsystems</h2><ol class="subsyslist">${rail}</ol></nav>
        <div class="studiomain"><section class="panel"><h2>${sc.label} scale</h2><p class="note small">${pan.gap}</p>
          <h3>Model</h3>${models}<h3>Media</h3>${media}<h3>Equations and claims</h3>${eqHtml}
          <h3>Parameters and unknowns</h3>${unknowns.length ? html`<ul>${unknowns.map((u) => html`<li>${u}</li>`)}</ul>` : html`<p class="faint small">No parameter list is attached at this scale.</p>`}
          ${srcs.length ? html`<h3>Sources</h3><ul>${srcs.map((s) => html`<li>${U.src("src:" + s.id, s.cite)} ${U.pill(s.read_level, "rl")}</li>`)}</ul>` : ""}
          <h3>Open questions at this scale</h3>${qs.length ? html`<ul>${qs.map((q) => html`<li><a href="${DF.href("/frontier/" + q.id)}"><b>${q.id}</b></a> ${q.title} ${U.pill(DF.annotate(q, snap).approach.replace(/_/g, " "), "ap-" + DF.annotate(q, snap).approach)}</li>`)}</ul>` : html`<p class="faint small">No curated question names this scale.</p>`}<p class="small"><a href="${DF.href("/frontier", { scale })}">Filter the Frontier to this scale</a></p>
          <h3>Couplings</h3>${here.length ? html`<ul>${here.map((c) => html`<li><code>${c.id}</code> ${U.pill(c.status, { composable: "ok", scenario: "warn", refused: "no" }[c.status] || "st-unk")} ${c.from} → ${c.to}</li>`)}</ul><p class="small"><a href="${DF.href("/simulations")}">Reasons and missing calibrations</a></p>` : mc.length ? html`<ul>${mc.map((c) => html`<li>${U.pill(c.status, c.status === "absent" ? "no" : "warn")} ${c.text}</li>`)}</ul>` : html`<p class="faint small">None recorded.</p>`}
        </section>
        <section class="panel" aria-labelledby="ann-h"><h2 id="ann-h">Comments and proposed edits for this subsystem</h2>
          <p class="note warn small"><b>Drafts stay on this browser.</b> Writing here stores a draft locally. Nothing is submitted, no agent is notified and nothing is regenerated. Submitting an annotation needs an operator credential and a route that is not available from this page.</p>
          <label for="annbody" class="small"><b>Comment or proposed change for the ${sc.label} subsystem</b></label><textarea id="annbody" rows="3" class="scen" placeholder="What should change, and why?"></textarea>
          <p><button type="button" class="btn small" id="annsave">Save as a local draft</button></p><ul id="annlist"></ul></section>
        <section class="panel"><h2>Regenerating candidate geometry</h2><p class="small">The recorded STL files are outputs of earlier runs. The bounded solver returns an exact point in the encoded model, not a mesh, and this page generates no geometry. <a href="${DF.href("/engineering")}">Open the solver and the print forms</a> to request a solver run; a solver request and a generated artifact are different things.</p></section></div></div>`,
      after(root) {
        const list = root.querySelector("#annlist"); const draw = () => { const d = drafts(dkey); list.innerHTML = d.length ? d.map((x, i) => `<li class="small"><span class="pill st-unk">local draft, not submitted</span> ${esc(x.at)}: ${esc(x.body)} <button type="button" class="btn small ghost" data-del="${i}">Delete</button></li>`).join("") : '<li class="faint small">No drafts for this subsystem.</li>'; list.querySelectorAll("[data-del]").forEach((b) => b.addEventListener("click", () => { const dd = drafts(dkey); dd.splice(+b.dataset.del, 1); saveDrafts(dkey, dd); draw(); })); };
        root.querySelector("#annsave").addEventListener("click", () => { const ta = root.querySelector("#annbody"); const body = ta.value.trim(); if (!body) return; const dd = drafts(dkey); dd.push({ at: new Date().toISOString().replace("T", " ").slice(0, 16), body }); if (!saveDrafts(dkey, dd)) { list.insertAdjacentHTML("afterbegin", '<li class="small empty">This browser would not store the draft; nothing was saved.</li>'); return; } ta.value = ""; draw(); });
        draw(); DF.renderMath(root);
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
