/* Claim browser: readable cards with structured filters and drill-down to the entity page. Works on the live corpus (paged once, then cached)
 * or the snapshot's claims. Organism and gene are NOT structured fields in these records, so that filter is a text match and says so. */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;
  let cache = null;

  async function loadClaims(snap) {
    if (cache && cache.live === DF.api.isLive() && Date.now() - cache.t < 120000) return cache;
    const rows = []; let more = false;
    let after = "", pages = 0;                       // the catalog adapter serves the live node or the snapshot with the same exact refs
    do { const r = await DF.api.catalog({ kind: "Claim", limit: 50, after }); r.records.forEach((x) => rows.push(x)); after = r.next_cursor || ""; pages++; } while (after && pages < 60);
    more = !!after;
    const items = rows.map((x) => facet(x));
    cache = { t: Date.now(), live: DF.api.isLive(), items, more }; return cache;
  }

  function facet(x) {
    const p = x.payload || {}; const pr = p.prior_review || {}; const d = (pr.delphi_original || {}); const g = d.delphi_graph || {}; const src = p.source || {};
    let host = ""; try { host = src.uri ? new URL(src.uri).hostname.replace(/^www\./, "") : ""; } catch (e) { host = ""; }
    return { rec: x, id: x.ref.id, ns: x.ref.namespace, title: x.title, statement: p.statement || "", context: p.context || "", thinker: g.thinker || "", work: g.work || (pr.source_label || ""), year: g.year || "", chapter: g.chapter || "", kind: g.kind || d.kind || "", status: g.status || g.verification || pr.category || "", math: g.math === true, host, domain: d.domain_dir || "", text: (x.title + " " + (p.statement || "") + " " + (p.context || "")).toLowerCase() };
  }
  const uniq = (items, k) => [...new Set(items.map((i) => i[k]).filter((v) => v !== "" && v !== null && v !== undefined))].sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true }));

  DF.knowledgeBrowse = function (snap, route, head) {
    const f = { q: route.params.q || "", t: route.params.t || "", w: route.params.w || "", k: route.params.k || "", s: route.params.s || "", h: route.params.h || "", ns: route.params.ns || "", m: route.params.m || "", y1: route.params.y1 || "", y2: route.params.y2 || "", p: Math.max(0, +route.params.p || 0) };
    return {
      html: html`${head}<section><h2 class="sr">Browse claims</h2><p class="note small">Each card is one claim with its statement, context and source. <b>Upstream labels, truth scores and testability scores are assertions or LLM-elicited numbers from the source corpus; they are shown as such and are never local acceptance or evidence.</b> Select a card for the full page.</p><div id="cbrowse" role="status">Loading the claims…</div></section>`,
      async after(root) {
        const host = root.querySelector("#cbrowse"); let C;
        try { C = await loadClaims(snap); } catch (e) { host.innerHTML = html`<p class="empty">The claims could not be read: ${e.message}. Nothing is shown in their place.</p>`.toString(); return; }
        const it = C.items; const sel = (name, label, vals, cur) => html`<label>${label} <select name="${name}"><option value="">all</option>${vals.map((v) => html`<option ${String(v) === cur ? raw("selected") : ""}>${v}</option>`)}</select></label>`;
        const hit = it.filter((i) => (!f.q || i.text.includes(f.q.toLowerCase())) && (!f.t || i.thinker === f.t) && (!f.w || i.work === f.w) && (!f.k || i.kind === f.k) && (!f.s || i.status === f.s) && (!f.h || i.host === f.h) && (!f.ns || i.ns === f.ns) && (!f.m || (f.m === "yes" ? i.math : !i.math)) && (!f.y1 || +i.year >= +f.y1) && (!f.y2 || +i.year <= +f.y2));
        const per = 25; const page = hit.slice(f.p * per, f.p * per + per); const link = (extra) => DF.href("/knowledge", { tab: "browse", ...Object.fromEntries(Object.entries(f).filter(([, v]) => v !== "" && v !== 0)), ...extra });
        host.removeAttribute("role");
        host.innerHTML = html`<form class="filters" data-form="cb" aria-label="Filter claims">
            <label>Mentions (organism, gene or term; text match) <input type="search" name="q" value="${f.q}" placeholder="e.g. zebrafish, fgf8, spiral"></label>
            ${sel("t", "Thinker", uniq(it, "thinker"), f.t)}${sel("w", "Work", uniq(it, "work"), f.w)}${sel("k", "Claim kind", uniq(it, "kind"), f.k)}${sel("s", "Upstream status", uniq(it, "status"), f.s)}${sel("h", "Source host", uniq(it, "host"), f.h)}${sel("ns", "Namespace", uniq(it, "ns"), f.ns)}
            <label>Has maths <select name="m"><option value="">any</option><option value="yes" ${f.m === "yes" ? raw("selected") : ""}>yes</option><option value="no" ${f.m === "no" ? raw("selected") : ""}>no</option></select></label>
            <label>Year from <input type="number" name="y1" value="${f.y1}" style="width:6rem"></label><label>to <input type="number" name="y2" value="${f.y2}" style="width:6rem"></label>
            <button class="btn" type="submit">Apply</button>${hit.length !== it.length ? html`<a class="btn ghost" href="${DF.href("/knowledge", { tab: "browse" })}">Clear</a>` : ""}</form>
          <p class="small faint">Organism and gene are not structured fields in these records, so “Mentions” matches text in the title, statement and context. A claim that names a gene in a source section this node does not hold will not match.</p>
          <p class="count" role="status">${hit.length} of ${it.length} claims${C.more ? "+ (more exist than were loaded)" : ""} · ${DF.api.isLive() ? "read from the live node" : "from the snapshot"}</p>
          <ul class="claimcards">${page.map((i) => html`<li class="claimcard"><a href="${DF.href("/entity/Claim/" + i.id, { v: i.rec.ref.version, ns: i.ns })}"><h3>${i.title}</h3></a>
            <p class="cstate">${i.statement.length > 260 ? i.statement.slice(0, 260) + "…" : i.statement}</p>
            <p class="small">${[i.thinker, i.work, i.year, i.chapter].filter(Boolean).map((x) => U.pill(String(x), "grp"))} ${i.kind ? U.pill(i.kind, "ev") : ""} ${i.status ? U.pill("upstream: " + i.status, "st-unk") : ""} ${i.math ? U.pill("has maths", "ok") : ""} ${U.pill(i.ns, "grp")}</p>
            <p class="small faint">${i.context.slice(0, 160)}${i.context.length > 160 ? "…" : ""}</p></li>`)}</ul>
          <p class="pager">${f.p > 0 ? html`<a class="btn small ghost" href="${link({ p: f.p - 1 })}">Previous</a>` : ""} <span class="small">Page ${f.p + 1} of ${Math.max(1, Math.ceil(hit.length / per))}</span> ${(f.p + 1) * per < hit.length ? html`<a class="btn small" href="${link({ p: f.p + 1 })}">Next</a>` : ""}</p>`.toString();
        DF.bindForm(root, "cb", (v) => DF.href("/knowledge", { tab: "browse", ...v }));
      },
    };
  };
})();
