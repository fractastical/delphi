/* System view (route /work and /system): one place, tabs. Two levels are kept apart on every tab:
 * author_report (what documents and people say) and measured (what a receipt in the tree records). */
(function () {
  const DF = window.DF; const { html, raw, esc } = DF; const U = DF.ui;
  const TABS = [["overview", "Overview"], ["built", "How it was built"], ["specs", "Specs and goals"], ["work", "Work and bottlenecks"], ["resources", "Resources"], ["receipts", "Receipts"], ["runtime", "Runtime and tools"], ["connect", "Connect and share"]];
  const AUTHOR = html`<span class="pill lvl-a" title="Written by the authors of the work">author report</span>`;
  const MEAS = html`<span class="pill lvl-m" title="A receipt in the tree records this">measured</span>`;
  const BLOCK = /blocked|failed|authentication|repair|requested|pending|recovery|not yet|unknown/i;

  DF.views.work = DF.views.system = function (snap, route) {
    RAW.clear();                                   // raw-JSON closures belong to the page being drawn; none survive a route change
    const tab = route.params.tab || "overview"; const S = snap.system; const live = DF.api.isLive();
    const nav = html`<nav class="subnav" aria-label="System sections">${TABS.map(([k, t]) => html`<a href="${DF.href("/work", { tab: k })}" aria-current="${tab === k ? "page" : "false"}">${t}</a>`)}</nav>`;
    const head = html`<section class="pagehead"><h1>System</h1><p class="lede">What is being built, by whom, against which spec, and what has actually been measured. Two levels stay apart: ${AUTHOR} (documents and status text) and ${MEAS} (a run with a receipt). Nothing here is live activity, and no step is claimed to have built itself.</p>${nav}</section>`;
    const body = { overview, built, specs, work, resources, receipts, runtime, connect }[tab] || overview;
    const out = body(snap, S, live, route);
    return { html: html`${head}${out.html}`, after: out.after };
  };

  const repository = (path, rev = "main") => `https://github.com/kganjam/delphi-frontier/blob/${encodeURIComponent(rev)}/${String(path).split("/").map(encodeURIComponent).join("/")}`;
  function counterTable(counters) {
    return html`<div class="tablewrap"><table class="build-table build-counters"><caption class="sr">Counters recorded in receipts; unknown where no counter exists</caption><thead><tr><th scope="col">Quantity</th><th scope="col">Recorded</th><th scope="col">Status</th><th scope="col">Limit and source</th></tr></thead><tbody>${counters.map((c) => html`<tr><th scope="row" data-label="Quantity">${c.quantity}</th><td data-label="Recorded">${c.value}</td><td data-label="Status">${U.pill(c.status, c.status === "actual" ? "ok" : c.status === "unknown" ? "no" : "warn")}</td><td class="small" data-label="Limit and source">${c.note}<span class="build-source"><code>${c.source}</code></span></td></tr>`)}</tbody></table></div>`;
  }
  function auditPanels(audits = {}) {
    const A = audits.contributors, M = audits.models, R = audits.repositories, a = A && A.data, m = M && M.data, r = R && R.data;
    const evidenceLink = (e, rev) => html`<li><a href="${repository(e.path, rev)}" target="_blank" rel="noopener noreferrer">${e.path}</a> ${e.sha256 ? U.sha(e.sha256) : ""}</li>`;
    return html`${a ? html`<details class="contributor-audit"><summary>Who contributed? Inspect the dated identity audit</summary>
      <p class="small">Observed ${new Date(a.window.observed_utc).toLocaleString("en-US", {timeZone: "America/Los_Angeles", timeZoneName: "short"})}. ${a.not_summed}. ${a.contribution_activity}.</p>
      <div class="two"><article><h3>Contributing harnesses · supported minimum</h3><ul>${Object.entries(a.supported_harnesses).map(([id, v]) => html`<li><code>${id}</code> — ${v.mapping ? v.mapping.role : v.basis}</li>`)}</ul></article>
      <article><h3>Native collaborators · separate identities</h3><ul>${a.native_contributors.entries.map((v) => html`<li><code>${v.identity}</code> — ${v.role}</li>`)}</ul></article></div>
      ${a.participation ? html`<p class="note small"><b>${a.participation.recorded_participant_floor} recorded participants</b>: ${a.participation.supported_harnesses} harnesses, ${a.participation.recorded_native_children} native children and ${a.participation.recorded_nested_claude_children} nested Claude children. The child groups total <b>${a.participation.recorded_native_children + a.participation.recorded_nested_claude_children} recorded subagents</b>. These are historical identities, not concurrent workers. The artifact-backed native list above is a subset. <a href="${repository(a.participation.source)}">Read the transcript-scoped count and exclusions</a>.</p>` : ""}
      <p class="small">Identity links include coordinator attestations. Artifact checks establish that the work exists, not independent proof of authorship. Historical contribution does not mean a worker is currently active.</p>
      <p class="small"><a href="${repository(A.path)}" target="_blank" rel="noopener noreferrer">Full audit, mappings and deduplication rules</a> ${U.sha(A.sha256)}</p></details>` : ""}
      ${r ? html`<details class="repository-activity-audit"><summary>Repository activity · inspect four pinned histories</summary>
      <p class="small">${r.scope} Window: ${new Date(r.since_utc).toLocaleString("en-US", {timeZone: "America/Los_Angeles", timeZoneName: "short"})} through ${new Date(r.until_utc).toLocaleString("en-US", {timeZone: "America/Los_Angeles", timeZoneName: "short"})}.</p>
      <div class="tablewrap"><table class="build-table"><caption class="sr">Commit objects by repository at pinned default-branch revisions</caption><thead><tr><th scope="col">Repository</th><th scope="col">Commits</th><th scope="col">Non-merge / merge</th><th scope="col">Pinned revision</th></tr></thead><tbody>${r.repositories.map((x) => html`<tr><th scope="row" data-label="Repository"><a href="${x.url}" target="_blank" rel="noopener noreferrer">${x.repository}</a></th><td data-label="Commits">${x.counts.commit_objects.toLocaleString("en-US")}</td><td data-label="Non-merge / merge">${x.counts.non_merge_commits} / ${x.counts.merge_commits}</td><td data-label="Pinned revision"><a href="${x.url}/commit/${x.head_sha}" target="_blank" rel="noopener noreferrer">${x.head_sha.slice(0, 10)}</a></td></tr>`)}</tbody></table></div>
      <p class="small">Commits are not participants or validated findings. Shared commit objects are counted once in the total. Unmerged task branches are outside this audit. <a href="${repository(R.path)}" target="_blank" rel="noopener noreferrer">Full IDs and reproducible counting scope</a> ${U.sha(R.sha256)}</p></details>` : ""}
      ${m ? html`<details class="model-usage-audit"><summary>Models and simulators actually exercised · ${m.entries.length} scoped records</summary>
      <p class="small">${m.scope}</p><p class="note small">${m.bionemo_nim.statement} NVIDIA Brev use is not established by this ledger. Total billing and provider-wide LLM usage remain unknown.</p>
      <div class="tablewrap"><table class="build-table"><caption class="sr">Scoped model executions, outcomes and evidence</caption><thead><tr><th scope="col">Model or simulator</th><th scope="col">Provider</th><th scope="col">Recorded outcome</th><th scope="col">Usage and evidence</th></tr></thead><tbody>
      ${m.entries.map((r) => html`<tr><th scope="row" data-label="Model or simulator">${r.model || r.model_or_tool || (r.models || []).map((x) => x.model).join(", ")}<br><code class="small">${r.id}</code></th><td class="small" data-label="Provider">${r.provider}</td><td class="small" data-label="Recorded outcome">${r.status.replace(/_/g, " ")}<p>${r.scope_note || ""}</p></td><td class="small" data-label="Usage and evidence"><details><summary>Inspect receipt and scope</summary>${tree(r.usage || r.calls || {usage: "See the named receipt; no aggregate is inferred."}, 0)}<ul>${(r.evidence || []).map((e) => evidenceLink(e, m.source_tree_commit))}</ul></details></td></tr>`)}</tbody></table></div>
      <p class="small">${m.source_tree_note} <a href="${repository(M.path)}" target="_blank" rel="noopener noreferrer">Full ledger and result artifacts</a> ${U.sha(M.sha256)}</p></details>` : ""}`;
  }

  /* How it was built: dated receipts, usage windows, provider outcomes and preregistered verdicts, each with its file and sha256. Spend and total usage stay unknown. */
  function built(snap) {
    const T = snap.timeline;
    if (!T) return { html: html`<section class="panel"><h2>How it was built</h2><p class="empty">No resource inventory or receipts are present in this snapshot.</p></section>` };
    const tone = (ok) => (ok === true ? U.pill("passed", "ok") : ok === false ? U.pill("failed", "no") : U.pill("recorded", "st-unk"));
    const ev = (r) => html`<span class="build-source"><code>${r.path}</code>${r.sha256 ? U.sha(r.sha256) : html`<span class="faint small">no digest recorded</span>`}</span>`;
    const N = T.nebius; const kinds = [...new Set(T.rows.map((r) => r.kind))];
    return { html: html`<section class="panel build-report" aria-labelledby="bt-h"><h2 id="bt-h">How it was built ${AUTHOR}</h2>
      <p class="note small"><b>Source repository:</b> <a href="https://github.com/kganjam/delphi-frontier" rel="noopener">github.com/kganjam/delphi-frontier</a> ${U.pill("public source", "ok")}. Browse the code, model inputs and recorded checks without signing in.</p>
      <p class="small">Every row is a file in the tree with its sha256. Times are UTC as recorded; Seattle local time is UTC−7 (PDT) on 2026-10-31. A row shows what that file records, not that the work was correct, independent or complete. Inventory observed ${T.observed_at.seattle}.</p>
      <h3>Recorded counters (event window from ${T.event_window_start_utc.slice(0, 10)})</h3>
      ${counterTable(T.counters)}
      ${auditPanels(T.audits)}
      ${snap.system.review_corrections ? html`<h3 id="review-corrections">Where review changed a decision</h3>
        <p class="small">A retrospective trace of corrections across this team's agents: typed-input failures, stale evidence and overstated results. These examples show what review changed; they do not establish an advantage over a single agent.</p>
        <ul class="small">${snap.system.review_corrections.entries.filter((e) => e.id !== "contributor-count-labels").map((e) => html`<li><b>${e.title}.</b> ${e.decision_changed}</li>`)}</ul>
        <p class="small"><a href="${snap.system.review_corrections.href}">Exact submissions, reviews and corrected revisions</a> · <a href="artifacts/coordination/collective-review-evidence.md">Read the scope and provenance gaps</a> · ${U.sha(snap.system.review_corrections.sha256)}</p>` : ""}
      <p class="small">Counts cover use recorded inside the event window only. Earlier work is not narrated here; where a result rests on published sources or earlier data, its card cites them with their hashes and licences.</p>
      <h3>Reuse</h3>
      <p class="small">What others can take and check: the claims and evidence through the <a href="${DF.href("/work", { tab: "connect" })}">public read interface and MCP tools</a>, every simulation with its manifest and limits on the <a href="${DF.href("/simulations")}">simulations page</a>, printable models and the 3D mesh on <a href="${DF.href("/home")}">Home</a>, and exact record pins on each entity page. Reuse by anyone outside this team is not recorded. The one recorded example of versioned reuse is a <a href="${DF.href("/reuse")}">worked case</a>: two computations read one exact Claim, and an independent reviewer disputed both results; it is a count of uses, not a measured benefit.</p>
      ${T.usage ? html`<h3>Role assignments in the earlier usage slice</h3><p class="small faint">One session can fill several roles. This table is not added to the contributor counts above.</p>
      <div class="tablewrap"><table class="build-table build-roles"><caption class="sr">Identified roles and their recorded status</caption><thead><tr><th scope="col">Contributor</th><th scope="col">Kind</th><th scope="col">Role</th><th scope="col">Status as recorded</th></tr></thead><tbody>${T.usage.roles.map((r) => html`<tr><td data-label="Contributor"><code>${r.id}</code></td><td data-label="Kind">${r.kind}</td><td class="small" data-label="Role">${r.role}</td><td class="small" data-label="Status as recorded">${r.status}</td></tr>`)}</tbody></table></div>
      <h3>Own provider jobs (${T.usage.jobs.length}, ${T.usage.observed_at_seattle})</h3>
      <details><summary class="small">Show every job record</summary><div class="tablewrap"><table class="build-table build-jobs"><caption class="sr">Own GPU and CPU job records</caption><thead><tr><th scope="col">Created</th><th scope="col">Kind</th><th scope="col">Job</th><th scope="col">Provider state</th></tr></thead><tbody>${T.usage.jobs.map((j) => html`<tr><td class="small" data-label="Created">${j.created}</td><td data-label="Kind">${j.kind}</td><td data-label="Job"><code class="small">${j.name}</code></td><td data-label="Provider state">${U.pill(j.state.toLowerCase(), j.state === "FAILED" ? "no" : j.state === "COMPLETED" ? "st-unk" : "warn")}</td></tr>`)}</tbody></table></div></details>
      <p class="small faint">Provider COMPLETED means the container ended, not that a scientific check passed. Failed jobs stay failed.</p>
      <h3>Controller outcomes for recent GPU tasks</h3>
      <ul class="small">${T.usage.controller.map((e) => html`<li>${U.pill(e.status, e.status === "failed" ? "no" : "st-unk")} <b>${e.task}</b>: container wall ${e.wall_s === null ? "not recorded" : e.wall_s + " s"}, return code ${e.rc === null ? "not recorded" : e.rc}. <code>${e.path}</code> ${U.sha(e.sha256)}</li>`)}</ul>
      ${snap.recovery_inputs ? html`<h3>Failed primary diffusion-model training run, retained</h3><p class="small">${U.pill("primary run: " + snap.recovery_inputs.primary_full_run_status.toLowerCase(), "no")} The run hit its time limit. A checkpoint after ${snap.recovery_inputs.training_steps.toLocaleString("en")} training steps was returned and is hash-checked; ${snap.diffusion_pilot ? html`a separate evaluation reused that checkpoint and returned generated examples, while the <a href="${DF.href("/generative")}">strict secondary audit failed</a>. The primary timeout remains a failure` : html`<b>no evaluation or generated examples are present in this snapshot</b>`}. ${snap.recovery_inputs.status}.</p>
        <p class="small">${snap.recovery_inputs.published ? html`Recovery inputs (the checkpoint and its control files, ${(snap.recovery_inputs.bytes / 1e6).toFixed(1)} MB): <a href="${snap.recovery_inputs.href}" download>primary-runtime-inputs.tar.xz</a> · sha256 ${U.sha(snap.recovery_inputs.sha256)}` : html`The recovery archive did not match its declared digest, so it is not published.`} ${snap.diffusion_pilot ? html`The original next-step note is superseded by the separate recovery and audit receipts linked above.` : html`Next step, as recorded: ${snap.recovery_inputs.next_admission}.`}</p>` : ""}
      ${snap.openresearch ? html`<h3>Recorded OpenResearch runs (local exemplars)</h3><p class="note small">${snap.openresearch.scope}</p>
        <div class="tablewrap"><table class="build-table build-research"><caption class="sr">Two recorded local OpenResearch runs</caption><thead><tr><th scope="col">Run</th><th scope="col">Backend and tool</th><th scope="col">Started (UTC), duration</th><th scope="col">Exit</th><th scope="col">Outputs</th></tr></thead><tbody>${snap.openresearch.exemplars.map((e) => html`<tr><td data-label="Run"><b>${e.title}</b><br><code class="small">${e.command}</code><br><span class="faint small">commit ${e.commit.slice(0, 10)}…, source ${e.source_tar_sha256.slice(0, 10)}…</span></td><td class="small" data-label="Backend and tool">${e.backend} (not a remote backend)<br>${e.orx_version}</td><td class="small" data-label="Started (UTC), duration">${e.started_utc}<br>${e.duration_s} s</td><td class="small" data-label="Exit">status ${e.status}; exit code file ${e.exit_code_file}${e.db_exit_code === null ? html`; database exit code <mark class="unk">null</mark>` : ""}</td><td class="small" data-label="Outputs">${e.outputs.map((o) => html`<code>${o.path}</code> ${o.sha256 ? U.sha(o.sha256) : "no digest"}<br>`)}${e.replay_checks ? html`<span class="faint">replay checks: ${Object.entries(e.replay_checks).map(([k, x]) => k.replace(/_/g, " ") + " " + (x ? "yes" : "NO")).join(", ")}</span>` : ""}<br><span class="faint">${e.note}</span></td></tr>`)}</tbody></table></div>
        <p class="small faint">Records: ${snap.openresearch.exemplars.map((e) => e.record).join(" · ")}. ${snap.openresearch.report}.</p>` : ""}
      <p class="small"><b>External tools credited:</b> ${T.usage.credit.join(", ")}. These are not authored in the event window.</p>
      <ul class="small">${T.usage.limitations.map((x) => html`<li>${x}</li>`)}</ul>` : ""}
      <h3>Providers and jobs</h3>
      <ul class="small"><li><b>Nebius (GPU jobs):</b> ${N.own_job_count} jobs by this project: ${Object.entries(N.job_states).filter(([, n]) => n).map(([k, n]) => n + " " + k.toLowerCase().replace(/_/g, " ")).join(", ")} (observed ${N.observed_at_utc}). Allocation is requested capacity, not utilisation.</li>
        <li><b>Google Generative Language:</b> ${T.rows.filter((r) => r.kind === "model usage").map((r) => r.title + ": " + r.outcome.split(";")[0]).join("; ")}.</li>
        <li><b>Live checks of the public node:</b> ${T.rows.filter((r) => r.kind === "live check").length} recorded, ${T.rows.filter((r) => r.kind === "live check" && r.ok).length} with every check passed.</li></ul>
      <p class="note warn small"><b>Unknown:</b> ${T.unknown.join(" ")}</p>
      <h3>Dated record (${T.rows.length} rows; ${kinds.join(", ")})</h3>
      <div class="tablewrap"><table class="build-table build-timeline"><caption class="sr">Dated build and run records</caption><thead><tr><th scope="col">Time (UTC)</th><th scope="col">Kind</th><th scope="col">What</th><th scope="col">Outcome</th><th scope="col">Evidence</th></tr></thead><tbody>${T.rows.map((r) => html`<tr><td class="small" data-label="Time (UTC)">${r.time.replace("T", " ").replace(/\.\d+Z?$/, "").replace("+00:00", "")}</td><td data-label="Kind">${U.pill(r.kind, "grp")}</td><td data-label="What">${r.title}</td><td class="small" data-label="Outcome">${tone(r.ok)} ${r.outcome}${r.scope ? html`<br><span class="faint">${r.scope}</span>` : ""}</td><td data-label="Evidence">${ev(r)}</td></tr>`)}</tbody></table></div>
      <h3>Results, stops and failures, with what checked them</h3>
      <ul>${T.undated.map((r) => html`<li>${tone(r.ok)} <b>${r.title}</b>${r.date ? " (" + r.date + ", date only)" : ""}: ${r.outcome}<br>${ev(r)}</li>`)}</ul>
      <h3>Limits of this record</h3><ul class="small">${T.limitations.map((x) => html`<li>${x}</li>`)}</ul>
      <p class="small faint">Inventory ${T.inventory} ${U.sha(T.inventory_sha256)}. Agent activity beyond these files is not reconstructed here.</p></section>` };
  }

  function overview(snap, S, live) {
    const open = S.goal_checklist.filter((g) => !g.done).length;
    return { html: html`<section class="panel"><h2>Where this stands</h2>
      <dl class="kv"><div><dt>Snapshot</dt><dd>${snap.label}</dd></div><div><dt>Runtime</dt><dd>${DF.api.state.authenticated ? "live, signed in" : DF.api.state.mode === "live" && DF.api.state.publicAccess ? "live, public read-only (not signed in)" : DF.api.state.mode === "live" ? "reachable, not signed in" : "none (snapshot only)"}</dd></div>
        <div><dt>Deployed commit</dt><dd id="depsha">${live ? "asking the runtime…" : "not reported: a snapshot cannot know it"}</dd></div></dl>
      <p class="note small">The deployed commit is shown only if the runtime's own system report states it. This page never infers it from the snapshot.</p></section>
      <section class="panel"><h2>Goal checklist ${AUTHOR}</h2><p class="small faint">From <code>GOAL.md</code>. A ticked box is the authors' report; ${open} of ${S.goal_checklist.length} are unticked. What a receipt backs is under <a href="${DF.href("/work", { tab: "receipts" })}">Receipts</a>.</p>
        <div class="tablewrap"><table><thead><tr><th>Author's box</th><th>Item</th></tr></thead><tbody>${S.goal_checklist.map((g) => html`<tr><td>${g.done ? U.pill("ticked", "ok") : U.pill("open", "open")}</td><td>${g.text}</td></tr>`)}</tbody></table></div></section>
      <section class="panel"><h2>The two levels</h2><div class="two"><article><h3>${AUTHOR}</h3><p>${S.levels.author_report}</p></article><article><h3>${MEAS}</h3><p>${S.levels.measured}</p></article></div></section>`,
      async after(root) { if (!live) return; const r = await DF.api.system(); const el = root.querySelector("#depsha"); const rep = r.report || {}; const k = ["deployed_sha", "git_sha", "commit", "sha", "release"].find((x) => typeof rep[x] === "string");
        const sha = rep.deployed_sha || (rep.release && (rep.release.sha || rep.release.checkout_sha)); const bi = rep.build && rep.build.release_sha;
        const dcl = rep.release && rep.release.directory_claim; const cl = rep.claimed_sha || (dcl && dcl.sha); const cc = dcl && dcl.contents;
        if (!sha && cl) { el.textContent = `${cl} (claimed by the release directory name, not measured${cc && cc.checked ? `; files ${cc.matches_recorded_tree ? "match" : "DO NOT match"} the tree hash recorded at release` : ""}; no git checkout to measure)`; return; }
        el.textContent = sha ? `${sha} (running release, measured${rep.release && rep.release.sha_source ? ", from " + rep.release.sha_source : ""})${bi ? `; build-info reports ${bi}, matches: ${rep.build.matches_checkout}` : ""}` : k ? `${rep[k]} (reported by the runtime as “${k}”)` : r.unavailable ? `not reported (system report unavailable: ${r.reason})` : "not reported in the system report"; } };
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
        if (!(DF.api.isLive())) return;
        const r = await DF.api.attention();
        root.querySelector("#attn").innerHTML = (r.unavailable ? html`<section class="panel"><h2>Attention view</h2><p class="empty">Not available (${r.reason}). Nothing is shown in its place.</p></section>`
          : html`<section class="panel"><h2>Attention view, as received</h2><p class="note small">Built by the attention layer from public stored records and events. Its fields are shown unprocessed: priority here is not truth, and this page has not checked it.</p>${rawJson("the attention report", r.report)}</section>`).toString();
      } };
  }

  function inventoryPanel(R) {
    if (!R) return "";
    const L = R.compute || {}, N = L.nebius || {}, G = L.google_compute || {}, O = L.launch_outcomes || {};
    return html`<section class="panel" aria-labelledby="ri-h"><h2 id="ri-h">Recorded resource inventory ${AUTHOR}</h2><p class="small faint">Observed ${R.observed_at && R.observed_at.seattle}. File sha256 ${U.sha(R.file_sha256)}. Requested capacity and job outcomes as recorded; this page does not turn them into utilisation or spend.</p>
      <ul class="small">${((R.scope || {}).limitations || []).map((x) => html`<li>${x}</li>`)}</ul>
      <dl class="kv"><div><dt>Nebius jobs by this project</dt><dd>${N.own_job_count ?? "unknown"} (${Object.entries(N.job_states || {}).filter(([, n]) => n).map(([k, n]) => `${n} ${k.toLowerCase()}`).join(", ")})</dd></div><div><dt>Active allocations now</dt><dd>${N.active_allocations ? N.active_allocations.instances + " instances, " + N.active_allocations.gpus + " GPUs" : "unknown"}</dd></div>
        <div><dt>Workers created by the last launch</dt><dd>${O.created_workers ?? "unknown"}</dd></div><div><dt>Provider billing meter queried</dt><dd>${String(O.provider_meter_queried)}</dd></div><div><dt>Actual spend</dt><dd>${O.actual_spend === null || O.actual_spend === undefined ? "unknown (not measured)" : O.actual_spend}</dd></div></dl>
      ${N.cpu_worker_attempt ? html`<p class="small"><b>CPU worker attempt:</b> provider result ${N.cpu_worker_attempt.provider_result} on quota ${N.cpu_worker_attempt.quota} (limit ${N.cpu_worker_attempt.quota_limit_vcpus} vCPUs, requested ${N.cpu_worker_attempt.aggregate_requested_vcpus}); job created: ${String(N.cpu_worker_attempt.job_created)}.</p>` : ""}
      ${G && G.project_id ? html`<p class="small"><b>Google compute:</b> enabled ${String(G.enabled)}${G.enable_attempt ? "; enabling failed with " + G.enable_attempt.result + " (" + G.enable_attempt.reason + ")" : ""}; VM created: ${String(G.vm_created)}.</p>` : ""}
      <details><summary class="small">Historical GPU telemetry, model usage, worker inventory, cost and sources</summary>${tree({ historical_gpu_telemetry: R.historical_gpu_telemetry, model_usage: R.model_usage, worker_inventory: R.worker_inventory, cost: R.cost, sources: R.sources }, 0)}</details></section>`;
  }

  function resources(snap, S, live) {
    return { html: html`${inventoryPanel(snap.resource_inventory)}<section class="panel build-report"><h2>Recorded use and its limits</h2>
      ${snap.timeline ? counterTable(snap.timeline.counters) : html`<p class="empty">No counter receipt is included in this snapshot.</p>`}
      ${auditPanels((snap.timeline || {}).audits)}<p class="small">These are dated observations. <a href="${DF.href("/work", {tab: "built"})}">How it was built</a> has the run timeline and failed attempts. Actual spend is unknown until a billing meter is queried.</p></section><div id="sysraw"></div>`,
      async after(root) {
        const host = root.querySelector("#sysraw");
        if (live) { const r = await DF.api.system(); host.innerHTML = liveSystem(r).toString(); return; }
        host.innerHTML = html`<p class="small faint">Live runtime details are unavailable in snapshot mode. The dated records above remain available.</p>`.toString();
      } };
  }

  DF.liveSystem = (r) => liveSystem(r);
  const MODE = (m) => (m === "measured" ? MEAS : m === "worker_report" ? AUTHOR : U.pill(String(m || "unlabelled"), "st-unk"));
  const bytes = (n) => (n === null || n === undefined ? "unknown" : n >= 1e9 ? (n / 1e9).toFixed(2) + " GB" : n >= 1e6 ? (n / 1e6).toFixed(1) + " MB" : Math.round(n / 1e3) + " kB");
  const sect = (s) => (s && s.status === "unavailable" ? html`<p class="empty">This section was unavailable on the runtime (${s.section}). Nothing is shown in its place.</p>` : null);

  /* Rendered from the documented frontier.system/1 shape (frontier/system_status.py). Every section carries its own mode label. */
  function liveSystem(r) {
    if (r.unavailable) return html`<section class="panel"><h2>Live system report</h2><p class="empty">Not available (${r.reason}). Nothing is shown in its place.</p></section>`;
    const R = r.report; if (!R || R.schema !== "frontier.system/1") return html`<section class="panel"><h2>Live system report</h2><p class="note warn small">The runtime answered with an unrecognised schema (${String(R && R.schema)}), so it is shown unprocessed.</p>${rawJson("the system report", R)}</section>`;
    const st = R.store || {}, pr = R.process || {}, ho = R.host || {}, sv = R.services || {}, rl = R.release || {}, rs = R.resources || {};
    return html`<section class="panel"><h2>Live system report ${MEAS}</h2><p class="small faint">Generated ${R.generated_at}${R.cache ? `, ${R.cache.cached ? "cached " + R.cache.age_seconds + " s" : "fresh"} (reused up to ${R.cache.ttl_seconds} s)` : ""}. ${R.legend ? R.legend.measured : ""}</p>
      <h3>Store ${MODE(st.mode)}</h3>${sect(st) || html`<p class="small">${st.note}</p>${st.counts_scope ? html`<p class="note warn small"><b>Scope.</b> ${st.counts_scope}</p>` : ""}${(st.versions_by_namespace || []).length ? html`<p class="small">By namespace (record versions): ${st.versions_by_namespace.map((n) => `${n.namespace} ${n.versions}`).join(", ")}. This node's own namespace is ${st.namespace}.</p>` : ""}<div class="tablewrap"><table><thead><tr><th>Kind</th><th>Local status</th><th>Versions</th><th>Current heads</th></tr></thead><tbody>${(st.records_by_kind_and_local_status || []).map((x) => html`<tr><td>${x.kind}</td><td>${String(x.local_status).replace(/_/g, " ")}</td><td>${x.versions}</td><td>${x.heads}</td></tr>`)}</tbody></table></div>
        <p class="small">Events by type: ${(st.events_by_type || []).map((e) => `${e.event_type} ${e.count}`).join(", ") || "none"}. Database ${bytes(st.database && st.database.size_bytes)}, up ${st.database ? Math.round(st.database.uptime_seconds / 60) + " min" : "unknown"}, PostgreSQL ${st.database && st.database.server_version}. These are record counts, not independent observations.</p>`}
      <h3>Services ${MODE(sv.mode)}</h3><div class="tablewrap"><table><thead><tr><th>Unit</th><th>State</th><th>Restarts</th><th>Memory</th><th>Tasks</th><th>Active since</th></tr></thead><tbody>${(sv.units || []).map((u) => html`<tr><td><code>${u.unit}</code></td><td>${u.state === "measured" ? `${u.active_state}/${u.sub_state}` : "unavailable"}</td><td>${u.restarts ?? "unknown"}</td><td>${bytes(u.memory_current_bytes)}</td><td>${u.tasks_current ?? "unknown"}</td><td>${u.active_since || ""}</td></tr>`)}</tbody></table></div>
      <h3>This web process ${MODE(pr.mode)}</h3>${sect(pr) || html`<p class="small">${pr.scope}: up ${Math.round(pr.uptime_seconds)} s, ${bytes(pr.resident_memory_kb * 1000)} resident, ${pr.threads} threads, CPU ${pr.cpu_seconds && pr.cpu_seconds.user} s user / ${pr.cpu_seconds && pr.cpu_seconds.system} s system.</p>`}
      <h3>Host ${MODE(ho.mode)}</h3>${sect(ho) || html`<p class="note warn small"><b>${ho.scope}</b></p><p class="small">${ho.cpu_count} CPUs; load ${ho.load_average ? `${ho.load_average["1m"]} / ${ho.load_average["5m"]} / ${ho.load_average["15m"]}` : "unknown"}; memory available ${bytes(ho.memory_kb && ho.memory_kb.MemAvailable * 1000)} of ${bytes(ho.memory_kb && ho.memory_kb.MemTotal * 1000)}${ho.cpu_pressure_some ? `; CPU pressure (some) avg10 ${ho.cpu_pressure_some.avg10}` : ""}.</p>`}
      <h3>Release ${MODE(rl.mode)}</h3>${R.deployed_sha || rl.sha || rl.checkout_sha ? html`<p>Running release (measured): <code>${R.deployed_sha || rl.sha || rl.checkout_sha}</code> <span class="faint small">${rl.sha_source ? "from " + rl.sha_source : ""}</span></p>` : claimBlock(R)}
      <p class="small faint">${rl.checkout_sha ? "" : "No git checkout (an archive was deployed), so the git commit is not measured. "}${rl.dir_sha ? "Release directory name: " + rl.dir_sha + "; matches the release marker: " + String(rl.dir_name_matches_release_marker) + ". " : ""}${rl.note || ""}</p>${buildBlock(R.build)}${workerSections(R)}
      <h3>Provider job receipts ${MODE(rs.mode)}</h3>${resBlock(rs)}</section>`;
  }
  /* An archive deployment has no .git: the commit is the release directory's claim, checked only against the tree hash the release tool recorded. */
  function claimBlock(R) {
    const dc = (R.release && R.release.directory_claim) || {}; const c = dc.contents || {}; const sha = R.claimed_sha || dc.sha;
    if (!sha) return html`<p>Running release: <b>not reported</b>. The deployed tree is not a git checkout and no release directory claim is present.</p>`;
    return html`<p>Release directory claims commit <code>${sha}</code> <span class="pill st-unk">claim, not measured</span></p>
      <p class="small">${c.checked ? html`Files on disk ${c.matches_recorded_tree ? "match" : html`<b>do NOT match</b>`} the git tree hash the release tool recorded (${c.files_hashed} files hashed in ${c.seconds} s; tree <code>${c.tree_sha_computed}</code>).` : "The files were not checked against the recorded tree hash."} ${dc.marker_matches_name === true ? "The release marker agrees with the directory name." : dc.marker_matches_name === false ? html`<b>The release marker disagrees with the directory name.</b>` : ""}</p>
      <details><summary class="small">What this does and does not show</summary><p class="small">${c.meaning || ""} ${dc.label || ""} No git checkout exists in the deployment, so the commit itself is not measured.</p></details>`;
  }

  function buildBlock(b) {
    if (!b || b.status === "unavailable") return "";
    if (b.status !== "reported") return html`<p class="small">${AUTHOR} Build info: <b>${b.status}</b>. ${b.reason || ""} ${b.note || ""}</p>`;
    return html`<p class="small">${AUTHOR} ${b.label || "Written when the release was cut; not verified here."}</p>
      <p class="small">Release <code>${b.release_sha}</code>, built ${b.built_at}${b.tree_sha ? html`, tree <code>${b.tree_sha}</code>` : ""}${b.archive_sha256 ? html`, archive sha256 ${U.sha(b.archive_sha256)}` : ""}. Matches the measured ${b.compared_with || "checkout"}: <b>${b.matches_checkout === null || b.matches_checkout === undefined ? "not determinable" : String(b.matches_checkout)}</b>. File sha256 ${U.sha(b.sha256)}${b.checks_receipt_sha256 ? html`; checks receipt ${U.sha(b.checks_receipt_sha256)}` : ""}.</p>
      ${(b.checks || []).length ? html`<div class="tablewrap"><table><thead><tr><th>Check (as reported)</th><th>Result</th><th>Command</th><th>At</th></tr></thead><tbody>${b.checks.map((c) => html`<tr><td>${c.name}</td><td>${c.result || (c.passed !== undefined ? `${c.passed} of ${c.total} passed` : c.exit !== undefined ? `exit ${c.exit}` : "")}${c.exit !== undefined && c.passed !== undefined ? `, exit ${c.exit}` : ""}</td><td><code>${c.command || ""}</code></td><td class="small">${c.at || ""}</td></tr>`)}</tbody></table></div><p class="small faint">${b.checks_all_passed === true ? "The report states all listed checks passed. " : b.checks_all_passed === false ? "The report states not all listed checks passed. " : ""}Only the checks listed here are reported; nothing is counted beyond them, and the page has not re-run them.</p>` : html`<p class="small faint">No check is listed in the build report.</p>`}`;
  }
  /* Worker-report sections of the live report: the checkout's own board, specs and goal, shown as reports, not as measurements. */
  function workerSections(R) {
    const bd = R.board || {}, sp = R.specs || {}, gl = R.goal || {};
    return html`<h3>Tasks, specs and goal as the running checkout reports them ${MODE("worker_report")}</h3>
      ${bd.rows ? html`<p class="small faint">${bd.source}, file sha256 ${U.sha(bd.sha256)}. Status text is the coordinator's; it is not checked.</p><div class="tablewrap"><table><thead><tr><th>Priority</th><th>Deliverable</th><th>Owner</th><th>Status / acceptance</th></tr></thead><tbody>${bd.rows.map((r) => html`<tr><td>${r.priority}</td><td>${r.deliverable}</td><td>${r.owner}</td><td>${r.status_acceptance || r.status_text || r.status || ""}</td></tr>`)}</tbody></table></div>${(bd.findings_to_correct || []).length ? html`<details><summary class="small">Findings to correct (${bd.findings_to_correct.length})</summary><ul>${bd.findings_to_correct.map((f) => html`<li class="small">${f}</li>`)}</ul></details>` : ""}` : html`<p class="empty">The board is ${bd.status || "not reported"}${bd.reason ? " (" + bd.reason + ")" : ""}.</p>`}
      ${(sp.specs || []).length ? html`<div class="tablewrap"><table><thead><tr><th>Spec</th><th>Title</th><th>Status line (as written)</th><th>sha256</th></tr></thead><tbody>${sp.specs.map((x) => html`<tr><td>${x.id}</td><td>${x.title}</td><td class="small">${x.status_line || ""}</td><td>${U.sha(x.sha256)}</td></tr>`)}</tbody></table></div>` : ""}
      ${gl.title ? html`<p class="small"><b>Goal:</b> ${gl.title}. ${gl.summary} (sha256 ${U.sha(gl.sha256)})</p>` : ""}`;
  }
  function resBlock(rs) {
    return html`<p><b>Actual cost:</b> ${rs.actual_cost ? rs.actual_cost.status : "unknown"}. ${rs.actual_cost ? rs.actual_cost.reason : ""}</p><p><b>Utilisation:</b> ${rs.utilization ? rs.utilization.status.replace(/_/g, " ") : "unknown"}. ${rs.utilization ? rs.utilization.reason : ""}</p>
      ${(rs.receipt_files || []).length ? html`<div class="tablewrap"><table><thead><tr><th>Receipt</th><th>Status</th><th>Pinned sha256</th></tr></thead><tbody>${rs.receipt_files.map((f) => html`<tr><td>${f.id}<br><span class="small faint">${f.description || ""}</span></td><td>${f.status}</td><td>${U.sha(f.pinned_sha256)}</td></tr>`)}</tbody></table></div>` : html`<p class="empty">No pinned receipt file.</p>`}
      ${(rs.jobs || []).length ? html`<div class="tablewrap"><table><thead><tr><th>Job</th><th>State</th><th>Self-reported wall (s)</th><th>Timed out</th><th>First / last event</th></tr></thead><tbody>${rs.jobs.map((j) => html`<tr><td>${j.job_name || j.job_id || ""}<br><span class="small faint">${j.item || ""}</span></td><td>${j.job_state || j.controller_status || ""}</td><td>${j.inner_wall_s ?? "unknown"}</td><td>${String(j.timed_out)}</td><td class="small">${j.first_event_at || ""}<br>${j.last_event_at || ""}</td></tr>`)}</tbody></table></div><p class="small faint">${rs.jobs_reported} jobs; ${rs.sum_note || ""}</p>` : ""}`;
  }

  function receipts(snap, S) {
    return { html: html`<section class="panel"><h2>What has been measured ${MEAS}</h2><p class="note small">Each row is a receipt present in this tree, with its hash and what it covers. A receipt covers only what it says; none of these is a biological validation.</p>
      <div class="tablewrap"><table><thead><tr><th>What</th><th>Result</th><th>Receipt</th><th>Covers</th></tr></thead><tbody>${S.measured.map((m) => html`<tr><td>${m.what}</td><td>${m.result}</td><td><code>${m.receipt}</code><br>${U.sha(m.sha256)}</td><td>${m.covers}</td></tr>`)}</tbody></table></div>
      ${S.measured.length ? "" : U.empty("No receipt is listed in this summary.")}<p class="small faint">This table is a selected summary. <a href="${DF.href("/work", {tab: "built"})}">How it was built</a> and <a href="${DF.href("/work", {tab: "resources"})}">Resources</a> contain the dated compute and model-use records; <a href="${DF.href("/reuse")}">Claim reuse</a> shows executed reuse and independent review.</p></section>` };
  }

  /* /api/counts as received: scalars with their units, nested groups collapsed, and every note or basis string kept right next to the numbers it qualifies. */
  const NOTEKEYS = new Set(["note", "basis", "meaning", "scope", "label"]);
  /* Large JSON stays out of the page until asked for: collapsed, and filled in only when opened. */
  const RAW = new Map(); let rawN = 0;
  function rawJson(label, obj) {
    const id = "raw" + ++rawN; RAW.set(id, obj); let n = 0; try { n = JSON.stringify(obj).length; } catch (e) { n = 0; }
    return html`<details class="rawjson" data-raw="${id}"><summary class="small">Show ${label} as received <span class="faint">(about ${n.toLocaleString("en")} characters)</span></summary><pre class="json" aria-label="Raw ${label}"></pre></details>`;
  }
  document.addEventListener("toggle", (e) => { const d = e.target; if (d && d.classList && d.classList.contains("rawjson") && d.open) { const pre = d.querySelector("pre"); if (pre && !pre.textContent) pre.textContent = JSON.stringify(RAW.get(d.dataset.raw), null, 2); } }, true);

  function tree(o, depth = 0) {
    if (o === null || o === undefined) return html`<span class="faint">none</span>`;
    if (typeof o !== "object") return html`${String(o)}`;
    if (Array.isArray(o)) return o.length > 8 ? html`${o.length} items` : html`${o.map((x) => (typeof x === "object" ? JSON.stringify(x) : String(x))).join(", ")}`;
    const ent = Object.entries(o); const notes = ent.filter(([k, v]) => NOTEKEYS.has(k) && typeof v === "string"); const rest = ent.filter(([k, v]) => !(NOTEKEYS.has(k) && typeof v === "string"));
    const simple = rest.every(([, v]) => v === null || typeof v !== "object");
    return html`${notes.map(([k, v]) => html`<p class="small faint"><b>${k}.</b> ${v}</p>`)}${simple ? html`<dl class="kv">${rest.map(([k, v]) => html`<div><dt>${k.replace(/_/g, " ")}</dt><dd>${String(v)}</dd></div>`)}</dl>` : html`<ul class="ctree">${rest.map(([k, v]) => (v && typeof v === "object" && depth >= 1 ? html`<li><details><summary>${k.replace(/_/g, " ")}</summary>${tree(v, depth + 1)}</details></li>` : html`<li><b>${k.replace(/_/g, " ")}</b>: ${tree(v, depth + 1)}</li>`))}</ul>`}`;
  }
  function countsView(R) {
    const keys = Object.keys(R).filter((k) => !["cache_seconds", "schema", "generated_at"].includes(k));
    return html`<p class="note small">Counts of records and declarations, not independent observations. A number comes with the note the node attaches to it (for example, zero byte-checked is the absence of any check, not a finding). Cached ${R.cache_seconds || "?"} s.</p>${keys.map((k) => html`<details ${["claims", "artifacts"].includes(k) ? raw("open") : ""}><summary><b>${k.replace(/_/g, " ")}</b></summary>${tree(R[k], 0)}</details>`)}`;
  }

  /* Connect and share: what a person or agent can actually use, with what is and is not verified. Nothing is claimed beyond the repository's own documents. */
  function connect(snap, S, live) {
    const origin = "https://frontier.morphoswarm.ai";
    const endpoint = origin + "/mcp";
    const config = JSON.stringify({ mcpServers: { frontier: { type: "http", url: endpoint } } }, null, 2);
    const apis = [["GET /api/health", "service status"], ["GET /api/catalog, /api/record, /api/events", "records, with exact pins"], ["GET /api/discovery?q=", "search (the response says which engine ran)"], ["GET /api/graph", "neighbourhood of one exact record"], ["GET /api/artifacts, /api/media?sha256=", "declared artifacts; node-verified local copies"], ["GET /api/attention, /api/system, /api/counts", "open work, system report, corpus counts"], ["POST /api/engineering/solve, /api/beliefs/solve, /api/simulations/run", "bounded calculations; they store nothing"]];
    return { html: html`<section class="panel" aria-labelledby="cn-h"><h2 id="cn-h">Connect an agent (MCP)</h2>
      <p>Give your agent access to the shared frontier: find claims, inspect projects and artifacts, explore open questions, and run bounded calculations.</p>
      <p><b>Streamable HTTP endpoint:</b> <a id="mcp-endpoint" href="${endpoint}">${endpoint}</a> <button class="btn small" type="button" id="copy-mcp">Copy endpoint</button> <span id="mcp-copied" class="small" role="status"></span></p>
      <p class="small">Public reads need no token. Use this URL in your MCP client's remote-server settings; it is a protocol endpoint, not a web page.</p>
      <details><summary>Client configuration</summary><p class="small">For clients that accept an <code>mcpServers</code> JSON configuration. Other clients ask for the URL directly.</p><pre class="json" id="mcp-config" tabindex="0">${config}</pre><button class="btn small" type="button" id="copy-mcp-config">Copy configuration</button> <span id="mcp-config-copied" class="small" role="status"></span></details>
      <p class="note small"><b>What is verified.</b> The public endpoint <code>${origin}/mcp</code> passed ${snap.mcp_check ? snap.mcp_check.passed + " of " + snap.mcp_check.total : "recorded"} checks with the official MCP SDK client (Streamable HTTP): initialisation, tool discovery, anonymous public identity, schema resources, a public fish search, anonymous writes denied before validation, an invalid token rejected, and public system metadata${snap.mcp_check ? ", at " + snap.mcp_check.checked_at : ""}. ${snap.mcp_check ? "Records written by that check: " + snap.mcp_check.scientific_records_written + "." : ""} <b>A specific product client (for example a desktop or IDE assistant) is not tested.</b> Report what yours actually does. <span class="faint">${snap.mcp_check ? snap.mcp_check.scope : ""}</span></p>
      <ul><li><b>Reading</b> public records, artifacts and schemas needs no credential on a public-read node.</li><li><b>Writing</b> (propose, lease, change state) needs the calling operator's own bearer credential; it is checked per request and an invalid one is refused, never treated as anonymous. Proposals stay <i>proposed</i> until an independent operator reviews them.</li><li>Never put a credential in a prompt, a URL or a shared link.</li></ul>
      <p class="small">Tools declared in <code>docs/mcp.md</code>: ${snap.capabilities.map((t) => html`<code>${t.name}</code> (${t.mode}) `)}. ${U.src("doc:mcp", "Read the MCP document")}</p></section>
      <section class="panel"><h2>Use the node directly (HTTP, read-only unless noted)</h2><div class="tablewrap"><table><thead><tr><th>Endpoint</th><th>What it gives</th></tr></thead><tbody>${apis.map(([e, w]) => html`<tr><td><code>${e}</code></td><td>${w}</td></tr>`)}</tbody></table></div><p class="small faint">Calculation endpoints need a session token from <code>GET /api/session</code> and send it as <code>X-CSRF-Token</code>.</p></section>
      <section class="panel"><h2>Share this view</h2><p class="small">The address bar carries the exact view, record pin or filter. Links to records include their version, so a shared link names the same record version for everyone.</p><p><input id="sharelink" type="text" readonly value="${location.href}" size="60" aria-label="Link to this view"> <button class="btn small" type="button" id="copylink">Copy link</button> <span id="copied" class="small" role="status"></span></p></section>`,
      after(root) {
        const copy = (button, text, status) => root.querySelector(button).addEventListener("click", async () => {
          try { await navigator.clipboard.writeText(text()); root.querySelector(status).textContent = "Copied."; }
          catch (e) { root.querySelector(status).textContent = "Select the text and copy it; this browser blocked clipboard access."; }
        });
        copy("#copy-mcp", () => endpoint, "#mcp-copied");
        copy("#copy-mcp-config", () => config, "#mcp-config-copied");
        copy("#copylink", () => root.querySelector("#sharelink").value, "#copied");
      } };
  }

  function runtime(snap, S, live) {
    return { html: html`<section class="panel"><h2>Runtime</h2><p>${U.pill(live ? "live runtime" : "snapshot only", live ? "ok" : "warn")} ${DF.api.state.reason}.</p>
        ${live ? html`<p>Namespace: <code>${DF.api.state.health.namespace || "not reported"}</code>.</p>` : html`<p class="note small">No runtime is connected, so there are no agents, leases, resources or contributions to show. Nothing below is simulated.</p>`}</section>
      <section class="panel"><h2>Events</h2><div id="events" role="status">Loading…</div></section>
      ${live ? html`<section class="panel" aria-labelledby="cnt-h"><h2 id="cnt-h">Corpus counts (from the node)</h2><div id="corpuscounts" role="status">Loading…</div></section>` : ""}
      ${live ? html`<section class="panel"><h2>What the live store holds</h2><p class="note small">Counts of records by kind, read by paging the catalog (50 per page). These are records, not independent observations: imported claims repeat what their sources assert.</p><button class="btn small" type="button" id="countrecs">Count records by kind</button><div id="counts" role="status"></div></section>` : ""}
      <section class="panel"><h2>Declared capabilities (MCP tools)</h2><p class="note small">Parsed from the Tools row of <code>docs/mcp.md</code>. A declared tool is not demonstrated competence; no success receipts are attached.</p>
        <div class="tablewrap"><table><thead><tr><th>Tool</th><th>Mode</th></tr></thead><tbody>${snap.capabilities.map((t) => html`<tr><td><code>${t.name}</code></td><td>${t.mode}</td></tr>`)}</tbody></table></div>
        <p class="small">Writes need <code>--allow-write</code> and an operator credential kept outside prompts; contributions stay proposed. ${U.src("doc:mcp", "Read the MCP document")}</p></section>`,
      async after(root) {
        const cc = root.querySelector("#corpuscounts");
        if (cc) DF.api.counts().then((r) => { cc.removeAttribute("role"); cc.innerHTML = (r.unavailable ? `<p class="empty">The counts endpoint did not answer (${esc(r.reason)}). Nothing is shown in its place; the button below pages the catalog instead.</p>` : countsView(r.report)).toString(); });
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
