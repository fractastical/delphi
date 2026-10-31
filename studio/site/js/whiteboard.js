/* Frontier view: the open-questions whiteboard.
 * Top-down: design goal -> constraints -> unresolved questions. Bottom-up: literature and theory evidence ->
 * challenge / reconcile. Both meet in the questions column. Nothing is drawn that a record does not state. */
(function () {
  const DF = window.DF; const { html, raw, fmt } = DF; const U = DF.ui;

  const note = (snap) => snap.mission.whiteboard;
  function annotate(q, snap) {
    const wb = note(snap); const a = wb.annotations[q.id] || {};
    const approach = q.approach || a.approach || "unknown";
    return {
      approach: wb.approaches[approach] ? approach : "unknown",
      fromRecord: !!q.approach,
      scales: q.scales || a.scales || [],
      tags: q.context_tags || a.tags || [],
      owner: q.owner || null,
      limits: a.limits || [], about: a.about || [],
      blockedBy: [...new Set([...(q.depends_on || []), ...(a.blocked_by || [])])],
    };
  }
  DF.annotate = annotate;

  const DIRS = { "": "all directions", topdown: "top-down (design goal, measurement)", bottomup: "bottom-up (theory fit, literature gap)", both: "challenge / reconcile", unknown: "unclassified" };
  const dirOf = (snap, ap) => ({ "top-down": "topdown", "bottom-up": "bottomup", both: "both", unknown: "unknown" })[note(snap).approaches[ap][1]];

  function model(snap, f) {
    const wb = note(snap); const m = snap.mission; const qs = DF.questions(snap);
    const ann = Object.fromEntries(qs.map((q) => [q.id, annotate(q, snap)]));
    const filtering = !!(f.q || f.approach || f.dir || f.scale || f.state);
    const vis = qs.filter((q) => { const a = ann[q.id];
      return (!f.approach || a.approach === f.approach) && (!f.dir || dirOf(snap, a.approach) === f.dir) && (!f.scale || a.scales.includes(f.scale)) && (!f.state || q.state === f.state) &&
        (!f.q || JSON.stringify([q, a]).toLowerCase().includes(f.q.toLowerCase())); });
    const visIds = new Set(vis.map((q) => q.id));
    const cids = new Set(filtering ? vis.flatMap((q) => ann[q.id].limits) : m.constraints.map((c) => c.id));
    const sids = new Set([...vis.flatMap((q) => ann[q.id].about), ...[...cids].flatMap((c) => wb.grounded_in[c] || [])]);
    const claimIds = new Set(vis.flatMap((q) => q.claim_ids || []));
    const nodes = []; const edges = []; const col = { 0: -1, 1: -1, 2: -1, 3: -1 };
    const put = (c, n) => { col[c]++; nodes.push({ ...n, col: c, row: col[c] }); };
    put(0, { id: "G1", label: wb.goal.title, sub: "design goal", cls: "goal" });
    const res = DF.fish.checks(DF.cand, m);
    m.constraints.filter((c) => cids.has(c.id)).forEach((c) => put(1, { id: c.id, label: c.id + " " + c.name, sub: "for candidate: " + res[c.id].status.replace("unknown", "cannot evaluate"), cls: "con st-" + res[c.id].status }));
    vis.forEach((q) => put(2, { id: q.id, label: q.title, sub: q.id + " · " + note(snap).approaches[ann[q.id].approach][0], cls: "ap-" + ann[q.id].approach + (q.state !== "open" ? " done" : "") }));
    m.sources.filter((s) => sids.has(s.id)).forEach((s) => put(3, { id: "src:" + s.id, label: DF.sourceTitle(snap, s.id), sub: s.read_level, cls: "src" }));
    snap.claims.filter((c) => claimIds.has(c.id)).forEach((c) => put(3, { id: "cl:" + c.id, label: c.short, sub: "claim, upstream label only", cls: "claimnode" }));
    cids.forEach((c) => edges.push({ id: "G1>" + c, from: "G1", to: c, kind: "requires", label: `The goal requires ${c} to hold for the candidate` }));
    cids.forEach((c) => (wb.grounded_in[c] || []).forEach((s) => { if (sids.has(s)) edges.push({ id: c + ">src:" + s, from: c, to: "src:" + s, kind: "grounded in", label: `${c} takes its threshold from ${DF.sourceTitle(snap, s)}` }); }));
    vis.forEach((q) => {
      ann[q.id].limits.forEach((c) => { if (cids.has(c)) edges.push({ id: q.id + ">" + c, from: c, to: q.id, kind: "limited by", label: `${c} is limited by the unresolved question ${q.id}` }); });
      ann[q.id].about.forEach((s) => edges.push({ id: q.id + ">src:" + s, from: q.id, to: "src:" + s, kind: "about", label: `${q.id} is about ${DF.sourceTitle(snap, s)}` }));
      (q.claim_ids || []).forEach((c) => edges.push({ id: q.id + ">cl:" + c, from: q.id, to: "cl:" + c, kind: "about", label: `${q.id} concerns the claim ${c}` }));
      ann[q.id].blockedBy.forEach((d) => { if (visIds.has(d)) edges.push({ id: d + ">" + q.id, from: d, to: q.id, kind: "blocks", label: `${d} must be settled before ${q.id}` }); });
    });
    return { nodes, edges, vis, ann, qs, filtering };
  }

  function whyNone(n) { return n ? "" : "nothing"; }

  function detail(snap, sel, mdl) {
    const m = snap.mission; const wb = note(snap);
    if (!sel) return html`<div class="detail-empty"><h3>Select a node or an edge</h3><p>The board reads left to right: the design goal, the constraints it requires, the unresolved questions that limit them, and the literature and theory evidence they rest on. Select anything to see its detail here; the selection stays in the address bar, so Back returns to it.</p></div>`;
    if (sel === "G1") return html`<article class="detail"><p class="eyebrow">Design goal</p><h3>${wb.goal.title}</h3><p>${wb.goal.text}</p><p class="small"><a href="${DF.href("/engineering")}">Work on it in Engineering</a></p></article>`;
    const c = m.constraints.find((x) => x.id === sel);
    if (c) { const r = DF.fish.checks(DF.cand, m)[c.id]; const limiting = mdl.qs.filter((q) => annotate(q, snap).limits.includes(c.id));
      return html`<article class="detail"><p class="eyebrow">Constraint ${c.id}</p><h3>${c.name}</h3><p><code class="rule">${c.rule}</code></p>
        <p>For the current candidate (${DF.candLabel || "custom"}): ${r.status === "pass" ? "pass" : r.status === "fail" ? "fail" : r.status === "disputed" ? "disputed" : "cannot evaluate"}. ${r.detail}</p>
        <p class="small faint">${c.confidence}. ${c.note}</p><h4>Source</h4><p>${U.src("src:" + c.source, DF.sourceTitle(snap, c.source))}</p>
        <h4>Unresolved questions limiting it</h4>${limiting.length ? html`<ul>${limiting.map((q) => html`<li><a href="${DF.href("/frontier/" + q.id)}">${q.id}</a> ${q.title}</li>`)}</ul>` : html`<p class="faint">None recorded.</p>`}
        <p class="small"><a href="${DF.href("/engineering")}">Check it against a candidate</a></p></article>`; }
    if (sel.startsWith("src:")) { const s = m.sources.find((x) => "src:" + x.id === sel); if (!s) return html`<p class="empty">Source not in this snapshot.</p>`;
      const qs = mdl.qs.filter((q) => annotate(q, snap).about.includes(s.id));
      return html`<article class="detail"><p class="eyebrow">Literature evidence</p><h3>${s.cite}</h3><p>${U.pill(s.read_level, "rl")} ${U.pill(s.kind, "ev")}</p><p>${s.note}</p>
        ${s.caveats.length ? html`<h4>Caveats</h4><ul>${s.caveats.map((x) => html`<li>${x}</li>`)}</ul>` : ""}
        ${qs.length ? html`<h4>Questions about it</h4><ul>${qs.map((q) => html`<li><a href="${DF.href("/frontier/" + q.id)}">${q.id}</a> ${q.title}</li>`)}</ul>` : ""}
        <p class="small">${U.src(sel, "Open the full source card")} ${s.url ? html`· ${U.ext(s.url, "Publisher or archive page")}` : ""}</p></article>`; }
    if (sel.startsWith("cl:")) { const cl = snap.claims.find((x) => "cl:" + x.id === sel); if (!cl) return html`<p class="empty">Claim not in this snapshot.</p>`;
      return html`<article class="detail"><p class="eyebrow">Claim (upstream label only)</p><h3>${cl.label}</h3><p>${U.pill(DF.CATEGORY[cl.category].text, DF.CATEGORY[cl.category].cls)}</p><p>${cl.statement}</p><p class="small"><a href="${DF.href("/knowledge/" + cl.id)}">Open in Knowledge</a> · ${U.src("claim:" + cl.id, "Source record")}</p></article>`; }
    const e = mdl.edges.find((x) => x.id === sel);
    if (e) return html`<article class="detail"><p class="eyebrow">Edge · ${e.kind}</p><h3>${e.label}</h3><p class="note small">${{ requires: "The goal is only satisfied if this constraint holds.", "grounded in": "A threshold taken from a source, at that source's read level.", "limited by": "The constraint cannot be strengthened or trusted further until the question is settled.", about: "The question concerns this source or claim.", blocks: "A dependency between questions." }[e.kind]}</p></article>`;
    const q = mdl.qs.find((x) => x.id === sel);
    if (q) return questionDetail(q, snap, mdl);
    return html`<p class="empty">The curated board has no entry with the id “${sel}”. If it is a question in the live node it is in the Questions panel above. Clear the selection to return to the board.</p>`;
  }

  function questionDetail(q, snap, mdl) {
    const a = mdl.ann[q.id]; const wb = note(snap); const byId = Object.fromEntries(mdl.qs.map((x) => [x.id, x]));
    const dependents = mdl.qs.filter((x) => annotate(x, snap).blockedBy.includes(q.id));
    const list = (arr) => (arr && arr.length ? html`<ul>${arr.map((x) => html`<li>${x}</li>`)}</ul>` : html`<p class="faint">None recorded.</p>`);
    return html`<article class="detail" aria-labelledby="qd-t">
      <p class="eyebrow">${q.id} · ${DF.kindText(q.kind)}</p><h3 id="qd-t">${q.title}</h3>
      ${DF.KIND_NOTE[q.kind] ? html`<p class="note small">${DF.KIND_NOTE[q.kind]}</p>` : ""}
      <p>${U.pill(q.state.replace(/_/g, " "), q.state === "open" ? "open" : "done")} ${U.pill(wb.approaches[a.approach][0], "ap-" + a.approach)} ${q.origin === "curated" ? U.pill("curated", "cur") : U.pill("generated", "gen")}</p>
      <p class="small faint">Approach is ${a.fromRecord ? "stated by the record" : "assigned by this site's authors (the record carries no approach field)"}.</p>
      ${q.state === "resolved_in_review" ? html`<p class="note small">“Resolved in review” is an upstream project label, not acceptance by this site.</p>` : ""}
      <dl class="kv wide"><div><dt>Owner</dt><dd>${a.owner || "no owner recorded"}</dd></div><div><dt>Scales</dt><dd>${a.scales.length ? a.scales.map((s) => html`<a class="pill" href="${DF.href("/studio/flying-fish", { scale: s })}" title="Open this subsystem in the Flying fish studio">${(snap.mission.scales.find((x) => x.key === s) || { label: s }).label}</a> `) : "none stated"}</dd></div>
      <div><dt>Context tags</dt><dd>${a.tags.length ? a.tags.join(", ") : "none"}</dd></div>
      <div><dt>Blocked by</dt><dd>${a.blockedBy.length ? a.blockedBy.map((d) => html`<a href="${DF.href("/frontier/" + d)}">${d}</a> `) : "nothing recorded"}</dd></div>
      <div><dt>Limits constraints</dt><dd>${a.limits.length ? a.limits.map((c) => html`<a href="${DF.href("/frontier/" + c)}">${c}</a> `) : "none"}</dd></div></dl>
      <h4>What is known</h4><p>${q.known || q.known_state}</p>
      <h4>The question</h4><p>${q.question}</p>
      <h4>What would settle it</h4><p>${q.acceptance || q.settles_by}</p>
      <h4>Next bounded action</h4><p>${q.next_action}</p>
      <h4>Falsifier</h4>${(q.falsifiers || []).length ? list(q.falsifiers) : html`<p class="faint">No frozen falsifier is recorded. Completeness: <b>${q.completeness || "recorded"}</b>, not actionable until one is frozen. The acceptance text above is prose, not a falsifier.</p>`}
      <h4>Capabilities needed</h4>${list(q.needs)}
      ${dependents.length ? html`<h4>Needed by</h4><ul>${dependents.map((d) => html`<li><a href="${DF.href("/frontier/" + d.id)}">${d.id}</a> ${d.title}</li>`)}</ul>` : ""}
      ${(q.unlocks || []).length ? html`<h4>If settled, it unlocks</h4>${list(q.unlocks)}` : ""}
      ${q.cache ? html`<h4>Reuse</h4><p>${q.cache}</p>` : ""}
      <h4>Who can act</h4><p>${DF.api.state.mode === "live" ? "The runtime is connected; leasing and proposing go through its MCP or HTTP interface, not through this page." : "Snapshot mode is read-only: this page cannot claim, lease or submit work. Agents act through the MCP tools described under Work."}</p>
      <p class="small">${q.source ? U.ext(q.source, "Upstream source") : ""} ${q.coordination_url ? html`· ${U.ext(q.coordination_url, "Coordination thread")} <span class="faint">(${q.coordination_access || "access unknown"})</span>` : ""}${q.derived_from ? html` · Derived from: ${q.derived_from}` : ""}</p>
    </article>`;
  }

  /* ---------- live questions: from /api/attention when present, else the live catalog's Problem records ---------- */
  const val = (x) => (x && typeof x === "object" && "value" in x ? x.value : x);
  let liveCache = null;
  async function liveRows() {
    if (liveCache && Date.now() - liveCache.t < 20000) return liveCache.v;
    let v;
    const a = await DF.api.attention();
    if (!a.unavailable && a.report && a.report.view && Array.isArray(a.report.view.rows)) {
      v = { source: "attention", generated_at: a.report.generated_at, namespace: a.report.namespace, rows: a.report.view.rows.map((r) => ({
        id: r.ref.id, ref: r.ref, kind: val(r.store.problem_kind), completeness: val(r.store.completeness), question: r.store.question, known: r.store.known_state, next: r.store.next_action_text,
        approach: r.store.approach, scales: r.store.scales, tags: r.store.context_tags, ndeps: (r.store.dependencies || []).length, dependents: r.dependents || [], annotation: r.annotation, utility: r.utility,
        assessment: r.assessment, actions: r.actions || [], interests: r.interest_issuers || {}, why: r.why_priority || [], register: r.register_labels })) };
    } else {
      const rows = []; let after = "", pages = 0;
      do { const r = await DF.api.catalog({ kind: "Problem", limit: 50, after }); r.records.forEach((x) => { const p = x.payload || {}; rows.push({ id: x.ref.id, ref: x.ref, kind: p.problem_kind, completeness: p.completeness, question: p.question, known: p.known_state, next: p.next_action, approach: p.approach, scales: p.scales, tags: p.context_tags, ndeps: (p.dependencies || []).length, dependents: [], annotation: null, utility: null, assessment: null, actions: null, interests: {}, why: [], title: p.title, local_status: x.local_status }); }); after = r.next_cursor || ""; pages++; } while (after && pages < 40);
      v = { source: "catalog", reason: a.reason, rows };
    }
    liveCache = { t: Date.now(), v }; return v;
  }

  DF.renderLiveQuestions = async function (host, snap, route) {
    if (!(DF.api.isLive())) { host.innerHTML = html`<section class="panel"><h2>Questions ${U.pill("snapshot", "warn")}</h2><p class="small">Only the curated snapshot projection below is available: ${DF.api.state.mode === "live" ? "the runtime is reachable but this session is not signed in." : "no runtime answered."} The live store's questions appear here when the runtime is reachable and you are signed in.</p></section>`.toString(); return; }
    host.innerHTML = '<section class="panel"><h2>Questions</h2><p role="status">Loading the live questions…</p></section>';
    let L; try { L = await liveRows(); } catch (e) { host.innerHTML = html`<section class="panel"><h2>Questions</h2><p class="empty">The live questions could not be read: ${e.message}. Nothing is shown in their place.</p></section>`.toString(); return; }
    const f = { lq: route.params.lq || "", lk: route.params.lk || "", lc: route.params.lc || "", la: route.params.la || "", lw: route.params.lw || "", ls: route.params.ls || "", n: Math.max(40, +route.params.n || 40) };
    const rows = L.rows; const sel = route.params.live || (route.parts[1] && L.rows.some((r) => r.id === route.parts[1]) ? route.parts[1] : null);
    const owner = (r) => (r.actions ? [...new Set(r.actions.filter((x) => x.lease_live_at_now && x.lease_operator).map((x) => x.lease_operator))] : null);
    const match = (r) => (!f.lk || r.kind === f.lk) && (!f.lc || r.completeness === f.lc) && (!f.la || (r.approach || "none") === f.la) && (!f.lw || (f.lw === "leased" ? (owner(r) || []).length : f.lw === "actions" ? (r.actions || []).length : true)) && (!f.lq || JSON.stringify([r.id, r.question, r.known, r.tags, r.title]).toLowerCase().includes(f.lq.toLowerCase()));
    const info = (r) => (r.completeness === "actionable" ? 4 : 0) + ((r.actions || []).length ? 2 : 0) + (r.approach ? 1 : 0);
    const list = rows.filter(match).sort(f.ls === "id" ? (a, b) => String(a.id).localeCompare(String(b.id)) : (a, b) => info(b) - info(a) || String(a.id).localeCompare(String(b.id))); const shown = list.slice(0, f.n);
    const uniq = (k) => [...new Set(rows.map((r) => r[k] || (k === "approach" ? "none" : "")).filter(Boolean))].sort();
    const hrefF = (extra) => DF.href("/frontier", { ...route.params, ...extra });
    const cur = rows.find((r) => r.id === sel) || shown[0]; const effSel = cur ? cur.id : null;
    const row = (r) => { const o = owner(r); return html`<tr class="${r.id === effSel ? "on" : ""}" data-href="${hrefF({ live: r.id })}"><td><a href="${hrefF({ live: r.id })}" aria-current="${r.id === effSel ? "true" : "false"}"><b>${r.id}</b></a></td><td><a class="qlink" href="${hrefF({ live: r.id })}">${r.title || ""}${r.title ? html`<br>` : ""}<span class="small">${String(r.question || "").slice(0, 160)}${String(r.question || "").length > 160 ? "…" : ""}</span></a></td><td>${U.pill(String(r.completeness || "not stated"), r.completeness === "actionable" ? "ok" : "st-unk")}</td><td>${r.approach ? U.pill(r.approach, "ap-" + r.approach) : html`<span class="faint small">not stated</span>`}</td><td>${o === null ? html`<span class="faint small">needs attention layer</span>` : o.length ? o.join(", ") : html`<span class="faint small">none recorded</span>`}</td><td>${r.actions === null ? "" : (r.actions || []).length}</td></tr>`; };
    const det = cur ? liveDetail(cur) : html`<div class="detail-empty"><h3>Select a question</h3><p>Pick a row to see what the store declares about it: state, who holds a live lease, actions, dependents, and why it is ranked where it is.</p></div>`;
    host.innerHTML = html`<section class="panel livepanel" aria-labelledby="lq-h"><h2 id="lq-h">Questions ${U.pill("live", "ok")} <span class="faint small">${rows.length} in the node${L.source === "attention" ? ", via the attention layer" : ", via the catalog (attention layer unavailable, so no owners or actions)"}</span></h2>
      <p class="small faint">Read just now from the runtime${L.generated_at ? " (" + L.generated_at + ")" : ""}. This is the store's own list, separate from the curated mission projection below. A count of records is not a measure of progress, and priority is not truth.</p>
      <form class="filters" data-form="frontier" aria-label="Filter the live questions"><label>Search <input type="search" name="lq" value="${f.lq}" placeholder="id, text or tag"></label>
        <label>Kind <select name="lk"><option value="">all</option>${uniq("kind").map((k) => html`<option ${k === f.lk ? raw("selected") : ""}>${k}</option>`)}</select></label>
        <label>Completeness <select name="lc"><option value="">all</option>${uniq("completeness").map((k) => html`<option ${k === f.lc ? raw("selected") : ""}>${k}</option>`)}</select></label>
        <label>Approach <select name="la"><option value="">all</option>${uniq("approach").map((k) => html`<option ${k === f.la ? raw("selected") : ""}>${k}</option>`)}</select></label>
        ${L.source === "attention" ? html`<label>Work <select name="lw"><option value="">any</option><option value="leased" ${f.lw === "leased" ? raw("selected") : ""}>live lease held</option><option value="actions" ${f.lw === "actions" ? raw("selected") : ""}>has an action</option></select></label>` : ""}
        <label>Sort <select name="ls"><option value="">most informative first</option><option value="id" ${f.ls === "id" ? raw("selected") : ""}>id</option></select></label><input type="hidden" name="live" value="${sel || ""}"><button class="btn" type="submit">Apply</button>${f.lq || f.lk || f.lc || f.la || f.lw ? html`<a class="btn ghost" href="${DF.href("/frontier", sel ? { live: sel } : {})}">Clear</a>` : ""}</form>
      ${rows.some((r) => r.kind === "curated_question") ? html`<p class="note small"><b>Curated questions.</b> Records of kind curated_question are a curator's questions with cited sources, proposed and recorded; they are not field-stated open problems. Quotes are the curator's transcription (most are unreviewed; a 15-item sample check is not an error rate), and importance or tractability labels are not value.</p>` : ""}<p class="small">${(() => { const rec = rows.filter((r) => r.completeness !== "actionable").length; return `${rec} of ${rows.length} are recorded only: the store keeps a question as recorded until it has acceptance criteria, falsifiers, a next action and stop bounds, and refuses an action against it until then. Approach, scales and tags are shown only when the record states them.`; })()}</p>
      <p class="count" role="status">${list.length} of ${rows.length} shown (${shown.length} on screen)</p>
      <div class="split graphsplit"><div class="tablewrap"><table class="qtable"><thead><tr><th>Id</th><th>Question</th><th>Completeness</th><th>Approach</th><th>Live lease holder</th><th>Actions</th></tr></thead><tbody>${shown.map(row)}</tbody></table>
        ${list.length > shown.length ? html`<p><a class="btn small" href="${hrefF({ n: f.n + 60 })}">Show 60 more</a></p>` : ""}</div><div class="detail-col" id="lqdetail" tabindex="-1">${det}</div></div></section>`.toString();
    DF.bindForm(host, "frontier", (vals) => DF.href("/frontier", vals)); DF.renderMath(host);
    host.querySelectorAll("tr[data-href]").forEach((tr) => tr.addEventListener("click", (e) => { if (e.target.closest("a")) return; DF.go(tr.dataset.href); }));
  };

  function liveDetail(r) {
    const o = r.actions ? [...new Set(r.actions.filter((x) => x.lease_live_at_now && x.lease_operator).map((x) => x.lease_operator))] : null;
    return html`<article class="detail"><p class="eyebrow">${r.id} · ${r.kind || "kind not stated"}</p><h3>${r.title || String(r.question || r.id).slice(0, 120)}</h3>
      <p>${U.pill(String(r.completeness || "not stated"), r.completeness === "actionable" ? "ok" : "st-unk")} ${r.approach ? U.pill(r.approach, "ap-" + r.approach) : ""} ${U.pill("live", "ok")}</p>
      ${r.completeness && r.completeness !== "actionable" ? html`<p class="note small">Recorded only: no Action can target it until acceptance criteria, falsifiers, a next action and stop bounds exist.</p>` : ""}
      <dl class="kv wide"><div><dt>Live lease holder</dt><dd>${o === null ? "needs the attention layer" : o.length ? o.join(", ") : "none recorded"}</dd></div><div><dt>Scales (as the record states)</dt><dd>${(r.scales || []).join(", ") || "not stated"}</dd></div><div><dt>Context tags</dt><dd>${(r.tags || []).join(", ") || "not stated"}</dd></div>
        <div><dt>Dependencies / dependents</dt><dd>${r.ndeps} / ${(r.dependents || []).length}</dd></div></dl>
      <h4>The question</h4><p>${r.question}</p><h4>What is known</h4><p>${r.known}</p>${r.next ? html`<h4>Next action (as written)</h4><p>${r.next}</p>` : ""}
      ${r.actions ? html`<h4>Actions</h4>${r.actions.length ? html`<div class="tablewrap"><table><thead><tr><th>Action</th><th>State</th><th>Live lease</th><th>Operator</th></tr></thead><tbody>${r.actions.map((x) => html`<tr><td><code>${x.id}</code></td><td>${x.state}</td><td>${String(x.lease_live_at_now)}</td><td>${x.lease_operator || ""}</td></tr>`)}</tbody></table></div>` : html`<p class="faint">No action targets it.</p>`}` : ""}
      ${r.assessment !== undefined && r.assessment !== null ? html`<h4>Assessment (truth, kept separate from priority)</h4><p class="small">${typeof r.assessment === "object" ? JSON.stringify(r.assessment) : r.assessment}</p>` : ""}
      ${r.utility ? html`<p class="small"><b>Utility:</b> ${r.utility.status}${r.utility.evpi !== null && r.utility.evpi !== undefined ? ", declared value " + r.utility.evpi + " " + (r.utility.unit || "") : ", unknown; nothing is imputed"}.</p>` : ""}
      ${(r.why || []).length ? html`<details><summary class="small">Why it sits where it does (${r.why.length} reasons)</summary><ul>${r.why.map((w) => html`<li class="small"><code>${w.field}</code> = ${typeof w.value === "object" ? JSON.stringify(w.value) : w.value}: ${w.effect}</li>`)}</ul></details>` : ""}
      <p class="small faint">${r.ref ? `${r.ref.namespace}/${r.ref.kind}/${r.ref.id}` : ""} ${r.ref ? "version " + String(r.ref.version).slice(0, 12) + "…" : ""}</p></article>`;
  }

  DF.views.frontier = function (snap, route) {
    const wb = note(snap); const m = snap.mission;
    const f = { q: route.params.q || "", approach: route.params.approach || "", dir: route.params.dir || "", scale: route.params.scale || "", state: route.params.state || "" };
    const sel = route.parts[1] || null;
    const mdl = model(snap, f);
    const sc = mdl.nodes.length;
    const keep = (extra = {}) => ({ ...f, ...extra });
    const dirChips = Object.entries(DIRS).map(([k, t]) => html`<a class="chip ${f.dir === k ? "on" : ""}" href="${DF.href("/frontier" + (sel ? "/" + sel : ""), keep({ dir: k, approach: "" }))}" aria-current="${f.dir === k ? "true" : "false"}">${t}</a>`);
    const open = mdl.qs.filter((q) => q.state === "open").length;
    const rowFor = (q) => { const a = mdl.ann[q.id]; return html`<tr class="${q.id === sel ? "on" : ""}"><td><a href="${DF.href("/frontier/" + q.id, f)}" aria-current="${q.id === sel ? "true" : "false"}"><b>${q.id}</b></a></td><td>${q.title}</td><td>${U.pill(wb.approaches[a.approach][0], "ap-" + a.approach)}</td>
      <td>${a.scales.length ? a.scales.map((s) => (m.scales.find((x) => x.key === s) || { label: s }).label).join(", ") : "none stated"}</td><td>${U.pill(q.state.replace(/_/g, " "), q.state === "open" ? "open" : "done")}</td><td>${a.owner || html`<span class="faint">none recorded</span>`}</td>
      <td>${a.blockedBy.length ? a.blockedBy.join(", ") : html`<span class="faint">none</span>`}</td><td>${[...a.about.map((s) => U.src("src:" + s, s)), ...(q.claim_ids || []).map((c) => html`<a href="${DF.href("/knowledge/" + c)}">${c}</a>`)].map((x, i) => html`${i ? ", " : ""}${x}`)}</td></tr>`; };

    const scaleChips = m.scales.map((s, i) => html`<li><a class="scale ${s.have.length ? "has" : "none"}" href="${DF.href("/engineering", { scale: s.key })}"><span class="n">${i + 1}</span><b>${s.label}</b><small>${s.have.length ? s.have.length + " source" + (s.have.length > 1 ? "s" : "") : "no source indexed"}</small></a></li>`);

    return {
      html: html`
      <section class="hero compact"><div><p class="eyebrow">MorphoSwarm Frontier · open work</p><h1>What we know.<br>What's next.<br>Who's working on it.</h1></div>
        <div class="herotext"><p class="lede">An open-questions whiteboard where a design goal and the literature meet. <b>Top-down</b>: goal, then constraints, then what is unresolved. <b>Bottom-up</b>: theory and evidence fitted to known biology, then challenged and reconciled. The questions column is where they have to agree.</p>
          <p class="mission"><b>Mission</b> Engineer toward a flying fish.</p></div></section>

      <div id="livepanel"></div>
      <section class="panel board" aria-labelledby="wb-h">
        <h2 id="wb-h">Open-questions whiteboard</h2>
        <p class="note small"><b>Curated mission projection from the snapshot.</b> Approach, scales and blockers here are site-assigned until a record states its own (the record's value wins). No owner appears unless a record names one.<details><summary class="small">How these annotations were made</summary><p class="small">${wb.note}</p></details></p>
        <div class="chips" role="group" aria-label="Direction">${dirChips}</div>
        <form class="filters" role="search" aria-label="Filter the whiteboard" data-form="frontier">
          <label>Search <input type="search" name="q" value="${f.q}" placeholder="text, tag or owner"></label>
          <label>Approach <select name="approach"><option value="">all</option>${Object.entries(wb.approaches).map(([k, v]) => html`<option value="${k}" ${k === f.approach ? raw("selected") : ""}>${v[0]}</option>`)}</select></label>
          <label>Scale <select name="scale"><option value="">all</option>${m.scales.map((s) => html`<option value="${s.key}" ${s.key === f.scale ? raw("selected") : ""}>${s.label}</option>`)}</select></label>
          <label>State <select name="state"><option value="">all</option>${[...new Set(mdl.qs.map((q) => q.state))].map((s) => html`<option value="${s}" ${s === f.state ? raw("selected") : ""}>${s.replace(/_/g, " ")}</option>`)}</select></label>
          <input type="hidden" name="dir" value="${f.dir}">
          <button type="submit" class="btn">Apply</button>${mdl.filtering ? html`<a class="btn ghost" href="${DF.href("/frontier" + (sel ? "/" + sel : ""))}">Clear</a>` : ""}
        </form>
        <p class="count" role="status">${mdl.vis.length} of ${mdl.qs.length} questions shown · ${open} open in total · counts of records in this snapshot, not progress</p>
        <div class="split graphsplit"><div><div class="graphhost board-graph" id="wbgraph"></div></div><div class="detail-col" id="qdetail" tabindex="-1">${detail(snap, sel, mdl)}</div></div>
        <h3>The board as a table</h3>
        <p class="small faint">The same questions as text, with owner, status, scales, blockers and sources. An owner appears only when a record names one.</p>
        ${mdl.vis.length ? html`<div class="tablewrap"><table class="qtable"><thead><tr><th>Id</th><th>Question</th><th>Approach</th><th>Scales</th><th>State</th><th>Owner</th><th>Blocked by</th><th>Sources</th></tr></thead><tbody>${mdl.vis.map(rowFor)}</tbody></table></div>` : U.empty("No question matches these filters.")}
      </section>

      <section class="panel missionview" aria-labelledby="mv">
        <div class="mv-head"><h2 id="mv">Mission view: eleven scales, one design</h2>
          <p class="note small">Each scale is a way to look at the same design. Showing a scale does not mean an executable model exists there; ${m.scales.filter((s) => s.have.length).length} of 11 have at least one indexed source.</p></div>
        <div class="mv-body"><div class="mv-fish"><div id="fishmini" class="fishmini"></div></div><ol class="scales" aria-label="The eleven MorphoSwarm scales; each opens Engineering at that scale">${scaleChips}</ol></div></section>`,
      async after(root) {
        DF.mountFishMini(root.querySelector("#fishmini"));
        DF.renderLiveQuestions(root.querySelector("#livepanel"), snap, route);
        const cls = { goal: "goal", con: "con" };
        DF.graph.draw(root.querySelector("#wbgraph"), {
          columns: [{ title: "Design goal" }, { title: "Constraints" }, { title: "Unresolved questions" }, { title: "Literature and theory" }],
          nodes: mdl.nodes, edges: mdl.edges, selected: sel && mdl.edges.some((e) => e.id === sel) ? { type: "edge", id: sel } : { type: "node", id: sel },
          ariaLabel: "Open-questions whiteboard: design goal, constraints, unresolved questions and literature",
          legend: [{ cls: "goal", text: "design goal" }, { cls: "con st-pass", text: "constraint (outline = status for the current candidate)" }, ...Object.entries(wb.approaches).map(([k, v]) => ({ cls: "ap-" + k, text: v[0] })), { cls: "src", text: "source" }, { cls: "claimnode", text: "claim" }],
          onSelect(type, id) { DF.go(DF.href("/frontier/" + id, f)); },
        });
        DF.bindForm(root, "frontier", (vals) => DF.href("/frontier" + (sel ? "/" + sel : ""), vals));
      },
    };
  };
})();
