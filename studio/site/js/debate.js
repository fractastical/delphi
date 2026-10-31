/* Design review: authored, falsifiable challenges on one exact Project version (frontier.project.design-context/1).
 * Not a vote, score or resolution. Live threads come from GET /api/design/context; without a node or a Project record the panel
 * shows repository-sourced review prompts, labelled as such, and local challenge drafts in the contract's shape (never submitted here). */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;
  const KEY = (pid) => `frontier-design-review-draft:${pid}`;
  const refHref = (r) => DF.href("/entity/" + r.kind + "/" + r.id, { v: r.version, ns: r.namespace });
  const key = (r) => JSON.stringify([r.namespace, r.kind, r.id, r.version]);   // one canonical key: property order in a stored ref must not matter
  const same = (a, b) => a && b && a.namespace === b.namespace && a.kind === b.kind && a.id === b.id && a.version === b.version;
  const word = (s) => String(s || "").replace(/_/g, " ");

  DF.designReviewPanel = function (snap, p) {
    const R = snap.design_review;
    if (!R) return html`<section class="panel" id="designreview"><h2>Design review</h2><p class="empty">No review prompts or contract text are present in this snapshot.</p></section>`;
    return html`<section class="panel designreview" id="designreview" aria-labelledby="dr-h"><h2 id="dr-h">Design review: challenges to this design</h2>
      <p class="note small"><b>What this is.</b> ${R.meaning} Replies are ordinary annotations pinned to the same Project version.</p>
      <div id="drlive" role="status">Looking for a Project record on the node…</div>
      <details class="simdet" open><summary><b>Review prompts from repository sources</b> <span class="faint small">${R.source_prompts.length} · not reviewer challenges</span></summary>
        <p class="note small warn">${R.note}</p>
        <div class="drprompts">${R.source_prompts.map((q) => html`<article class="drcard" id="drp-${q.id}"><h3>${q.title}</h3><p class="small">${U.pill(word(q.dimension), "grp")} ${U.pill(q.scale, "grp")} ${U.pill("source-only prompt", "st-unk")}</p>
          <p class="small">${q.observation}</p><p class="small"><b>Challenge to write:</b> ${q.ask}</p><p class="small faint">Source: ${q.source}</p>
          <button type="button" class="btn small ghost" data-seed="${q.id}">Start a challenge from this</button></article>`)}</div>
        <h3>Other dimensions to inspect</h3><ul class="small">${R.general_prompts.map((g) => html`<li>${U.pill(word(g.dimension), "grp")} ${g.text}</li>`)}</ul><p class="small faint">${R.prompts_note}</p></details>
      <h3>Draft a challenge</h3>
      <p class="note warn small"><b>A draft stays in this browser.</b> Nothing is submitted, no one is notified and the Project is not changed. Submitting needs an operator credential: <code>POST /v1/design/reviews</code> with <code>Authorization: Bearer …</code> and an <code>Idempotency-Key</code>. This page never holds a credential. The anchor must be the exact Project version, which the draft marks as unpinned until a Project record supplies it.</p>
      <form id="drform" class="filters" aria-label="Draft a design challenge">
        <label>Dimension <select name="dimension">${R.dimensions.map((d) => html`<option>${d}</option>`)}</select></label>
        <label>Project member (optional, 0 to 59) <input type="number" name="member_index" min="0" max="59" style="width:6rem"></label>
        <label>Evidence basis <select name="evidence_basis">${R.evidence_basis.map((d) => html`<option ${d === "unknown" ? raw("selected") : ""}>${d}</option>`)}</select></label>
        <label class="wide">Challenge (what is wrong or unsupported) <textarea name="body" rows="3" required maxlength="2000"></textarea></label>
        <label class="wide">Scope (what this challenge covers and does not) <textarea name="scope" rows="2" required maxlength="500"></textarea></label>
        <label class="wide">Alternative explanation <textarea name="alternative" rows="2" required maxlength="1000"></textarea></label>
        <label class="wide">Falsifiable next test <textarea name="falsifiable_next_test" rows="2" required maxlength="1000"></textarea></label>
        <label class="wide">Evidence pins (optional; one exact <code>namespace/Kind/id@version</code> per line, at most 12) <textarea name="evidence_refs" rows="2"></textarea></label>
        <button class="btn" type="submit">Save local draft</button></form>
      <p id="drerr" class="small" role="alert"></p><ul id="drdrafts" class="small"></ul></section>`;
  };

  function thread(root, replies) {
    const pl = root.record.payload; const dr = pl.design_review || {}; const refs = dr.evidence_refs || [];
    const card = (it, isRoot) => { const q = it.record.payload; return `<div class="${isRoot ? "drroot" : "drreply"}"><p class="small">${isRoot ? U.pill(word(dr.dimension || "challenge"), "grp").toString() : U.pill(word(q.kind || "reply"), "grp").toString()}${isRoot && dr.evidence_basis ? " " + U.pill("basis: " + dr.evidence_basis, "ev").toString() : ""}${it.member_index != null ? " " + U.pill("member " + it.member_index, "grp").toString() : ""} ${U.pill(it.local_status || "proposed", "st-unk").toString()}${it.record.issuer ? ` <span class="faint">by ${esc(typeof it.record.issuer === "string" ? it.record.issuer : JSON.stringify(it.record.issuer))}</span>` : ""}</p><p>${esc(q.body || "")}</p></div>`; };
    return `<article class="drcard open"><p>${U.pill("open: no resolution state exists", "warn").toString()}</p>${card(root, true)}
      ${dr.scope ? `<p class="small"><b>Scope.</b> ${esc(dr.scope)}</p>` : ""}${dr.alternative ? `<p class="small"><b>Alternative.</b> ${esc(dr.alternative)}</p>` : ""}${dr.falsifiable_next_test ? `<p class="small"><b>Falsifiable next test.</b> ${esc(dr.falsifiable_next_test)}</p>` : ""}
      ${refs.length ? `<p class="small"><b>Evidence pinned:</b> ${refs.map((r) => `<a href="${refHref(r)}">${esc(r.kind)} ${esc(r.id)}</a>`).join(", ")}</p>` : ""}
      ${replies.length ? `<details open><summary class="small">${replies.length} repl${replies.length === 1 ? "y" : "ies"}</summary>${replies.map((r) => card(r, false)).join("")}</details>` : `<p class="small faint">No replies.</p>`}</article>`;
  }

  function parseRefs(txt) {
    const out = []; for (const l of String(txt || "").split("\n").map((x) => x.trim()).filter(Boolean)) { const m = l.match(/^([^/]+)\/([A-Za-z]+)\/(.+)@([0-9a-f]{64})$/); if (!m) return { error: `Not an exact pin: ${l}` }; out.push({ namespace: m[1], kind: m[2], id: m[3], version: m[4] }); }
    return out.length > 12 ? { error: "At most 12 evidence pins" } : { refs: out };
  }

  DF.designReviewWire = function (root, snap, p) {
    const R = snap.design_review; if (!R) return;
    const host = root.querySelector("#drlive"); const form = root.querySelector("#drform"); let project = null;
    const drafts = () => { try { return JSON.parse(localStorage.getItem(KEY(p.id)) || "[]"); } catch (e) { return []; } };
    const save = (d) => { try { localStorage.setItem(KEY(p.id), JSON.stringify(d)); return true; } catch (e) { return false; } };
    const draw = () => { const d = drafts(); root.querySelector("#drdrafts").innerHTML = d.map((x, i) => `<li><span class="pill st-unk">local draft, not submitted</span> <b>${esc(x.payload.design_review.dimension)}</b>: ${esc(x.payload.body.slice(0, 140))} <button type="button" class="btn small ghost" data-del="${i}">Delete</button></li>`).join("") + (d.length ? `<li><button type="button" class="btn small" data-export>Export drafts as JSON</button></li>` : ""); };
    root.querySelector("#designreview").addEventListener("click", (e) => {
      const seed = e.target.closest("[data-seed]"); const del = e.target.closest("[data-del]");
      if (seed) { const q = R.source_prompts.find((x) => x.id === seed.dataset.seed); form.dimension.value = q.dimension; form.body.value = q.observation; form.falsifiable_next_test.value = q.ask; form.scope.focus(); }
      if (del) { const d = drafts(); d.splice(+del.dataset.del, 1); save(d); draw(); }
      if (e.target.closest("[data-export]")) { const w = window.open("", "_blank"); if (w) { w.document.title = "design-review-drafts.json"; w.document.body.innerHTML = "<pre></pre>"; w.document.querySelector("pre").textContent = JSON.stringify(drafts(), null, 2); } }
    });
    form.addEventListener("submit", (e) => {
      e.preventDefault(); const v = Object.fromEntries(new FormData(form)); const err = root.querySelector("#drerr"); err.textContent = "";
      const pr = parseRefs(v.evidence_refs); if (pr.error) { err.textContent = pr.error; return; }
      const dr = { dimension: v.dimension, evidence_basis: v.evidence_basis, scope: v.scope.trim(), evidence_refs: pr.refs, alternative: v.alternative.trim(), falsifiable_next_test: v.falsifiable_next_test.trim() };
      if (v.member_index !== "") { const n = +v.member_index; if (!Number.isInteger(n) || n < 0 || n > 59) { err.textContent = "Member index must be 0 to 59 and exist in the pinned Project."; return; } dr.member_index = n; }
      const draft = { kind: "Annotation", payload: { kind: "challenge", body: v.body.trim(), anchor: { record: project ? project.ref : { namespace: "UNPINNED", kind: "Project", id: p.id, version: "UNPINNED: supply the exact 64-hex Project version" } }, design_review: dr } };
      const d = drafts(); d.push(draft); if (!save(d)) err.textContent = "Browser storage is unavailable, so the draft was not kept."; form.reset(); draw();
    });
    draw();
    if (!DF.api.isLive()) { host.innerHTML = `<p class="empty">No node is connected, so there are no challenge threads to show and none are invented. Live threads appear here when a node serves a Project record and its design context.</p>`; host.removeAttribute("role"); return; }
    (async () => {
      try {
        const want = p.live_project_id;
        if (!want) { host.innerHTML = `<p class="empty">The site's project metadata names no live Project id, so no Project is looked up and nothing is guessed.</p>`; host.removeAttribute("role"); return; }
        const cat = await DF.api.catalog({ kind: "Project", query: want, limit: 50 });
        const cands = cat.records.filter((r) => r.ref.id === want);          // exact id only: no title or fuzzy match
        project = cands.find((r) => r.is_head) || cands[0];
        if (!project) { host.innerHTML = `<p class="empty">The node serves no Project record with id "${esc(want)}" yet, so challenges cannot anchor to an exact version. Nothing is shown in its place.</p>`; host.removeAttribute("role"); return; }
        const roots = [], replies = new Map(); let wh = 0, interp = "", total = 0, cursor = "", more = false;
        const out = document.createElement("div"); host.innerHTML = ""; host.removeAttribute("role"); host.appendChild(out);
        const head = document.createElement("p"); head.className = "drhead"; out.appendChild(head); const list = document.createElement("div"); out.appendChild(list); const foot = document.createElement("div"); out.appendChild(foot);
        const paint = () => {
          head.innerHTML = `<b>${roots.length}</b> challenge${roots.length === 1 ? "" : "s"} on Project <code>${esc(project.ref.id)}</code> at exact version <code>${esc(project.ref.version.slice(0, 12))}…</code>${more ? " (more pages exist)" : ""}. ${U.pill("none resolved: the contract has no resolution state", "warn").toString()}${wh ? ` <span class="faint">${wh} withheld by licence or visibility</span>` : ""}`;
          list.innerHTML = roots.length ? roots.map((r) => thread(r, replies.get(key(r.ref)) || [])).join("") : `<p class="empty">No challenge is recorded against this exact Project version${more ? " on the pages read so far" : ""}.</p>`;
          foot.innerHTML = (interp ? `<p class="small faint">${esc(interp)}</p>` : "") + (more ? `<button type="button" class="btn small" data-drmore>Load more</button>` : "");
          DF.renderMath(list);
        };
        const read = async () => {
          const r = await DF.api.designContext(project.ref, { cursor, limit: 50 }); total++;
          for (const it of r.annotations || []) { const pl = (it.record || {}).payload || {}; if (!it.ref) continue; if (pl.reply_to) { const k = key(pl.reply_to); replies.set(k, [...(replies.get(k) || []), it]); } else if (pl.kind === "challenge") roots.push(it); }
          wh += r.withheld_unlicensed || 0; interp = r.interpretation || interp; cursor = (r.pagination || {}).next_cursor || ""; more = !!cursor; paint();
        };
        foot.addEventListener("click", async (e) => { if (e.target.closest("[data-drmore]")) { try { await read(); } catch (x) { foot.insertAdjacentHTML("beforeend", `<p class="empty" role="alert">Could not load more: ${esc(x.message)}</p>`); } } });
        await read();
      } catch (e) { host.innerHTML = `<p class="empty">Design context is not available from this node (${esc(e.message)}). Nothing is shown in its place.</p>`; host.removeAttribute("role"); }
    })();
  };
})();
