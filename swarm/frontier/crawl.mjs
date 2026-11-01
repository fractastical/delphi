#!/usr/bin/env node
/* Crawl https://frontier.morphoswarm.ai/#/work?tab=built ("How it was built").
 *
 * The site is a hash-routed single-page app with no server-side HTML: every view is drawn in the browser from
 * data/snapshot.json (and data/catalog.json). Fetching the hash URL returns only the empty shell, so this script
 * does what the page does: it downloads the snapshot and extracts exactly the fields that views4.js `built()`
 * renders (timeline, system.review_corrections, openresearch, recovery_inputs, diffusion_pilot), plus the two
 * same-origin documents the tab links to. Nothing is summarised or recomputed; every number is the one in the file.
 *
 *   node swarm/frontier/crawl.mjs            # writes swarm/frontier/{crawl.json,built.json,BUILT.md,raw/}
 *   node swarm/frontier/crawl.mjs --render   # re-render BUILT.md from raw/ without fetching
 */
import { createHash } from "node:crypto";
import { mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ORIGIN = "https://frontier.morphoswarm.ai/";
const PAGE = ORIGIN + "#/work?tab=built";
const RAW = join(HERE, "raw");
const UA = "delphisci-swarm-crawl/0.1 (+https://github.com/fractastical/delphi)";
const renderOnly = process.argv.includes("--render");

const sha256 = (buf) => createHash("sha256").update(buf).digest("hex");

async function fetchRaw(path) {
  const url = ORIGIN + path;
  const r = await fetch(url, { headers: { "User-Agent": UA, Accept: "*/*" }, cache: "no-store" });
  if (!r.ok) throw new Error(`HTTP ${r.status} for ${url}`);
  const buf = Buffer.from(await r.arrayBuffer());
  return { url, path, bytes: buf.length, sha256: sha256(buf), content_type: r.headers.get("content-type"), buf };
}

async function main() {
  await mkdir(RAW, { recursive: true });
  const retrieved_at = new Date().toISOString();
  let snapshot, fetched = [];

  if (renderOnly) {
    snapshot = JSON.parse(await readFile(join(RAW, "snapshot.json"), "utf8"));
  } else {
    const snap = await fetchRaw("data/snapshot.json");
    snapshot = JSON.parse(snap.buf.toString("utf8"));
    if (snapshot.schema !== "frontier-site-snapshot-0.1") throw new Error("unexpected snapshot schema " + snapshot.schema);
    const linked = ["data/catalog.json", "artifacts/coordination/collective-review-evidence.md"];
    if (snapshot.system?.review_corrections?.href) linked.unshift(snapshot.system.review_corrections.href);
    const docs = [snap];
    for (const p of linked) {
      try { docs.push(await fetchRaw(p)); } catch (e) { fetched.push({ path: p, error: String(e.message) }); }
    }
    // Where the snapshot itself quotes a sha256 for a linked document, compare it with what we downloaded.
    const quoted = { [snapshot.system?.review_corrections?.href]: snapshot.system?.review_corrections?.sha256 };
    for (const d of docs) {
      const name = d.path.split("/").pop();
      await writeFile(join(RAW, name), d.buf);
      const row = { path: d.path, url: d.url, saved_as: "raw/" + name, bytes: d.bytes, sha256: d.sha256, content_type: d.content_type };
      if (quoted[d.path]) row.matches_digest_quoted_in_snapshot = quoted[d.path] === d.sha256;
      fetched.push(row);
    }
  }

  // Exactly what the "How it was built" tab reads.
  const built = {
    source_page: PAGE,
    renderer: "js/views4.js built(snap)",
    snapshot_label: snapshot.label,
    input_fingerprint: snapshot.input_fingerprint,
    inputs_hashed: snapshot.inputs?.length ?? null,
    timeline: snapshot.timeline ?? null,
    review_corrections: snapshot.system?.review_corrections ?? null,
    openresearch: snapshot.openresearch ?? null,
    recovery_inputs: snapshot.recovery_inputs ?? null,
    diffusion_pilot: snapshot.diffusion_pilot ?? null,
  };
  await writeFile(join(HERE, "built.json"), JSON.stringify(built, null, 2) + "\n");

  if (!renderOnly) {
    const crawl = {
      schema: "delphisci-frontier-crawl/0.1",
      page: PAGE,
      retrieved_at,
      how: "The page is a client-rendered SPA; its content comes from data/snapshot.json. Fetched that file plus the documents the tab links to, extracted the fields views4.js built() renders into built.json, rendered BUILT.md from them. Not re-verified: none of the sha256 digests the snapshot quotes for files inside the upstream repository were checked against that repository.",
      upstream_repository: "https://github.com/kganjam/delphi-frontier",
      snapshot_label: snapshot.label,
      input_fingerprint: snapshot.input_fingerprint,
      fetched,
      outputs: ["built.json", "BUILT.md", "raw/"],
    };
    await writeFile(join(HERE, "crawl.json"), JSON.stringify(crawl, null, 2) + "\n");
  }

  const prov = JSON.parse(await readFile(join(HERE, "crawl.json"), "utf8"));
  await writeFile(join(HERE, "BUILT.md"), render(built, prov));
  console.log(`crawled ${PAGE}\n  snapshot ${snapshot.label} (${snapshot.input_fingerprint})\n  timeline rows ${built.timeline?.rows?.length ?? 0}, undated ${built.timeline?.undated?.length ?? 0}, counters ${built.timeline?.counters?.length ?? 0}, jobs ${built.timeline?.usage?.jobs?.length ?? 0}\n  wrote built.json, BUILT.md, crawl.json, raw/`);
}

/* ---- Markdown rendering: the same sections, in the same order, as the page ---- */
const esc = (s) => String(s ?? "").replace(/\|/g, "\\|").replace(/\r?\n/g, " ");
const short = (h) => (h ? "`" + h.slice(0, 12) + "…`" : "no digest recorded");
const tone = (ok) => (ok === true ? "passed" : ok === false ? "failed" : "recorded");
const table = (head, rows) => ["| " + head.join(" | ") + " |", "|" + head.map(() => "---").join("|") + "|", ...rows.map((r) => "| " + r.map(esc).join(" | ") + " |")].join("\n");
const timeOf = (t) => String(t).replace("T", " ").replace(/\.\d+Z?$/, "").replace("+00:00", "");

/* Same three panels as the page's auditPanels(): contributors, repositories, models. Full data stays in built.json. */
function auditPanels(audits) {
  const out = [];
  const A = audits.contributors, R = audits.repositories, M = audits.models;
  const a = A?.data, r = R?.data, m = M?.data;
  out.push(`## Audits\n`);
  if (a) {
    out.push(`### Who contributed? The dated identity audit\n`);
    out.push(`Observed ${a.window?.observed_utc}. ${a.not_summed ?? ""} ${a.contribution_activity ?? ""}\n`);
    out.push(`**Contributing harnesses, supported minimum (${Object.keys(a.supported_harnesses || {}).length}):**\n`);
    for (const [id, v] of Object.entries(a.supported_harnesses || {})) out.push(`- \`${id}\` — ${v.mapping ? v.mapping.role : v.basis}`);
    out.push("");
    out.push(`**Native collaborators, separate identities (${a.native_contributors?.entries?.length ?? 0}):**\n`);
    for (const v of a.native_contributors?.entries || []) out.push(`- \`${v.identity}\` — ${v.role}${v.verified ? " (artifact verified)" : ""}`);
    out.push("");
    if (a.participation) {
      const p = a.participation;
      out.push(`**${p.recorded_participant_floor} recorded participants**: ${p.supported_harnesses} harnesses, ${p.recorded_native_children} native children and ${p.recorded_nested_claude_children} nested Claude children; the child groups total ${p.recorded_native_children + p.recorded_nested_claude_children} recorded subagents. Historical identities, not concurrent workers. Transcript scan: ${JSON.stringify(p.task_units)}. Source \`${p.source}\` ${short(p.source_sha256)}.\n`);
    }
    if (a.counts) out.push(`Counts: ${Object.entries(a.counts).map(([k, v]) => `${k} = ${typeof v === "object" ? JSON.stringify(v) : v}`).join("; ")}.\n`);
    out.push(`Identity links include coordinator attestations; artifact checks establish that the work exists, not independent proof of authorship. Full audit \`${A.path}\` ${short(A.sha256)}.\n`);
  }
  if (r) {
    out.push(`### Repository activity, four pinned histories\n`);
    out.push(`${r.scope} Window ${r.since_utc} through ${r.until_utc}.\n`);
    out.push(table(["Repository", "Commits", "Non-merge / merge", "Pinned revision"], r.repositories.map((x) => [x.url ? `[${x.repository}](${x.url})` : x.repository, x.counts.commit_objects, `${x.counts.non_merge_commits} / ${x.counts.merge_commits}`, x.head_sha?.slice(0, 10)])));
    out.push("");
    if (r.deduplicated_counts) out.push(`Deduplicated: ${JSON.stringify(r.deduplicated_counts)}. Commits are not participants or validated findings. Full IDs \`${R.path}\` ${short(R.sha256)}.\n`);
  }
  if (m) {
    out.push(`### Models and simulators actually exercised, ${m.entries.length} scoped records\n`);
    out.push(`${m.scope}\n`);
    if (m.bionemo_nim?.statement) out.push(`${m.bionemo_nim.statement}\n`);
    out.push(table(["Model or simulator", "id", "Provider", "Recorded outcome", "Usage (as recorded)", "Evidence"], m.entries.map((e) => [e.model || e.model_or_tool || (e.models || []).map((x) => x.model).join(", "), "`" + e.id + "`", e.provider, `${String(e.status).replace(/_/g, " ")}${e.scope_note ? ". " + e.scope_note : ""}`, e.usage || e.calls ? JSON.stringify(e.usage || e.calls) : "see receipt", (e.evidence || []).map((x) => `\`${x.path}\``).join(", ")])));
    out.push("");
    if (m.accounting) out.push(`Accounting, as stated upstream: ${Object.entries(m.accounting).map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join("; ") : v}`).join(". ")}.\n`);
    out.push(`${m.source_tree_note ?? ""} Full ledger \`${M.path}\` ${short(M.sha256)}.\n`);
  }
  return out.join("\n");
}

function render(b, prov) {
  const T = b.timeline;
  const out = [];
  out.push(`# How it was built — frontier.morphoswarm.ai (crawl)\n`);
  out.push(`Crawled from [${b.source_page}](${b.source_page}) on ${prov.retrieved_at}. The page is drawn in the browser from \`data/snapshot.json\` (snapshot label **${b.snapshot_label}**, input fingerprint \`${b.input_fingerprint}\`, ${b.inputs_hashed} input files hashed). This file re-renders the fields that page reads; the exact data is in [built.json](built.json) and the untouched download in \`raw/\`. Upstream source: [kganjam/delphi-frontier](${prov.upstream_repository}). All statements below are the upstream authors' own records, quoted, not re-verified by this repo.\n`);
  if (!T) { out.push("No resource inventory or receipts are present in this snapshot.\n"); return out.join("\n"); }
  out.push(`Inventory observed ${T.observed_at?.seattle ?? ""} (${T.observed_at?.utc ?? ""}). Event window from ${T.event_window_start_utc}.\n`);

  out.push(`## Recorded counters\n`);
  out.push(table(["Quantity", "Value", "Status", "Note", "Source"], T.counters.map((c) => [c.quantity, c.value, c.status, c.note, c.source])));
  out.push("");

  if (T.audits) out.push(auditPanels(T.audits));

  if (b.review_corrections) {
    const R = b.review_corrections;
    out.push(`## Where review changed a decision\n`);
    out.push(`${R.nature ?? ""}\n`);
    for (const e of R.entries) {
      out.push(`- **${e.title}.** ${e.decision_changed}` + (e.correction?.commit ? ` (commit \`${e.correction.commit}\`${e.correction.protocol_frozen_before_rerun ? `, protocol frozen before rerun \`${e.correction.protocol_frozen_before_rerun}\`` : ""})` : ""));
    }
    out.push("");
    if (R.independence) out.push(`Independence, as stated upstream: ${R.independence}\n`);
    if (R.counterfactual) out.push(`Counterfactual, as stated upstream: ${R.counterfactual}\n`);
    if (R.not_claimed?.length) out.push(`Not claimed upstream:\n${R.not_claimed.map((x) => "- " + x).join("\n")}\n`);
    out.push(`Record: \`${R.href}\` ${short(R.sha256)} (saved as \`raw/${R.href.split("/").pop()}\`).\n`);
  }

  if (T.usage) {
    const U = T.usage;
    out.push(`## Role assignments in the earlier usage slice\n`);
    out.push(`One session can fill several roles (upstream note). Observed ${U.observed_at_seattle}.\n`);
    out.push(table(["Contributor", "Kind", "Role", "Status as recorded"], U.roles.map((r) => [r.id, r.kind, r.role, r.status])));
    out.push("");
    out.push(`## Own provider jobs (${U.jobs.length})\n`);
    const states = {};
    for (const j of U.jobs) states[j.state] = (states[j.state] || 0) + 1;
    out.push(`By provider state: ${Object.entries(states).map(([k, n]) => `${n} ${k}`).join(", ")}. Provider COMPLETED means the container ended, not that a scientific check passed.\n`);
    out.push(table(["Created", "Kind", "Job", "Provider state", "Capacity"], U.jobs.map((j) => [j.created, j.kind, j.name, j.state, j.capacity ? Object.entries(j.capacity).map(([k, v]) => `${k} ${v}`).join(", ") : ""])));
    out.push("");
    out.push(`## Controller outcomes for recent GPU tasks\n`);
    out.push(table(["Status", "Task", "Wall (s)", "Return code", "Path", "sha256"], U.controller.map((e) => [e.status, e.task, e.wall_s ?? "not recorded", e.rc ?? "not recorded", e.path, short(e.sha256)])));
    out.push("");
  }

  if (b.recovery_inputs) {
    const r = b.recovery_inputs;
    out.push(`## Failed primary diffusion-model training run, retained\n`);
    out.push(`Primary run status: **${r.primary_full_run_status}** (job \`${r.original_primary_job_id}\`). Checkpoint after ${r.training_steps} training steps, sha256 ${short(r.checkpoint_sha256)}. ${r.status}. Published: ${r.published}${r.published ? ` (\`${r.href}\`, ${(r.bytes / 1e6).toFixed(1)} MB, sha256 ${short(r.sha256)})` : ""}. Next step as recorded: ${r.next_admission}\n`);
    if (b.diffusion_pilot) out.push(`A separate diffusion pilot reused that checkpoint (${b.diffusion_pilot.files?.length ?? 0} files, manifest \`${b.diffusion_pilot.manifest_href}\`); the upstream page says its strict secondary audit failed and the primary timeout remains a failure.\n`);
  }

  if (b.openresearch) {
    out.push(`## Recorded OpenResearch runs (local exemplars)\n`);
    out.push(`${b.openresearch.scope}\n`);
    out.push(table(["Run", "Command", "Backend", "orx", "Started (UTC)", "Duration (s)", "Status", "Record"], b.openresearch.exemplars.map((e) => [e.title, "`" + e.command + "`", e.backend, e.orx_version, e.started_utc, e.duration_s, e.status, e.record])));
    out.push("");
    out.push(`${b.openresearch.report}\n`);
  }

  if (T.usage) {
    out.push(`External tools credited upstream: ${T.usage.credit.join(", ")}.\n`);
    out.push(`Usage-slice limitations:\n${T.usage.limitations.map((x) => "- " + x).join("\n")}\n`);
  }

  const N = T.nebius;
  out.push(`## Providers and jobs\n`);
  out.push(`- Nebius (GPU jobs): ${N.own_job_count} jobs by this project: ${Object.entries(N.job_states).filter(([, n]) => n).map(([k, n]) => n + " " + k.toLowerCase()).join(", ")} (observed ${N.observed_at_utc}). Allocation is requested capacity, not utilisation.`);
  out.push(`- Google Generative Language: ${T.rows.filter((r) => r.kind === "model usage").map((r) => r.title + ": " + r.outcome.split(";")[0]).join("; ")}.`);
  const live = T.rows.filter((r) => r.kind === "live check");
  out.push(`- Live checks of the public node: ${live.length} recorded, ${live.filter((r) => r.ok).length} with every check passed.\n`);
  out.push(`Unknown (upstream's own list): ${T.unknown.join(" ")}\n`);

  const kinds = [...new Set(T.rows.map((r) => r.kind))];
  out.push(`## Dated record (${T.rows.length} rows; ${kinds.join(", ")})\n`);
  out.push(table(["Time (UTC)", "Kind", "What", "Outcome", "Scope", "Evidence"], T.rows.map((r) => [timeOf(r.time), r.kind, r.title, `${tone(r.ok)}: ${r.outcome}`, r.scope ?? "", `\`${r.path}\` ${short(r.sha256)}`])));
  out.push("");

  out.push(`## Results, stops and failures, with what checked them (${T.undated.length})\n`);
  for (const r of T.undated) out.push(`- **${tone(r.ok)}** — **${r.title}**${r.date ? ` (${r.date}, date only)` : ""}: ${r.outcome}  \n  \`${r.path}\` ${short(r.sha256)}`);
  out.push("");

  out.push(`## Limits of this record (upstream)\n`);
  out.push(T.limitations.map((x) => "- " + x).join("\n") + "\n");
  out.push(`Inventory \`${T.inventory}\` ${short(T.inventory_sha256)}. Agent activity beyond these files is not reconstructed upstream, and nothing was reconstructed here.\n`);

  out.push(`## Files fetched\n`);
  out.push(table(["Path", "Saved as", "Bytes", "sha256 (of download)", "Matches digest quoted in snapshot"], prov.fetched.map((f) => [f.path, f.saved_as ?? "", f.bytes ?? "", f.sha256 ? "`" + f.sha256 + "`" : f.error ?? "", "matches_digest_quoted_in_snapshot" in f ? String(f.matches_digest_quoted_in_snapshot) : "no digest quoted"])));
  out.push("");
  return out.join("\n");
}

main().catch((e) => { console.error(e); process.exit(1); });
