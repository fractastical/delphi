/* Data adapters. One surface for the runtime (live) and the committed snapshot.
 * Nothing here fabricates a result: when an interface is not connected the adapter throws Unavailable. */
(function () {
  const DF = window.DF;
  class Unavailable extends Error {
    constructor(name, detail) { super(`${name} is not connected`); this.name = "Unavailable"; this.adapter = name; this.detail = detail; }
  }
  const state = { mode: "snapshot", health: null, reason: "not probed", snapshot: null, catalog: null };

  const isLive = () => state.mode === "live" && (state.publicAccess === true || state.authenticated === true);

  async function getJSON(url, ms = 3000, signal = null) {
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
    if (signal) signal.addEventListener("abort", () => ctl.abort(), { once: true });
    try {
      const r = await fetch(url, { signal: ctl.signal, headers: { Accept: "application/json" }, cache: "no-store" });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const ct = r.headers.get("content-type") || "";
      if (!/json/i.test(ct)) throw new Error(`not JSON (${ct || "no content-type"})`);
      return await r.json();
    } finally { clearTimeout(t); }
  }

  async function load() {
    const [snap, cat] = await Promise.all([getJSON("data/snapshot.json", 8000), getJSON("data/catalog.json", 8000)]);
    if (!snap || snap.schema !== "frontier-site-snapshot-0.1" || !Array.isArray(snap.claims) || !Array.isArray(snap.problems)) throw new Error("snapshot.json has an unexpected shape");
    if (!cat || !Array.isArray(cat.records)) throw new Error("catalog.json has an unexpected shape");
    state.snapshot = snap; state.catalog = cat;
    try {
      const h = await getJSON("api/health", 2500);
      if (h && (h.status === "ok" || h.ok === true || h.status === "live")) {
        state.mode = "live"; state.health = h; state.reason = "runtime answered /api/health";
        try { const s = await getJSON("api/session", 3000); state.authenticated = !!s.authenticated; state.publicAccess = s.public_access === true; } catch (e) { state.authenticated = false; state.publicAccess = false; }
      }
      else { state.reason = "/api/health answered but did not report ok"; }
    } catch (e) { state.reason = "runtime unavailable (" + (e.name === "AbortError" ? "timeout" : e.message) + ")"; }
    return state;
  }

  /* Live rows are {record:{namespace,kind,id,version,payload,...}, local_status, is_head, action, why_matched}; the page uses one shape for both modes. */
  function norm(row) {
    const rec = row.record || row; const p = rec.payload || {};
    return { ref: { namespace: rec.namespace, kind: rec.kind, id: rec.id, version: rec.version }, title: p.title || rec.id, payload: p, local_status: row.local_status, is_head: row.is_head,
      why_matched: row.why_matched === undefined ? undefined : [].concat(row.why_matched), policy_version: row.policy_version, issuer: rec.issuer, source_uri: rec.source_uri, action: row.action, raw: row };
  }

  /* Catalog: GET /api/catalog?query&kind&status&limit<=50&after -> {records, next_cursor, namespace, mode}. */
  async function catalog({ query = "", kind = "", status = "", limit = 20, after = "" } = {}) {
    limit = Math.max(1, Math.min(50, limit | 0 || 20));
    if (isLive()) {
      const q = new URLSearchParams(); if (query) q.set("query", query); if (kind) q.set("kind", kind); if (status) q.set("status", status); q.set("limit", String(limit)); if (after) q.set("after", after);
      const r = await getJSON("api/catalog?" + q.toString());
      return { records: (r.results || []).map(norm), next_cursor: r.next_cursor || null, namespace: r.namespace || null, mode: r.mode || "live", search_mode: r.search_mode || null, source: "runtime" };
    }
    const needle = query.trim().toLowerCase();
    const rows = state.catalog.records.filter((rec) => (!kind || rec.ref.kind === kind) && (!status || rec.local_status === status) &&
      (!needle || JSON.stringify([rec.title, rec.payload]).toLowerCase().includes(needle)));
    const start = after ? Math.max(0, rows.findIndex((r) => r.ref.id === after) + 1) : 0;
    const page = rows.slice(start, start + limit);
    return { records: page, next_cursor: start + limit < rows.length ? page[page.length - 1].ref.id : null, namespace: state.catalog.namespace, mode: "snapshot", total_matching: rows.length, source: state.catalog.snapshot };
  }

  async function record(ref) {
    if (isLive()) {
      const q = new URLSearchParams({ namespace: ref.namespace, kind: ref.kind, id: ref.id, version: ref.version });
      const r = await getJSON("api/record?" + q.toString()); const n = norm(r); n.raw = r; return n;
    }
    const hit = state.catalog.records.find((r) => r.ref.kind === ref.kind && r.ref.id === ref.id && (!ref.version || r.ref.version === ref.version));
    if (!hit) throw new Error("record not in snapshot");
    return hit;
  }

  /* GET /api/artifacts?limit&after -> {items:[{artifact,evidence,target,produced_by,evidence_kind,relation,context,limitations,local_status,is_head,artifact_bytes_verified}], next_cursor} */
  async function artifacts({ limit = 50, after = "" } = {}) {
    if (!isLive()) return { items: [], next_cursor: null, source: "snapshot" };
    const q = new URLSearchParams({ limit: String(Math.min(50, limit)) }); if (after) q.set("after", after);
    const r = await getJSON("api/artifacts?" + q.toString());
    return { items: Array.isArray(r.items) ? r.items : [], next_cursor: r.next_cursor || null, source: "runtime" };
  }

  /* GET /api/system: shape not yet specified by the runtime owner, so it is returned as received and shown as received. */
  async function system() {
    if (!isLive()) return { unavailable: true, reason: "no live runtime" };
    try { return { report: await getJSON("api/system") }; } catch (e) { return { unavailable: true, reason: e.message }; }
  }

  /* GET /api/media?sha256= -> {matches[{href,sha256,byte_size,media_type,bytes_verified}], scope, index}. Local availability only; the Evidence's own declaration is never changed. null when not served. */
  async function media(sha) {
    if (!isLive() || state.mediaAbsent === true || !/^[0-9a-f]{64}$/.test(String(sha))) return null;
    try { return await getJSON("api/media?sha256=" + sha, 6000); } catch (e) { if (/HTTP 404/.test(e.message)) state.mediaAbsent = true; return null; }
  }

  async function events() {
    if (isLive()) { const r = await getJSON("api/events?limit=50"); return { events: (r.events || []).map((e) => ({ sequence: e.sequence, kind: (e.envelope || {}).kind, id: (e.envelope || {}).id, version: (e.envelope || {}).version, issuer: (e.envelope || {}).issuer, created_at: (e.envelope || {}).created_at })), next_cursor: r.next_cursor || null, source: "runtime" }; }
    return { events: [], source: "snapshot", note: "A snapshot has no event stream." };
  }

  /* Pending interfaces: exact names are not final. Root connects them. */
  const pending = (name) => async () => { throw new Unavailable(name, "The interface name and schema are pending; nothing was submitted and no result is shown."); };
  /* POST /api/engineering/solve with a session CSRF token from /api/session. Numbers go as decimal strings;
   * rho and cl_max are null (unknown) unless the user typed them; the assumption flags default to false. */
  async function solve(c) {
    if (!isLive()) throw new Unavailable("constraint solver", "No runtime is connected, so no solver ran and no result is shown.");
    const MAX = { rho: 10, cl_max: 3, mass: 50, area: 10, span: 10, speed: 100, mass_min: 50, wing_loading_min: 1000, speed_max: 100 };
    const dec = (x, key) => {
      if (x === null || x === undefined || !isFinite(x)) return null;
      const s = Number(x).toFixed(12).replace(/0+$/, "").replace(/\.$/, "");
      if (!/^(?:0|[1-9][0-9]{0,5})(?:\.[0-9]{1,12})?$/.test(s) || !(Number(s) > 0) || Number(s) > MAX[key]) throw new Error(`${key} = ${x} cannot be sent: the solver takes a positive decimal no greater than ${MAX[key]} with at most 12 decimals`);
      return s;
    };
    const area = c.span_m && c.aspect_ratio ? (c.span_m * c.span_m) / c.aspect_ratio : null;
    const body = { rho: dec(c.rho, "rho"), cl_max: dec(c.cl_max, "cl_max"), mass: dec(c.mass_kg, "mass"), area: dec(area, "area"), span: dec(c.span_m, "span"), speed: dec(c.launch_speed, "speed"),
      mass_min: dec(c.mass_min, "mass_min"), wing_loading_min: dec(c.wing_loading_min, "wing_loading_min"), speed_max: dec(c.speed_max, "speed_max"), relax_envelopes: false,
      assume_pectoral_ar_applies_to_wing: c.assume_pect_ar_wing === true, assume_taxi_speed_applies_to_flight: c.assume_taxi_flight === true };
    const sess = await getJSON("api/session", 5000); const csrf = sess.csrf || sess.csrf_token || sess.token;
    if (!csrf) throw new Error("the session did not provide a CSRF token");
    const r = await fetch("api/engineering/solve", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(body), cache: "no-store" });
    if (!r.ok) {
      let e = null; try { e = await r.json(); } catch (x) { /* not JSON */ }
      throw new Error(`the solver refused the request (HTTP ${r.status}${e && e.error ? ", " + e.error : ""})${e && e.message ? ": " + e.message : ""}. Submitted: ${JSON.stringify(body)}`);
    }
    const out = await r.json(); out._submitted = body; return out;
  }
  /* POST /api/beliefs/solve with the scenario JSON; the envelope (including error bodies) comes back as the adapter built it. */
  async function belief(scenario) {
    if (!isLive()) throw new Unavailable("belief solver", "No runtime is connected, so nothing was solved and no result is shown.");
    const sess = await getJSON("api/session", 5000); const csrf = sess.csrf;
    if (!csrf) throw new Error("the session did not provide a CSRF token");
    const r = await fetch("api/beliefs/solve", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(scenario), cache: "no-store" });
    let body = null; try { body = await r.json(); } catch (e) { /* not JSON */ }
    if (!r.ok) { const e = new Error(`the belief solver refused the request (HTTP ${r.status}${body && body.error && body.error.code ? ", " + body.error.code : body && body.error ? ", " + body.error : ""})${body && body.error && body.error.message ? ": " + body.error.message : body && body.message ? ": " + body.message : ""}`); e.envelope = body; throw e; }
    return body;
  }
  async function attention() {
    if (!isLive()) return { unavailable: true, reason: "no live runtime" };
    try { return { report: await getJSON("api/attention", 8000) }; } catch (e) { return { unavailable: true, reason: e.message }; }
  }
  /* POST /api/simulations/run {model, parameters} -> frontier.simulation.preview/1 (completed | unknown with reason). 400 invalid, 429 busy, 503 unavailable carry fixed safe messages. */
  async function simulate(body) {
    if (!isLive()) throw new Unavailable("simulation", "No runtime is connected, so nothing ran and no result is shown.");
    if (JSON.stringify(body).length > 8192) throw new Error("the request is larger than the 8192-byte limit");
    const sess = await getJSON("api/session", 5000); if (!sess.csrf) throw new Error("the session did not provide a CSRF token");
    const r = await fetch("api/simulations/run", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": sess.csrf }, body: JSON.stringify(body), cache: "no-store" });
    let j = null; try { j = await r.json(); } catch (e) { /* not JSON */ }
    if (!r.ok) throw new Error(`${{ 400: "The request was refused as invalid", 404: "This node does not serve simulation previews", 429: "The preview slots are busy; try again shortly", 503: "The simulation runtime is unavailable on this node" }[r.status] || "The request failed"} (HTTP ${r.status}${j && j.error ? ", " + j.error : ""})${j && j.message ? ": " + j.message : ""}.`);
    return j;
  }
  const propose = pending("proposal submission");

  /* GET /api/discovery?q&kind&limit&mode=hybrid -> {items[{type,ref,artifact_sha256?,title,snippet,kind,local_status,score,score_kind,why_matched}], mode, index metadata, unavailable_reason?}.
   * Until the runtime serves it, an honest lexical fallback over the catalog and artifact index; the result always says which one ran. */
  async function discovery(q, { kind = "", limit = 12, signal = null, cacheOnly = false } = {}) {
    if (isLive() && state.discoveryAbsent !== true) {
      try {
        const p = new URLSearchParams({ q, limit: String(limit), mode: "hybrid" }); if (kind) p.set("kind", kind);
        let r;
        if (cacheOnly && state.cacheOnlyRejected !== true) {            // typed suggestions may use cached embeddings only; a node that rejects the parameter gets the plain request
          try { r = await getJSON("api/discovery?" + p.toString() + "&cache_only=1", 6000, signal); } catch (e) { if (e.name === "AbortError") throw e; if (/HTTP 400/.test(e.message)) state.cacheOnlyRejected = true; else throw e; }
        }
        if (!r) r = await getJSON("api/discovery?" + p.toString(), 8000, signal);
        return { source: "discovery", mode: r.mode || "unknown", items: Array.isArray(r.items) ? r.items : [], unavailable_reason: r.unavailable_reason || null, index: r.index || null };
      } catch (e) { if (e.name === "AbortError") throw e; if (/HTTP 404/.test(e.message)) state.discoveryAbsent = true; }
    }
    const needle = q.trim().toLowerCase(); const items = [];
    const cat = await catalog({ query: q, kind, limit: Math.min(50, limit * 2) });
    cat.records.forEach((rec) => items.push({ type: rec.ref.kind === "Problem" ? "question" : rec.ref.kind === "Action" ? "action" : "record", ref: rec.ref, title: rec.title, snippet: String((rec.payload && (rec.payload.statement || rec.payload.question || rec.payload.method || rec.payload.known_state)) || "").slice(0, 140), kind: rec.ref.kind, local_status: rec.local_status, score: null, score_kind: "none", why_matched: rec.why_matched || ["text match"] }));
    if (isLive() && !kind) {
      try { const ar = await getJSON("api/artifacts?" + new URLSearchParams({ q, limit: "5" }).toString(), 6000, signal);
        (ar.items || []).forEach((it) => { const a = it.artifact || {}; items.push({ type: "artifact", ref: it.evidence, artifact_sha256: a.sha256, title: a.title, snippet: `${a.role || ""} · ${a.media_type || ""}`, kind: "Artifact", local_status: it.local_status, score: null, score_kind: "none", why_matched: ["text match"] }); }); } catch (e) { if (e.name === "AbortError") throw e; }
    }
    return { source: "lexical-fallback", mode: "lexical", items: items.slice(0, limit), unavailable_reason: state.discoveryAbsent ? "the semantic index is not connected on this node" : null, total_matching: cat.total_matching };
  }

  /* GET /api/graph?namespace&kind&id&version&depth=1&limit=120 -> {nodes, edges, truncated, scope, counts}; null when the runtime does not serve it. */
  async function graph(ref, { depth = 1, limit = 120, signal = null } = {}) {
    if (!isLive() || state.graphAbsent === true) return null;
    try {
      const p = new URLSearchParams({ namespace: ref.namespace, kind: ref.kind, id: ref.id, depth: String(depth), limit: String(limit) }); if (ref.version) p.set("version", ref.version);
      return await getJSON("api/graph?" + p.toString(), 8000, signal);
    } catch (e) { if (e.name === "AbortError") throw e; if (/HTTP 404/.test(e.message)) { state.graphAbsent = true; return null; } throw e; }
  }

  DF.api = { state, isLive, load, discovery, graph, catalog, record, artifacts, media, system, attention, events, solve, belief, simulate, propose, Unavailable, getJSON };
})();
