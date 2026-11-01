/* App shell: hash router, source drawer, header, error handling. All state that should survive Back lives in the hash. */
(function () {
  const DF = window.DF; const { html, esc } = DF;
  DF.views = DF.views || {};
  const leave = []; DF.onLeave = (fn) => leave.push(fn);

  /* ---- routing: #/view/sel?key=val ---- */
  function parse(hash) {
    const h = (hash || "").replace(/^#/, "") || "/home"; const [path, qs] = h.split("?");
    const parts = path.split("/").filter(Boolean).map((p) => { try { return decodeURIComponent(p); } catch (e) { return p; } });
    const params = {}; new URLSearchParams(qs || "").forEach((v, k) => (params[k] = v));
    return { path: "/" + parts.join("/"), parts: parts.length ? parts : ["frontier"], params, view: (parts[0] || "frontier") };
  }
  const qstr = (p) => { const u = new URLSearchParams(); Object.entries(p || {}).forEach(([k, v]) => { if (v !== "" && v !== null && v !== undefined) u.set(k, v); }); const s = u.toString(); return s ? "?" + s : ""; };
  DF.href = (path, params) => "#" + path.split("/").map((p, i) => (i && p ? encodeURIComponent(p).replace(/%3A/g, ":") : p)).join("/") + qstr(params);
  DF.hrefWith = (extra) => { const r = DF.route || parse(location.hash); return DF.href(r.path, { ...r.params, ...extra }); };
  DF.go = (href) => { if (href === location.hash) render(); else location.hash = href; };
  DF.bindForm = (root, name, build) => root.querySelectorAll(`form[data-form="${name}"]`).forEach((form) => form.addEventListener("submit", (e) => {
    e.preventDefault(); const v = {}; new FormData(form).forEach((val, k) => { if (String(val).trim()) v[k] = String(val).trim(); }); DF.go(build(v));
  }));

  const ABOUT = [["/about", "Overview"], ["/about/team", "Team"], ["/about/docs", "Documentation"], ["/about/inspirations", "Motivation & inspirations"], ["/generative", "Generative biology"]];
  const NAV = [["studio", "Studio"], ["frontier", "Frontier"], ["knowledge", "Knowledge"], ["evidence", "Evidence"], ["work", "System"]];
  const STUDIO_GROUP = new Set(["studio", "engineering", "simulations", "belief", "formalize", "history", "regulatory"]);       // reached from a project; they highlight Studio
  const inNav = (k, view) => view === k || (k === "studio" && STUDIO_GROUP.has(view)) || (k === "knowledge" && view === "entity") || (k === "work" && view === "system");
  let snap = null; let lastView = null; let opener = null;
  document.addEventListener("click", (e) => { const am = document.querySelector(".aboutmenu details"); if (am && am.open && !am.contains(e.target)) am.open = false; }, true);   // one listener for the life of the page

  function header(route) {
    const s = DF.api.state; const live = s.mode === "live";
    return html`<div class="bar"><a class="brand" href="${DF.href("/home")}"><svg class="mark" viewBox="0 0 44 28" width="44" height="28" aria-hidden="true" focusable="false"><defs><linearGradient id="mk" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#c8f24a"/><stop offset="1" stop-color="#2bb3a3"/></linearGradient></defs><path d="M3 15c5-8 14-9 21-5 4 2 6 4 8 5-2 1-4 3-8 5-7 4-16 3-21-5z" fill="url(#mk)"/><path d="M32 15l8-7v14z" fill="url(#mk)" opacity=".85"/><circle cx="9" cy="13.5" r="1.4" fill="#0e2433"/><path d="M14 8c3-4 6-6 12-7M17 7c4-1 8 0 12 3M12 20c2 3 5 5 10 6" fill="none" stroke="#c8f24a" stroke-width="1.3" stroke-linecap="round"/><g fill="#c8f24a"><circle cx="26" cy="1.2" r="1.5"/><circle cx="29.5" cy="10" r="1.5"/><circle cx="22" cy="26" r="1.5"/></g></svg>MorphoSwarm <b>Frontier</b><span class="brandsub">claims and evidence: Delphi</span></a>
      <nav aria-label="Views"><ul>${NAV.map(([k, t]) => html`<li><a href="${DF.href("/" + k)}" aria-current="${inNav(k, route.view) ? "page" : "false"}">${t}</a></li>`)}
        <li class="aboutmenu"><details><summary class="${route.view === "about" || route.view === "generative" ? "on" : ""}">About</summary><ul aria-label="About">${ABOUT.map(([h, t]) => html`<li><a href="${DF.href(h)}">${t}</a></li>`)}</ul></details></li></ul></nav>
      <form class="gsearch" role="search" id="gs"><label class="sr" for="gq">Search the catalog</label><input id="gq" type="search" placeholder="Search records" value="${route.view === "search" ? route.params.q || "" : ""}"><button class="btn small" type="submit">Search</button></form>
      <span class="mode ${live ? "live" : "snap"}" title="${esc(s.reason)}">${live ? "Live runtime" : "Snapshot"}</span></div>
      ${live && !s.publicAccess && s.authenticated === false ? html`<div class="banner" role="status"><b>Runtime reachable, not signed in.</b> Records need a session: <a href="/login">sign in</a>. Until then the catalog, artifacts and solver are unavailable, and the page shows the snapshot.</div>` : ""}
      ${live ? "" : html`<div class="banner" role="status"><b>Snapshot, not live.</b> No runtime answered (${s.reason}). Everything shown comes from <code>${snap ? snap.label : "the committed snapshot"}</code>. Local controls are calculations in this browser; nothing is submitted.</div>`}`;
  }

  async function render() {
    leave.splice(0).forEach((f) => { try { f(); } catch (e) { /* ignore */ } });
    const route = (DF.route = parse(location.hash));
    const hdr = document.getElementById("hdr"); const main = document.getElementById("main");
    if (!snap) return;
    hdr.innerHTML = header(route).toString();
    if (DF.attachSearch) DF.attachSearch();
    const am = hdr.querySelector(".aboutmenu details");
    if (am) {                                          // native <details> menu: expose its state, close on Escape (focus returns to the button) and on an outside click or Tab away
      const sm = am.querySelector("summary"), ul = am.querySelector("ul"); ul.id = "aboutlist"; sm.setAttribute("aria-controls", "aboutlist"); sm.setAttribute("aria-expanded", "false"); sm.setAttribute("aria-haspopup", "true");
      am.addEventListener("toggle", () => sm.setAttribute("aria-expanded", am.open ? "true" : "false"));
      am.addEventListener("keydown", (e) => { if (e.key === "Escape" && am.open) { e.preventDefault(); am.open = false; sm.focus(); } });
      am.addEventListener("focusout", (e) => { if (am.open && e.relatedTarget && !am.contains(e.relatedTarget)) am.open = false; });
    }
    document.getElementById("gs").addEventListener("submit", (e) => { e.preventDefault(); const q = document.getElementById("gq").value.trim(); DF.go(DF.href("/search", { q, tab: "catalog" })); });
    const fn = DF.views[route.view];
    const y = lastView === route.view ? window.scrollY : 0;
    document.title = (route.view[0].toUpperCase() + route.view.slice(1)) + " · MorphoSwarm Frontier";
    if (!fn) { main.innerHTML = html`<section class="pagehead"><h1>Not found</h1><p class="lede">${route.view === "about" || route.view === "generative" ? "This page is delivered by a module that is not part of this build yet." : "There is no view called “" + route.view + "”."} Choose one from the navigation above.</p></section>`.toString(); }
    else {
      try {
        const out = fn(snap, route); main.innerHTML = out.html.toString(); DF.renderMath(main);
        if (out.after) await out.after(main);
      } catch (e) {
        console.error(e); main.innerHTML = html`<section class="pagehead"><h1>This view could not be drawn</h1><p class="lede">${e.message}</p><p>The data may be malformed. <a href="${DF.href("/frontier")}">Return to Frontier</a>.</p></section>`.toString();
      }
    }
    if (lastView !== route.view) { try { main.focus({ preventScroll: true }); } catch (e) { /* focus is best effort */ } }   // keyboard and screen-reader users land at the new view, not on the old link
    lastView = route.view; window.scrollTo(0, y);
    await drawer(route);
  }

  /* ---- source drawer: every source link opens a useful artifact ---- */
  async function drawer(route) {
    const el = document.getElementById("drawer"); const id = route.params.src;
    if (!id) { if (!el.hidden) { el.hidden = true; document.body.classList.remove("drawer-open"); if (opener && document.contains(opener)) opener.focus(); } return; }
    const wasHidden = el.hidden; el.hidden = false; document.body.classList.add("drawer-open");
    if (wasHidden && history.state === null) history.replaceState({ openedDrawer: true }, "");
    el.querySelector(".dbody").innerHTML = "<p>Loading…</p>"; el.querySelector("#dtitle").textContent = "Source";
    try {
      const r = await drawerContent(id);
      el.querySelector("#dtitle").textContent = r.title; el.querySelector(".dbody").innerHTML = r.body.toString(); DF.renderMath(el);
    } catch (e) {
      el.querySelector("#dtitle").textContent = "Source not available"; el.querySelector(".dbody").innerHTML = html`<p class="empty">Could not open “${id}”: ${e.message}. Nothing is shown in its place.</p>`.toString();
    }
    if (wasHidden) el.querySelector("#dclose").focus();
  }
  function closeDrawer() {
    const r = DF.route;
    if (history.state && history.state.openedDrawer) history.back(); else { const p = { ...r.params }; delete p.src; history.replaceState(null, ""); location.replace(DF.href(r.path, p)); }
  }

  async function drawerContent(id) {
    const [type, ...rest] = id.split(":"); const key = rest.join(":");
    if (type === "doc") {
      const d = snap.documents.find((x) => x.id === key); if (!d) throw new Error("no such document in this snapshot");
      const r = await fetch(d.href, { cache: "no-store" }); if (!r.ok) throw new Error("HTTP " + r.status);
      return { title: d.title, body: html`<p class="small">${DF.ui.pill("document", "ev")} <code>${d.path}</code> · sha256 <code>${d.sha256}</code> · <a href="${d.href}">raw file</a></p><div class="md">${DF.markdown(await r.text())}</div>` };
    }
    if (type === "src") {
      const s = snap.mission.sources.find((x) => x.id === key); if (!s) throw new Error("no such source");
      const qs = DF.questions(snap).filter((q) => (snap.mission.whiteboard.annotations[q.id] || {}).about && snap.mission.whiteboard.annotations[q.id].about.includes(s.id));
      const cons = snap.mission.constraints.filter((c) => c.source === s.id);
      return { title: s.cite, body: html`<p>${DF.ui.pill(s.read_level, "rl")} ${DF.ui.pill(s.kind, "ev")}</p><h4>What it supports here</h4><p>${s.note}</p>
        ${s.caveats.length ? html`<h4>Caveats</h4><ul>${s.caveats.map((c) => html`<li>${c}</li>`)}</ul>` : ""}
        ${cons.length ? html`<h4>Constraints that rest on it</h4><ul>${cons.map((c) => html`<li><b>${c.id}</b> ${c.name}: <code>${c.rule}</code> (${c.confidence})</li>`)}</ul>` : ""}
        ${qs.length ? html`<h4>Open questions about it</h4><ul>${qs.map((q) => html`<li><a href="${DF.href("/frontier/" + q.id)}">${q.id}</a> ${q.title}</li>`)}</ul>` : ""}
        <h4>Where to read it</h4><p>${s.url ? DF.ui.ext(s.url, s.url) : "No link: the page does not guess an address it has not verified."}</p>
        <p class="small faint">Read level is the research report's own, recorded at ${snap.label}. Report origin and hash are listed under the mission origin in <code>snapshot.json</code>.</p>` };
    }
    if (type === "claim") {
      const c = snap.claims.find((x) => x.id === key); if (!c) throw new Error("no such claim");
      return { title: c.label, body: html`<p>${DF.ui.pill(DF.CATEGORY[c.category].text, DF.CATEGORY[c.category].cls)}</p><p class="note small">${DF.CATEGORY[c.category].help}</p>
        <h4>Statement</h4><p>${c.statement}</p><h4>Equation</h4>${DF.mixedSpan(c.math)}<h4>Context</h4><p>${c.context}</p><h4>Upstream source</h4><p>${c.source}</p>
        <h4>Record</h4><p class="small">sha256 <code>${c.record_sha256}</code><br>${DF.ui.ext(c.source_url, "Record on GitHub")} <span class="faint">(repository may require access)</span></p>
        <h4>Evidence entries</h4>${c.evidence.length ? html`<ul>${c.evidence.map((e) => html`<li>${DF.ui.pill(e.kind, "ev")} ${DF.ui.ext(e.url, e.label)}</li>`)}</ul>` : html`<p class="faint">None.</p>`}
        <p class="small">Seed revision <code>${snap.scope.seed_source_revision}</code>. ${snap.scope.claims}.</p>` };
    }
    if (type === "rec") {
      const [kind, ...r2] = rest; const rid = r2.join(":");
      let ref = (DF.recRefs && DF.recRefs[id]) || (DF.api.state.catalog.records.find((x) => x.ref.kind === kind && x.ref.id === rid) || {}).ref;
      if (!ref) { const hit = (await DF.api.catalog({ query: rid, kind, limit: 50 })).records.find((x) => x.ref && x.ref.id === rid); if (hit) ref = hit.ref; }
      if (!ref) throw new Error("no record with that id is visible to this session");
      const rec = await DF.api.record(ref);
      return { title: rec.title || rid, body: html`<p class="note small">Full record envelope as the adapter returned it. Local status is separate from any upstream label.</p><pre class="json">${JSON.stringify(rec.raw || rec, null, 2)}</pre>` };
    }
    throw new Error("unknown source type “" + type + "”");
  }

  /* ---- boot ---- */
  async function boot() {
    const main = document.getElementById("main");
    try { await DF.api.load(); snap = DF.api.state.snapshot; DF.initCandidate(snap); }
    catch (e) {
      main.innerHTML = html`<section class="pagehead"><h1>Data could not be loaded</h1><p class="lede">${e.message}.</p><p>The page needs <code>data/snapshot.json</code> and <code>data/catalog.json</code> next to it (built by <code>scripts/build_site.py</code>). Nothing is shown in their place.</p><p><button class="btn" type="button" id="retry">Try again</button></p></section>`.toString();
      document.getElementById("retry").addEventListener("click", () => location.reload()); return;
    }
    const foot = document.getElementById("foot");
    foot.innerHTML = html`<p><b>${snap.label}</b> · ${snap.inputs.length} input files hashed · <a href="data/snapshot.json">snapshot.json</a> · <a href="data/catalog.json">catalog.json</a> · KaTeX 0.16.47 (MIT, <a href="vendor/katex/LICENSE">licence</a>)</p>
      <details><summary>Input files and sha256</summary><div class="tablewrap"><table><tbody>${snap.inputs.map((i) => html`<tr><td><code>${i.path}</code></td><td><code>${i.sha256}</code></td><td>${i.bytes} bytes</td></tr>`)}</tbody></table></div></details>
      <p class="small faint">Geometry is a design visualisation, not an observed fish and not CFD. Calculations are browser arithmetic on published fits. Upstream review labels are assertions, never local acceptance. Live: records, search, questions, System and the solver read the running node when it answers. From the snapshot: the curated mission board, recorded results and media, labelled with the snapshot above. No votes, scores or progress figures are shown.</p>`.toString();
    document.addEventListener("click", (e) => { const a = e.target.closest("a[data-src]"); if (a) opener = a; });
    document.getElementById("dclose").addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !document.getElementById("drawer").hidden) closeDrawer(); });
    window.addEventListener("hashchange", render);
    await render();
  }
  DF.boot = boot;
  document.addEventListener("DOMContentLoaded", boot);
})();
