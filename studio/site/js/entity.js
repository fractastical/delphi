/* Entity page (route /entity/<Kind>/<id>?v=<version>): one human-readable page for any record, with the raw envelope as an optional advanced view.
 * Every field shown is a field of the record; nothing is inferred. Upstream labels and imported statements stay labelled as assertions. */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;

  const MEDIA_IMG = /^image\/(png|jpeg|gif|webp|svg\+xml)$/; const MEDIA_VID = /^video\/(mp4|webm)$/;
  const list = (a, empty = "None recorded.") => (Array.isArray(a) && a.length ? html`<ul>${a.map((x) => html`<li>${typeof x === "string" ? x : JSON.stringify(x)}</li>`)}</ul>` : html`<p class="faint small">${empty}</p>`);
  const para = (t) => (t ? html`<p>${t}</p>` : "");
  const refLink = (r, label) => (r && r.kind && r.id ? html`<a href="${DF.href("/entity/" + r.kind + "/" + r.id, { v: r.version, ns: r.namespace })}">${label || r.kind + " " + r.id}</a>` : "");
  const src = (s) => (s && typeof s === "object" ? html`<dl class="kv"><div><dt>Source</dt><dd>${DF.safeUrl(s.uri) ? U.ext(s.uri, s.uri) : s.uri || "not stated"}</dd></div><div><dt>Locator</dt><dd>${s.locator || "not stated"}</dd></div><div><dt>Source version</dt><dd>${s.source_version || "not stated"}</dd></div><div><dt>Access</dt><dd>${s.access || "not stated"}</dd></div><div><dt>Licence</dt><dd>${s.license || "not stated"}</dd></div><div><dt>Content hash</dt><dd>${s.content_sha256 ? U.sha(s.content_sha256) : "none"} ${s.content_available ? "" : html`<span class="faint small">content not held here</span>`}</dd></div></dl>` : "");

  function mediaOf(a) {
    const ok = a.availability === "downloadable" && /^https:/.test(a.uri || "");
    if (ok && MEDIA_IMG.test(a.media_type)) return html`<img class="embed" src="${a.uri}" alt="${a.title}" loading="lazy">`;
    if (ok && MEDIA_VID.test(a.media_type)) return html`<video class="embed" controls playsinline preload="metadata" src="${a.uri}" aria-label="${a.title}"></video>`;
    return "";
  }
  function artifacts(arts) {
    if (!Array.isArray(arts) || !arts.length) return html`<p class="faint small">No artifact is declared.</p>`;
    return html`<div class="artgrid">${arts.map((a) => html`<article class="artcard"><h3>${a.title}</h3>${mediaOf(a)}
      <p class="small">${U.pill(a.role, "ev")} ${U.pill(a.media_type, "grp")} ${U.pill(a.availability, a.availability === "downloadable" ? "ok" : "st-unk")}</p>
      <p class="small">${/^https:/.test(a.uri || "") ? U.ext(a.uri, a.uri) : html`<code>${a.uri}</code>`}<br>sha256 ${U.sha(a.sha256)} · ${a.byte_size} bytes${a.license ? " · licence " + a.license : ""}</p>
      <p class="small faint">The digest is declared; the bytes have not been verified by this page.</p></article>`)}</div>`;
  }

  /* Equation: a record's own math, else the snapshot's seed claim with the same id. */
  function equationFor(rec, snap) {
    const p = rec.payload || {}; const m = p.math || (p.prior_review && p.prior_review.math);
    if (m) return m;
    const c = snap.claims.find((x) => x.id === rec.ref.id); return c ? c.math : null;
  }

  /* Imported Delphi claims carry their origin in prior_review.delphi_original; shown readably, with LLM-elicited numbers kept apart and labelled. */
  function delphiBlock(p) {
    const d = (p.prior_review || {}).delphi_original; if (!d) return "";
    const g = d.delphi_graph || {}; const a = d.assessments || {};
    return html`<h2 class="eh">Where it comes from</h2><dl class="kv wide"><div><dt>Thinker</dt><dd>${g.thinker || "not stated"}</dd></div><div><dt>Work</dt><dd>${g.work || "not stated"}${g.year ? ", " + g.year : ""}</dd></div><div><dt>Chapter</dt><dd>${g.chapter || "not stated"}</dd></div><div><dt>Claim kind</dt><dd>${g.kind || d.kind || "not stated"}</dd></div>
      <div><dt>Upstream status</dt><dd>${g.status || g.verification || "not stated"}</dd></div><div><dt>Has maths / theorem</dt><dd>${String(g.math)} / ${String(g.theorem)}</dd></div></dl>
      <p class="note small"><b>Scores are not evidence.</b> ${g.label || ""} ${a.label || ""}</p>
      ${g.truth !== undefined ? html`<p class="small">Upstream numbers, for orientation only: truth ${g.truth}, testability ${g.testability}, disagreement ${g.disagreement}. These come from LLM assessors in the source corpus; they are not measurements and not local review.</p>` : ""}
      <p class="small">${g.nanopub ? html`Optional export: <a href="${g.nanopub}" target="_blank" rel="noopener noreferrer">nanopublication</a> (not a requirement of this page).` : ""}</p>
      <details><summary class="small">Import receipt and permissions</summary><pre class="json">${JSON.stringify({ adapter: (p.prior_review || {}).adapter, permission: d.permission, source_verification: (p.prior_review || {}).source_verification }, null, 1)}</pre></details>`;
  }

  function body(rec, snap, related) {
    const p = rec.payload || {}; const k = rec.ref.kind; const eq = equationFor(rec, snap);
    const eqBlock = eq ? html`<h2 class="eh">Equation</h2>${DF.mixedSpan(eq)}<p class="small faint">Rendered with KaTeX. An expression it cannot render is shown as its TeX source, marked unsupported.</p>` : "";
    if (k === "Claim") return html`<h2 class="eh">Statement</h2>${para(p.statement)}${eqBlock}<h2 class="eh">Context</h2>${para(p.context)}<h2 class="eh">Assumptions</h2>${list(p.assumptions)}<h2 class="eh">Limitations</h2>${list(p.limitations)}<h2 class="eh">Source</h2>${src(p.source)}
      ${delphiBlock(p)}
      ${p.prior_review && Object.keys(p.prior_review).length ? html`<h2 class="eh">Upstream review (an assertion, not local acceptance)</h2><dl class="kv wide">${Object.entries(p.prior_review).filter(([, v]) => typeof v === "string").map(([a, v]) => html`<div><dt>${a.replace(/_/g, " ")}</dt><dd>${v}</dd></div>`)}</dl>` : ""}`;
    if (k === "Evidence") return html`<h2 class="eh">What was done</h2>${para(p.method)}<h2 class="eh">Result context</h2>${para(p.context)}
      <p>${U.pill("evidence kind: " + p.evidence_kind, "ev")} ${p.relation ? U.pill("relation to target: " + p.relation, "grp") : ""}</p><h2 class="eh">Uncertainty</h2>${para(p.uncertainty)}<h2 class="eh">Limitations</h2>${list(p.limitations)}<h2 class="eh">Assumptions</h2>${list(p.assumptions)}
      <h2 class="eh">Artifacts</h2>${artifacts(p.artifacts)}<h2 class="eh">Source</h2>${src(p.source)}${p.source_dependence ? html`<details><summary class="small">Source dependence</summary><pre class="json">${JSON.stringify(p.source_dependence, null, 1)}</pre></details>` : ""}
      ${p.provenance ? html`<details><summary class="small">Provenance</summary><pre class="json">${JSON.stringify(p.provenance, null, 1)}</pre></details>` : ""}`;
    if (k === "Problem") return html`<h2 class="eh">The question</h2>${para(p.question)}<h2 class="eh">What is known</h2>${para(p.known_state)}${eqBlock}<p>${U.pill("completeness: " + (p.completeness || "not stated"), p.completeness === "actionable" ? "ok" : "st-unk")} ${p.problem_kind ? U.pill(p.problem_kind, "grp") : ""}</p>
      ${p.next_action ? html`<h2 class="eh">Next action</h2>${para(p.next_action)}` : ""}${(p.acceptance_criteria || []).length ? html`<h2 class="eh">What would settle it</h2>${list(p.acceptance_criteria)}` : ""}${(p.falsifiers || []).length ? html`<h2 class="eh">Falsifiers</h2>${list(p.falsifiers)}` : ""}
      <h2 class="eh">Capabilities needed</h2>${list(p.required_capabilities)}<h2 class="eh">Data access</h2>${para(p.data_access)}<h2 class="eh">Novelty status</h2>${para(p.novelty_status)}<h2 class="eh">Source</h2>${src(p.source)}`;
    if (k === "Action") return html`<h2 class="eh">What would be done</h2>${para(p.title)}<h2 class="eh">Acceptance criteria</h2>${list(p.acceptance_criteria)}<h2 class="eh">Cost and stop bounds</h2>${para(p.cost_stop_bounds)}<h2 class="eh">Capabilities needed</h2>${list(p.required_capabilities)}
      ${p.target ? html`<p><b>Target:</b> ${refLink(p.target)}</p>` : ""}${(p.inputs || []).length ? html`<p><b>Inputs:</b> ${p.inputs.map((r) => html`${refLink(r)} `)}</p>` : ""}`;
    const scal = Object.entries(p).filter(([, v]) => typeof v === "string" || typeof v === "number" || typeof v === "boolean");
    return html`<dl class="kv wide">${scal.map(([a, v]) => html`<div><dt>${a.replace(/_/g, " ")}</dt><dd>${String(v)}</dd></div>`)}</dl>`;
  }

  DF.views.entity = function (snap, route) {
    const kind = route.parts[1] || "", id = route.parts.slice(2).join("/");
    return {
      html: html`<section class="pagehead"><p class="eyebrow"><a href="${DF.href("/search", { tab: "catalog" })}">Search</a> / ${kind}</p><div id="entity" role="status">Loading ${kind} ${id}…</div></section>`,
      async after(root) {
        const host = root.querySelector("#entity"); const v = route.params.v || "";
        let rec = null;
        try {
          let ref = (DF.recRefs && DF.recRefs[`rec:${kind}:${id}`]) || null;
          if (!ref || (v && ref.version !== v)) {
            const cands = (await DF.api.catalog({ query: id, kind, limit: 50 })).records.filter((x) => x.ref && x.ref.id === id);
            const hit = (v ? cands.find((x) => x.ref.version === v) : null) || cands[0]; ref = hit ? hit.ref : null;
          }
          if (!ref) throw new Error(`no ${kind} with the id “${id}” is visible${DF.api.isLive() ? " on this node" : " in the snapshot"}`);
          rec = await DF.api.record(ref);
        } catch (e) { host.innerHTML = html`<h1>Not found</h1><p class="lede">${e.message}.</p><p><a href="${DF.href("/search", { tab: "catalog" })}">Search the catalog</a></p>`.toString(); return; }
        const p = rec.payload || {}; const r = rec.ref;
        const rel = [];
        if (p.target) rel.push(["Targets", p.target]); if (p.produced_by) rel.push(["Produced by", p.produced_by]);
        (p.inputs || []).forEach((x) => rel.push(["Uses", x])); (p.dependencies || []).forEach((x) => rel.push(["Depends on", x]));
        host.className = ""; host.removeAttribute("role");
        host.innerHTML = html`<h1>${rec.title || r.id}</h1>
          <p>${U.pill(r.kind, "k-" + r.kind)} ${U.pill("local status: " + String(rec.local_status || "not reported").replace(/_/g, " "), "st-unk")} ${rec.is_head === false ? U.pill("not the current version", "warn") : ""}</p>
          <p class="small faint"><code>${r.namespace}/${r.kind}/${r.id}</code> · version ${U.sha(r.version)} · ${rec.issuer ? "issuer " + rec.issuer + " · " : ""}Imported or upstream labels are assertions made elsewhere; a local status is this node's review state only.</p>
          <div class="entlayout"><div class="entmain">${body(rec, snap, rel)}</div>
          <aside class="entside" aria-label="Related"><h2 class="eh">Related</h2>${rel.length ? html`<ul>${rel.map(([a, x]) => html`<li>${a}: ${refLink(x)}</li>`)}</ul>` : html`<p class="faint small">No typed reference in this record.</p>`}<div id="relmore"></div>
            <p class="small"><a class="btn small" href="${DF.href("/graph/" + r.kind + "/" + r.id, { v: r.version, ns: r.namespace })}">Open the neighbourhood graph</a></p></aside></div>
          <details class="advraw"><summary><b>Advanced: raw record envelope</b></summary><pre class="json">${JSON.stringify(rec.raw || rec, null, 2)}</pre></details>`.toString();
        DF.renderMath(host);
        // Evidence that points at this record (a lexical lookup of records that mention its id, filtered to a real typed target reference).
        try {
          const more = (await DF.api.catalog({ query: r.id, limit: 50 })).records.filter((x) => x.ref.id !== r.id && x.payload && x.payload.target && x.payload.target.id === r.id);
          if (more.length) host.querySelector("#relmore").innerHTML = html`<h3>Records that target this one</h3><ul>${more.map((x) => html`<li>${U.pill(x.ref.kind, "k-" + x.ref.kind)} ${refLink(x.ref, x.title)}${x.payload.relation ? html` <span class="faint small">(${x.payload.relation})</span>` : ""}</li>`)}</ul>`.toString();
        } catch (e) { /* the page stands without it */ }
      },
    };
  };
})();
