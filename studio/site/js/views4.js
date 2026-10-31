/* System view (route /work and /system): one place, tabs. Two levels are kept apart on every tab:
 * author_report (what documents and people say) and measured (what a receipt in the tree records). */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;
  const TABS = [["overview", "Overview"], ["specs", "Specs and goals"], ["work", "Work and bottlenecks"], ["resources", "Resources"], ["receipts", "Receipts"], ["runtime", "Runtime and tools"]];
  const AUTHOR = html`<span class="pill lvl-a" title="Written by the authors of the work">author report</span>`;
  const MEAS = html`<span class="pill lvl-m" title="A receipt in the tree records this">measured</span>`;
  const BLOCK = /blocked|failed|authentication|repair|requested|pending|recovery|not yet|unknown/i;

  DF.views.work = DF.views.system = function (snap, route) {
    const tab = route.params.tab || "overview"; const S = snap.system; const live = DF.api.state.mode === "live" && DF.api.state.authenticated;
    const nav = html`<nav class="subnav" aria-label="System sections">${TABS.map(([k, t]) => html`<a href="${DF.href("/work", { tab: k })}" aria-current="${tab === k ? "page" : "false"}">${t}</a>`)}</nav>`;
    const head = html`<section class="pagehead"><h1>System</h1><p class="lede">What is being built, by whom, against which spec, and what has actually been measured. Two levels stay apart: ${AUTHOR} (documents and status text) and ${MEAS} (a run with a receipt). Nothing here is live activity, and no step is claimed to have built itself.</p>${nav}</section>`;
    const body = { overview, specs, work, resources, receipts, runtime }[tab] || overview;
    const out = body(snap, S, live, route);
    return { html: html`${head}${out.html}`, after: out.after };
  };

  function overview(snap, S, live) {
    const open = S.goal_checklist.filter((g) => !g.done).length;
    return { html: html`<section class="panel"><h2>Where this stands</h2>
      <dl class="kv"><div><dt>Snapshot</dt><dd>${snap.label}</dd></div><div><dt>Runtime</dt><dd>${live ? "live, signed in" : DF.api.state.mode === "live" ? "reachable, not signed in" : "none (snapshot only)"}</dd></div>
        <div><dt>Deployed commit</dt><dd id="depsha">${live ? "asking the runtime…" : "not reported: a snapshot cannot know it"}</dd></div></dl>
      <p class="note small">The deployed commit is shown only if the runtime's own system report states it. This page never infers it from the snapshot.</p></section>
      <section class="panel"><h2>Goal checklist ${AUTHOR}</h2><p class="small faint">From <code>GOAL.md</code>. A ticked box is the authors' report; ${open} of ${S.goal_checklist.length} are unticked. What a receipt backs is under <a href="${DF.href("/work", { tab: "receipts" })}">Receipts</a>.</p>
        <div class="tablewrap"><table><thead><tr><th>Author's box</th><th>Item</th></tr></thead><tbody>${S.goal_checklist.map((g) => html`<tr><td>${g.done ? U.pill("ticked", "ok") : U.pill("open", "open")}</td><td>${g.text}</td></tr>`)}</tbody></table></div></section>
      <section class="panel"><h2>The two levels</h2><div class="two"><article><h3>${AUTHOR}</h3><p>${S.levels.author_report}</p></article><article><h3>${MEAS}</h3><p>${S.levels.measured}</p></article></div></section>`,
      async after(root) { if (!live) return; const r = await DF.api.system(); const el = root.querySelector("#depsha"); const rep = r.report || {}; const k = ["deployed_sha", "git_sha", "commit", "sha", "release"].find((x) => typeof rep[x] === "string");
        el.textContent = k ? `${rep[k]} (reported by the runtime as “${k}”)` : r.unavailable ? `not reported (system report unavailable: ${r.reason})` : "not reported in the system report"; } };
  }

  function specs(snap, S) {
    return { html: html`<section class="panel"><h2>Specs</h2><p class="small faint">Each opens in the source drawer with its sha256. Specs are proposals until a receipt establishes the behaviour they describe.</p>
      <div class="tablewrap"><table><thead><tr><th>Spec</th><th>Path</th><th>sha256</th></tr></thead><tbody>${S.specs.map((x) => html`<tr><td>${U.src("doc:" + x.id, x.title)}</td><td><code>${x.path}</code></td><td>${U.sha(x.sha256)}</td></tr>`)}</tbody></table></div></section>
      <section class="panel"><h2>SPEC-005 acceptance rows ${AUTHOR}</h2><p class="small faint">Unticked means the authors have not recorded an execution receipt for it. The spec itself says counts of test definitions or generated records are not successful executions.</p>
        <div class="tablewrap"><table><tbody>${S.spec005_acceptance.map((g) => html`<tr><td>${g.done ? U.pill("ticked", "ok") : U.pill("open", "open")}</td><td>${g.text}</td></tr>`)}</tbody></table></div></section>` };
  }

  function work(snap, S) {
    const rows = S.board;
    return { html: html`<section class="panel"><h2>Work in progress ${AUTHOR}</h2><p class="note small">From <code>tasks/BUILD.md</code> at ${snap.label}: owners, deliverables and status text as the coordinator wrote them. It is a plan with notes, not live status. “Possible bottleneck” only means the status text mentions a blocker word; it is a reading aid, not a measurement.</p>
      <div class="tablewrap"><table><thead><tr><th>Priority</th><th>Deliverable</th><th>Owner</th><th>Status text</th><th></th></tr></thead><tbody>${rows.map((r) => html`<tr><td>${r.priority}</td><td>${r.deliverable}</td><td>${r.owner}</td><td>${r.status_text}</td><td>${BLOCK.test(r.status_text) ? U.pill("possible bottleneck", "warn") : ""}</td></tr>`)}</tbody></table></div>
      <p class="small faint">Branch names, commit hashes and release path are not in this file, so none is shown. They appear here once the runtime's system report supplies them.</p></section><div id="attn"></div>`,
      async after(root) {
        if (!(DF.api.state.mode === "live" && DF.api.state.authenticated)) return;
        const r = await DF.api.attention();
        root.querySelector("#attn").innerHTML = (r.unavailable ? html`<section class="panel"><h2>Attention view</h2><p class="empty">Not available (${r.reason}). Nothing is shown in its place.</p></section>`
          : html`<section class="panel"><h2>Attention view, as received</h2><p class="note small">Built by the attention layer from public stored records and events. Its fields are shown unprocessed: priority here is not truth, and this page has not checked it.</p><pre class="json">${JSON.stringify(r.report, null, 2)}</pre></section>`).toString();
      } };
  }

  function resources(snap, S, live) {
    return { html: html`<section class="panel"><h2>Resources: actual versus unknown</h2><div class="tablewrap"><table><thead><tr><th>Quantity</th><th>Actual (receipt)</th><th>Status</th></tr></thead><tbody>
      <tr><td>CPU jobs, utilisation</td><td>none in this tree</td><td>${U.pill("unknown", "st-unk")}</td></tr><tr><td>GPU jobs, utilisation</td><td>none in this tree</td><td>${U.pill("unknown", "st-unk")}</td></tr>
      <tr><td>Provider-billed cost</td><td>none; the board says it is not yet known</td><td>${U.pill("unknown", "st-unk")}</td></tr><tr><td>Resource bounds used for runs</td><td>stated in <code>tasks/BUILD.md</code> (author report)</td><td>${AUTHOR}</td></tr></tbody></table></div>
      <ul>${S.unknown.map((u) => html`<li>${u}</li>`)}</ul><p class="small faint">An estimate is not an actual. Figures appear here only when the runtime reports them.</p></section><div id="sysraw"></div>`,
      async after(root) { if (!live) return; const r = await DF.api.system(); root.querySelector("#sysraw").innerHTML = rawBlock(r).toString(); } };
  }

  function rawBlock(r) {
    return r.unavailable ? html`<section class="panel"><h2>Live system report</h2><p class="empty">Not available (${r.reason}). Nothing is shown in its place.</p></section>`
      : html`<section class="panel"><h2>Live system report, as received</h2><p class="note small">The report's fields are not yet specified, so it is shown unprocessed rather than interpreted. Nothing here has been checked by this page.</p><pre class="json">${JSON.stringify(r.report, null, 2)}</pre></section>`;
  }

  function receipts(snap, S) {
    return { html: html`<section class="panel"><h2>What has been measured ${MEAS}</h2><p class="note small">Each row is a receipt present in this tree, with its hash and what it covers. A receipt covers only what it says; none of these is a biological validation.</p>
      <div class="tablewrap"><table><thead><tr><th>What</th><th>Result</th><th>Receipt</th><th>Covers</th></tr></thead><tbody>${S.measured.map((m) => html`<tr><td>${m.what}</td><td>${m.result}</td><td><code>${m.receipt}</code><br>${U.sha(m.sha256)}</td><td>${m.covers}</td></tr>`)}</tbody></table></div>
      ${S.measured.length ? "" : U.empty("No receipt is present in this tree.")}<p class="small faint">Not here because no receipt exists in this tree: mesh or geometry validation, controlled reuse measurements, executed claim reuse, GPU runs.</p></section>` };
  }

  function runtime(snap, S, live) {
    return { html: html`<section class="panel"><h2>Runtime</h2><p>${U.pill(live ? "live runtime" : "snapshot only", live ? "ok" : "warn")} ${DF.api.state.reason}.</p>
        ${live ? html`<p>Namespace: <code>${DF.api.state.health.namespace || "not reported"}</code>.</p>` : html`<p class="note small">No runtime is connected, so there are no agents, leases, resources or contributions to show. Nothing below is simulated.</p>`}</section>
      <section class="panel"><h2>Events</h2><div id="events" role="status">Loading…</div></section>
      ${live ? html`<section class="panel"><h2>What the live store holds</h2><p class="note small">Counts of records by kind, read by paging the catalog (50 per page). These are records, not independent observations: imported claims repeat what their sources assert.</p><button class="btn small" type="button" id="countrecs">Count records by kind</button><div id="counts" role="status"></div></section>` : ""}
      <section class="panel"><h2>Declared capabilities (MCP tools)</h2><p class="note small">Parsed from the Tools row of <code>docs/mcp.md</code>. A declared tool is not demonstrated competence; no success receipts are attached.</p>
        <div class="tablewrap"><table><thead><tr><th>Tool</th><th>Mode</th></tr></thead><tbody>${snap.capabilities.map((t) => html`<tr><td><code>${t.name}</code></td><td>${t.mode}</td></tr>`)}</tbody></table></div>
        <p class="small">Writes need <code>--allow-write</code> and an operator credential kept outside prompts; contributions stay proposed. ${U.src("doc:mcp", "Read the MCP document")}</p></section>`,
      async after(root) {
        const cb = root.querySelector("#countrecs");
        if (cb) cb.addEventListener("click", async () => {
          const out = root.querySelector("#counts"); cb.disabled = true; const rows = []; let capped = false;
          try {
            for (const kind of ["Claim", "Problem", "Evidence", "Assessment", "Action", "Actor", "ResourceOffer", "Interest", "Event"]) {
              let n = 0, after = "", pages = 0;
              do { const r = await DF.api.catalog({ kind, limit: 50, after }); n += r.records.length; after = r.next_cursor || ""; pages++; out.textContent = `Counting ${kind}… ${n}`; } while (after && pages < 200);
              if (after) capped = true; rows.push([kind, n]);
            }
            out.innerHTML = html`<div class="tablewrap"><table><thead><tr><th>Kind</th><th>Records</th></tr></thead><tbody>${rows.map(([k, n]) => html`<tr><td>${k}</td><td>${n}</td></tr>`)}<tr><td><b>Total</b></td><td><b>${rows.reduce((a, r) => a + r[1], 0)}</b></td></tr></tbody></table></div>${capped ? html`<p class="small faint">Stopped at 200 pages for a kind; that count is a lower bound.</p>` : ""}<p class="small faint">Counts read from the live catalog just now; not independent observations and not a measure of progress.</p>`.toString();
          } catch (e) { out.textContent = "Counting failed: " + e.message; } finally { cb.disabled = false; }
        });
        const host = root.querySelector("#events");
        try { const r = await DF.api.events(); host.innerHTML = r.events.length ? html`<p class="small faint">Events are records emitted by the store, in sequence order; they say what was recorded, not that it is correct.</p><div class="tablewrap"><table><thead><tr><th>#</th><th>Kind</th><th>Id</th><th>Issuer</th><th>Created</th></tr></thead><tbody>${r.events.map((e) => html`<tr><td>${e.sequence}</td><td>${e.kind}</td><td><code>${e.id}</code></td><td>${e.issuer || ""}</td><td>${e.created_at || ""}</td></tr>`)}</tbody></table></div>${r.next_cursor ? html`<p class="small faint">More events exist than shown.</p>` : ""}`.toString() : `<p class="empty">${esc(r.note || "The runtime reports no events.")} No agents, leases or contributions are displayed.</p>`; }
        catch (e) { host.innerHTML = `<p class="empty">Could not read events: ${esc(e.message)}. Nothing is displayed in their place.</p>`; }
      } };
  }
})();
