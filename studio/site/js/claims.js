/* Claim browser: readable cards with structured filters and drill-down to the entity page. Works on the live corpus (paged once, then cached)
 * or the snapshot's claims. Organism and gene are NOT structured fields in these records, so that filter is a text match and says so. */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;
  function facet(x) {
    const p = x.payload || {}; const pr = p.prior_review || {}; const d = (pr.delphi_original || {}); const g = d.delphi_graph || {}; const src = p.source || {};
    let host = ""; try { host = src.uri ? new URL(src.uri).hostname.replace(/^www\./, "") : ""; } catch (e) { host = ""; }
    return { rec: x, id: x.ref.id, ns: x.ref.namespace, title: x.title, statement: p.statement || "", context: p.context || "", thinker: g.thinker || "", work: g.work || (pr.source_label || ""), year: g.year || "", chapter: g.chapter || "", kind: g.kind || d.kind || "", status: g.status || g.verification || pr.category || "", math: g.math === true, host, domain: d.domain_dir || "", text: (x.title + " " + (p.statement || "") + " " + (p.context || "")).toLowerCase() };
  }
  const uniq = (items, k) => [...new Set(items.map((i) => i[k]).filter((v) => v !== "" && v !== null && v !== undefined))].sort((a, b) => String(a).localeCompare(String(b), undefined, { numeric: true }));

  DF.knowledgeBrowse = function (snap, route, head) {
    const f = { q: route.params.q || "", t: route.params.t || "", w: route.params.w || "", k: route.params.k || "", s: route.params.s || "", h: route.params.h || "", ns: route.params.ns || "", m: route.params.m || "", y1: route.params.y1 || "", y2: route.params.y2 || "", p: 0 };
    return {
      html: html`${head}<section><h2 class="sr">Browse claims</h2><p class="note small">Each card is one claim with its statement, context and source. <b>Upstream labels, truth scores and testability scores are assertions or LLM-elicited numbers from the source corpus; they are shown as such and are never local acceptance or evidence.</b> Select a card for the full page.</p><div id="cbrowse" role="status">Loading the claims…</div></section>`,
      async after(root) {
        const host = root.querySelector("#cbrowse"); host.removeAttribute("role");
        const FACETS = [["t", "Thinker", "thinker"], ["w", "Work", "work"], ["k", "Claim kind", "kind"], ["s", "Upstream status", "status"], ["h", "Source host", "host"], ["ns", "Namespace", "ns"]];
        const opts = (v, cur) => html`<option value="">all</option>${v.map((x) => html`<option ${String(x) === cur ? raw("selected") : ""}>${x}</option>`)}`;
        const sel = (name, label, key, cur) => html`<label>${label} <select name="${name}" data-facet="${key}">${opts(cur ? [cur] : [], cur)}</select></label>`;
        const active = Object.entries(f).some(([k, v]) => k !== "p" && v !== "");
        const match = (i) => (!f.t || i.thinker === f.t) && (!f.w || i.work === f.w) && (!f.k || i.kind === f.k) && (!f.s || i.status === f.s) && (!f.h || i.host === f.h) && (!f.ns || i.ns === f.ns) && (!f.m || (f.m === "yes" ? i.math : !i.math)) && (!f.y1 || +i.year >= +f.y1) && (!f.y2 || +i.year <= +f.y2);
        const card = (i) => html`<li class="claimcard"><a href="${DF.href("/entity/Claim/" + i.id, { v: i.rec.ref.version, ns: i.ns })}"><h3>${i.title}</h3></a>
            <p class="cstate">${i.statement.length > 260 ? i.statement.slice(0, 260) + "…" : i.statement}</p>
            <p class="small">${[i.thinker, i.work, i.year, i.chapter].filter(Boolean).map((x) => U.pill(String(x), "grp"))} ${i.kind ? U.pill(i.kind, "ev") : ""} ${i.status ? U.pill("upstream: " + i.status, "st-unk") : ""} ${i.math ? U.pill("has maths", "ok") : ""} ${U.pill(i.ns, "grp")}</p>
            <p class="small faint">${i.context.slice(0, 160)}${i.context.length > 160 ? "…" : ""}</p></li>`.toString();
        host.innerHTML = html`<form class="filters" data-form="cb" aria-label="Filter claims">
            <label>Mentions (organism, gene or term; text match) <input type="search" name="q" value="${f.q}" placeholder="e.g. zebrafish, fgf8, spiral"></label>
            ${FACETS.map(([n, l, k]) => sel(n, l, k, f[n]))}
            <label>Has maths <select name="m"><option value="">any</option><option value="yes" ${f.m === "yes" ? raw("selected") : ""}>yes</option><option value="no" ${f.m === "no" ? raw("selected") : ""}>no</option></select></label>
            <label>Year from <input type="number" name="y1" value="${f.y1}" style="width:6rem"></label><label>to <input type="number" name="y2" value="${f.y2}" style="width:6rem"></label>
            <button class="btn" type="submit">Apply</button>${active ? html`<a class="btn ghost" href="${DF.href("/knowledge", { tab: "browse" })}">Clear</a>` : ""}</form>
          <p class="small faint">Organism and gene are not structured fields in these records, so “Mentions” is sent to the node as a text query. The other filters apply to the claims loaded so far; more load as you scroll, and their choices grow with them.</p>
          <p class="count" role="status" id="cbcount"></p>
          <ul class="claimcards" id="cblist"></ul>
          <div id="cbmore" class="pager"></div>`.toString();
        const list = host.querySelector("#cblist"), more = host.querySelector("#cbmore"), count = host.querySelector("#cbcount");
        const S = { after: "", done: false, busy: false, err: "", loaded: 0, shown: 0, ctl: null, seen: new Set(), vals: Object.fromEntries(FACETS.map(([, , k]) => [k, new Set()])) };
        let dead = false; DF.onLeave(() => { dead = true; if (S.ctl) S.ctl.abort(); });
        const stat = () => { count.textContent = `${S.shown} claims shown of ${S.loaded} loaded${S.done ? " (end of the list)" : ", more available"} · ${DF.api.isLive() ? "read from the live node" : "from the snapshot"}`; };
        const growFacets = (items) => {
          for (const [n, , k] of FACETS) {
            for (const i of items) if (i[k] !== "" && i[k] != null) S.vals[k].add(i[k]);
            const el = host.querySelector(`select[name=${n}]`); if (!el) continue;
            const have = new Set([...el.options].map((o) => o.value)); const add = [...S.vals[k]].filter((v) => !have.has(String(v)));
            for (const v of add) { const o = document.createElement("option"); o.textContent = String(v); el.appendChild(o); }
            const sorted = [...el.options].slice(1).sort((a, b) => a.text.localeCompare(b.text, undefined, { numeric: true })); sorted.forEach((o) => el.appendChild(o));
            el.value = f[n];
          }
        };
        const paint = () => {
          if (S.err) more.innerHTML = html`<p class="empty" role="alert">Could not load more claims: ${S.err}</p><button type="button" class="btn small" data-more>Retry</button>`.toString();
          else if (S.busy) more.innerHTML = '<p class="small" role="status">Loading more claims…</p>';
          else if (S.done) more.innerHTML = S.shown ? '<p class="small faint">End of the list.</p>' : '<p class="empty">No claim matches these filters among those the node returned.</p>';
          else more.innerHTML = '<button type="button" class="btn small" data-more>Load more</button>';
          stat();
        };
        const loadMore = async () => {
          if (S.busy || S.done || dead) return;
          S.busy = true; S.err = ""; paint(); S.ctl = new AbortController(); const ctl = S.ctl;
          try {
            const r = await DF.api.catalog({ kind: "Claim", query: f.q, limit: 50, after: S.after, signal: ctl.signal });
            if (dead || ctl.signal.aborted) return;
            const items = r.records.filter((x) => !S.seen.has(x.ref.namespace + "/" + x.ref.id + "@" + x.ref.version)).map((x) => { S.seen.add(x.ref.namespace + "/" + x.ref.id + "@" + x.ref.version); return facet(x); });
            S.loaded += items.length; growFacets(items);
            const keep = items.filter(match); S.shown += keep.length;
            if (keep.length) list.insertAdjacentHTML("beforeend", keep.map(card).join(""));
            S.after = r.next_cursor || ""; S.done = !S.after;
          } catch (e) { if (!ctl.signal.aborted && !dead) S.err = e.message; }
          finally { if (!dead && !ctl.signal.aborted) { S.busy = false; paint(); if (!S.err && !S.done && inView()) loadMore(); } }
        };
        const inView = () => more.getBoundingClientRect().top < window.innerHeight + 600;
        more.addEventListener("click", (e) => { if (e.target.closest("[data-more]")) loadMore(); });
        if ("IntersectionObserver" in window) { const io = new IntersectionObserver((en) => { if (en.some((x) => x.isIntersecting)) loadMore(); }, { rootMargin: "600px" }); io.observe(more); DF.onLeave(() => io.disconnect()); }
        paint(); loadMore();
        DF.bindForm(root, "cb", (v) => DF.href("/knowledge", { tab: "browse", ...v }));
      },
    };
  };
})();
