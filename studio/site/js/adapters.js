/* Data adapters. One surface for the runtime (live) and the committed snapshot.
 * Nothing here fabricates a result: when an interface is not connected the adapter throws Unavailable. */
(function () {
  const DF = window.DF;
  class Unavailable extends Error {
    constructor(name, detail) { super(`${name} is not connected`); this.name = "Unavailable"; this.adapter = name; this.detail = detail; }
  }
  const state = { mode: "snapshot", health: null, reason: "not probed", snapshot: null, catalog: null };

  const isLive = () => state.mode === "live" && state.authenticated === true;

  async function getJSON(url, ms = 3000) {
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
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
        try { const s = await getJSON("api/session", 3000); state.authenticated = !!s.authenticated; } catch (e) { state.authenticated = false; }
      }
      else { state.reason = "/api/health answered but did not report ok"; }
    } catch (e) { state.reason = "runtime unavailable (" + (e.name === "AbortError" ? "timeout" : e.message) + ")"; }
    return state;
  }

  /* Catalog: GET /api/catalog?query&kind&status&limit<=50&after -> {records, next_cursor, namespace, mode}. */
  async function catalog({ query = "", kind = "", status = "", limit = 20, after = "" } = {}) {
    limit = Math.max(1, Math.min(50, limit | 0 || 20));
    if (isLive()) {
      const q = new URLSearchParams(); if (query) q.set("query", query); if (kind) q.set("kind", kind); if (status) q.set("status", status); q.set("limit", String(limit)); if (after) q.set("after", after);
      const r = await getJSON("api/catalog?" + q.toString());
      return { records: r.records || r.items || [], next_cursor: r.next_cursor || null, namespace: r.namespace || null, mode: r.mode || "live", source: "runtime" };
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
      return getJSON("api/record?" + q.toString());
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

  async function events() {
    if (isLive()) return { events: (await getJSON("api/events")).events || [], source: "runtime" };
    return { events: [], source: "snapshot", note: "A snapshot has no event stream." };
  }

  /* Pending interfaces: exact names are not final. Root connects them. */
  const pending = (name) => async () => { throw new Unavailable(name, "The interface name and schema are pending; nothing was submitted and no result is shown."); };
  /* POST /api/engineering/solve with a session CSRF token from /api/session. Numbers go as decimal strings;
   * rho and cl_max are null (unknown) unless the user typed them; the assumption flags default to false. */
  async function solve(c) {
    if (!isLive()) throw new Unavailable("constraint solver", "No runtime is connected, so no solver ran and no result is shown.");
    const dec = (x) => (x === null || x === undefined || !isFinite(x) ? null : String(x));
    const area = c.span_m && c.aspect_ratio ? (c.span_m * c.span_m) / c.aspect_ratio : null;
    const body = { rho: dec(c.rho), cl_max: dec(c.cl_max), mass: dec(c.mass_kg), area: dec(area), span: dec(c.span_m), speed: dec(c.launch_speed),
      mass_min: dec(c.mass_min), wing_loading_min: dec(c.wing_loading_min), speed_max: dec(c.speed_max), relax_envelopes: false, assume_pectoral_ar_applies_to_wing: c.assume_pect_ar_wing === true, assume_taxi_speed_applies_to_flight: c.assume_taxi_flight === true };
    Object.keys(body).forEach((k) => { if (body[k] === null && !["rho", "cl_max"].includes(k)) delete body[k]; });
    const sess = await getJSON("api/session", 5000); const csrf = sess.csrf || sess.csrf_token || sess.token;
    if (!csrf) throw new Error("the session did not provide a CSRF token");
    const r = await fetch("api/engineering/solve", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRF-Token": csrf }, body: JSON.stringify(body), cache: "no-store" });
    if (!r.ok) throw new Error("solver answered HTTP " + r.status);
    return r.json();
  }
  const belief = pending("belief / forecast");
  const simulate = pending("simulation");
  const propose = pending("proposal submission");

  DF.api = { state, load, catalog, record, artifacts, events, solve, belief, simulate, propose, Unavailable, getJSON };
})();
