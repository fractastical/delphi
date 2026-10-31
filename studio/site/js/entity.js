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
    return html`<div class="artgrid">${arts.map((a) => html`<article class="artcard"><h4>${a.title}</h4>${mediaOf(a)}
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

  function body(rec, snap, related) {
    const p = rec.payload || {}; const k = rec.ref.kind; const eq = equationFor(rec, snap);
    const eqBlock = eq ? html`<h3>Equation</h3>${DF.mixedSpan(eq)}<p class="small faint">Rendered with KaTeX. An expression it cannot render is shown as its TeX source, marked unsupported.</p>` : "";
    if (k === "Claim") return html`<h3>Statement</h3>${para(p.statement)}${eqBlock}<h3>Context</h3>${para(p.context)}<h3>Assumptions</h3>${list(p.assumptions)}<h3>Limitations</h3>${list(p.limitations)}<h3>Source</h3>${src(p.source)}
      ${p.prior_review && Object.keys(p.prior_review).length ? html`<h3>Upstream review (an assertion, not local acceptance)</h3><dl class="kv wide">${Object.entries(p.prior_review).filter(([, v]) => typeof v === "string").map(([a, v]) => html`<div><dt>${a.replace(/_/g, " ")}</dt><dd>${v}</dd></div>`)}</dl>` : ""}`;
    if (k === "Evidence") return html`<h3>What was done</h3>${para(p.method)}<h3>Result context</h3>${para(p.context)}
      <p>${U.pill("evidence kind: " + p.evidence_kind, "ev")} ${p.relation ? U.pill("relation to target: " + p.relation, "grp") : ""}</p><h3>Uncertainty</h3>${para(p.uncertainty)}<h3>Limitations</h3>${list(p.limitations)}<h3>Assumptions</h3>${list(p.assumptions)}
      <h3>Artifacts</h3>${artifacts(p.artifacts)}<h3>Source</h3>${src(p.source)}${p.source_dependence ? html`<details><summary class="small">Source dependence</summary><pre class="json">${JSON.stringify(p.source_dependence, null, 1)}</pre></details>` : ""}
      ${p.provenance ? html`<details><summary class="small">Provenance</summary><pre class="json">${JSON.stringify(p.provenance, null, 1)}</pre></details>` : ""}`;
    if (k === "Problem") return html`<h3>The question</h3>${para(p.question)}<h3>What is known</h3>${para(p.known_state)}${eqBlock}<p>${U.pill("completeness: " + (p.completeness || "not stated"), p.completeness === "actionable" ? "ok" : "st-unk")} ${p.problem_kind ? U.pill(p.problem_kind, "grp") : ""}</p>
      ${p.next_action ? html`<h3>Next action</h3>${para(p.next_action)}` : ""}${(p.acceptance_criteria || []).length ? html`<h3>What would settle it</h3>${list(p.acceptance_criteria)}` : ""}${(p.falsifiers || []).length ? html`<h3>Falsifiers</h3>${list(p.falsifiers)}` : ""}
      <h3>Capabilities needed</h3>${list(p.required_capabilities)}<h3>Data access</h3>${para(p.data_access)}<h3>Novelty status</h3>${para(p.novelty_status)}<h3>Source</h3>${src(p.source)}`;
    if (k === "Action") return html`<h3>What would be done</h3>${para(p.title)}<h3>Acceptance criteria</h3>${list(p.acceptance_criteria)}<h3>Cost and stop bounds</h3>${para(p.cost_stop_bounds)}<h3>Capabilities needed</h3>${list(p.required_capabilities)}
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
          <aside class="entside" aria-label="Related"><h3>Related</h3>${rel.length ? html`<ul>${rel.map(([a, x]) => html`<li>${a}: ${refLink(x)}</li>`)}</ul>` : html`<p class="faint small">No typed reference in this record.</p>`}<div id="relmore"></div>
            <p class="small"><a class="btn small" href="${DF.href("/graph/" + r.kind + "/" + r.id, { v: r.version, ns: r.namespace })}">Open the neighbourhood graph</a></p></aside></div>
          <details class="advraw"><summary><b>Advanced: raw record envelope</b></summary><pre class="json">${JSON.stringify(rec.raw || rec, null, 2)}</pre></details>`.toString();
        DF.renderMath(host);
        // Evidence that points at this record (a lexical lookup of records that mention its id, filtered to a real typed target reference).
        try {
          const more = (await DF.api.catalog({ query: r.id, limit: 50 })).records.filter((x) => x.ref.id !== r.id && x.payload && x.payload.target && x.payload.target.id === r.id);
          if (more.length) host.querySelector("#relmore").innerHTML = html`<h4>Records that target this one</h4><ul>${more.map((x) => html`<li>${U.pill(x.ref.kind, "k-" + x.ref.kind)} ${refLink(x.ref, x.title)}${x.payload.relation ? html` <span class="faint small">(${x.payload.relation})</span>` : ""}</li>`)}</ul>`.toString();
        } catch (e) { /* the page stands without it */ }
      },
    };
  };
})();
