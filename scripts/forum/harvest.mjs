#!/usr/bin/env node
// Harvest test results and claim proposals from the Science Claw forum into the repo.
//
//   node scripts/forum/harvest.mjs              # dry run: what would be taken, skipped or rejected, and why
//   node scripts/forum/harvest.mjs --write      # write the accepted files into this checkout
//   node scripts/forum/harvest.mjs --pr         # write them in a worktree off origin/main and open a pull request
//   options: --forum <url>  --post <id>  --since <ISO date>  --json
//
// Results (posts with a delphi:test-result block, from delphi_log_test_result) become
// test-data/claim-tests/<project>/<claim>/forum-<post>/result.json. A claim's top-level result.json
// wins over subfolders (scripts/site/load-claims.mjs), so a harvested run only becomes a claim's
// verdict where none exists. Proposals (delphi:claim-proposal blocks, from delphi_propose_claim)
// become claim-sources/forum-proposals/inbox/<post>.json for a maintainer to place in a project,
// assess and publish. Each file records the post in `forum`, which is how reruns skip it and how
// the leaderboard credits the agent (result.json agent.forum). Nothing is signed or published.

import { execFileSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");
const args = process.argv.slice(2);
const flag = name => args.includes(`--${name}`);
const opt = name => { const i = args.indexOf(`--${name}`); return i >= 0 ? args[i + 1] : undefined; };
const FORUM = (opt("forum") ?? process.env.CLAW_FORUM ?? "https://forum.delphibio.org").replace(/\/$/, "");
const PR = flag("pr"), WRITE = flag("write") || PR;

const VERDICTS = ["supports", "refutes", "mixed", "inconclusive"];
const REASONS = ["data-unavailable", "underpowered", "not-operationalizable", "other"];
const DATA_KINDS = ["biological", "physical", "computational", "none"];
const CLAIM_KINDS = ["empirical-generalization", "mechanism", "prediction", "experimental-result", "simulation-result", "historical-inference", "mathematical", "definition", "other"];
const TESTS = "test-data/claim-tests";
const INBOX = "claim-sources/forum-proposals/inbox";

const readJson = f => JSON.parse(readFileSync(f, "utf8"));
const short = id => id.slice(0, 8);
const postUrl = id => `${FORUM}/#/post/${id}`;

function walk(dir, name, out = []) {
  if (!existsSync(dir)) return out;
  for (const f of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, f.name);
    if (f.isDirectory() && !["data", "derived", "nanopubs", "node_modules", "__pycache__"].includes(f.name)) walk(p, name, out);
    else if (f.name === name || (name instanceof RegExp && name.test(f.name))) out.push(p);
  }
  return out;
}

// Which project each claim id belongs to, from the per-project claim lists.
function claimProjects() {
  const map = new Map();
  for (const project of readdirSync(join(ROOT, "claim-sources"))) {
    for (const f of [join(ROOT, "claim-sources", project, "claims.json"), join(ROOT, "claim-sources", project, "claims/key-claims.json")]) {
      if (!existsSync(f)) continue;
      const j = readJson(f);
      for (const c of Array.isArray(j) ? j : j.claims ?? []) if (c.id) map.set(c.id, project);
    }
  }
  return map;
}

// Posts already in the repo, by forum post id.
function harvested() {
  const seen = new Map();
  for (const f of [...walk(join(ROOT, TESTS), "result.json"), ...walk(join(ROOT, INBOX), /\.json$/)]) {
    try { const post = readJson(f).forum?.post; if (post) seen.set(post, relative(ROOT, f)); } catch {}
  }
  return seen;
}

async function forumPosts(query) {
  const posts = [];
  for (let cursor = null; ;) {
    const u = new URL(`${FORUM}/api/v1/posts`);
    for (const [k, v] of Object.entries({ ...query, sort: "new", limit: 100, ...(cursor ? { cursor } : {}) })) u.searchParams.set(k, v);
    const res = await fetch(u, { signal: AbortSignal.timeout(30_000) });
    const j = await res.json();
    if (!j.success) throw new Error(`Forum ${res.status}: ${j.error}`);
    posts.push(...j.data.posts);
    if (!j.data.has_more) return posts;
    cursor = j.data.next_cursor;
  }
}

function block(content, tag) {
  const m = (content ?? "").match(new RegExp("```json " + tag + "\\n([\\s\\S]*?)\\n```"));
  if (!m) return { missing: true };
  try { return { data: JSON.parse(m[1]) }; } catch (e) { return { error: e.message }; }
}

const nonEmpty = v => typeof v === "string" && v.trim().length > 0;

// Errors reject a result; warnings go in the pull request for the reviewer.
function checkResult(r, post, { projects, claimIds }) {
  const errors = [], warnings = [];
  if (!claimIds.has(r.claim_id)) errors.push(`unknown claim id ${r.claim_id}`);
  const project = projects.get(r.claim_id) ?? (r.project && existsSync(join(ROOT, TESTS, r.project)) ? r.project : null);
  if (!project) errors.push(`no project for ${r.claim_id}`);
  else if (r.project && r.project !== project) warnings.push(`project given as ${r.project}, filed under ${project}`);
  for (const k of ["hypothesis", "pass_criterion", "fail_criterion", "method"]) if (!nonEmpty(r[k])) errors.push(`missing ${k}`);
  if (!VERDICTS.includes(r.verdict)) errors.push(`verdict must be one of ${VERDICTS.join(", ")}`);
  if (r.verdict === "inconclusive" && !REASONS.includes(r.reason)) errors.push(`inconclusive needs reason: ${REASONS.join(", ")}`);
  if (!(typeof r.confidence === "number" && r.confidence >= 0 && r.confidence <= 1)) errors.push("confidence must be a number in [0, 1]");
  if (!DATA_KINDS.includes(r.data_kind)) errors.push(`data_kind must be one of ${DATA_KINDS.join(", ")} (posted before delphi_log_test_result had dataKind? ask the agent to re-post)`);
  if (r.measured == null || !("value" in r.measured)) errors.push("missing measured.value");
  if (r.data_kind !== "none") {
    const files = (r.datasets ?? []).flatMap(d => d.files ?? []);
    if (!r.datasets?.length) errors.push("no datasets");
    else if (!files.length) errors.push("datasets list no files: each needs download_url and sha256");
    for (const f of files) {
      if (!/^https?:\/\//.test(f.download_url ?? "")) errors.push(`file without an http(s) download_url: ${JSON.stringify(f.download_url)}`);
      if (!/^[0-9a-f]{64}$/i.test(f.sha256 ?? "")) errors.push(`file without a SHA-256: ${f.download_url}`);
    }
    if (!/^https?:\/\//.test(r.code_url ?? "")) errors.push("no code_url: measured values must come from a runnable script");
  }
  if (!r.preregistration) warnings.push("criteria not linked to a pre-registration; filed with preregistered: false");
  if (!r.test_contract) warnings.push("no test_contract (required for new tests)");
  if (r.agent?.forum && r.agent.forum !== post.author) warnings.push(`block names agent ${r.agent.forum}, post is by ${post.author}; credited to ${post.author}`);
  if (r.also_bears_on?.length) warnings.push(`also bears on ${r.also_bears_on.join(", ")}; only ${r.claim_id} gets a result file`);
  if (project && existsSync(join(ROOT, TESTS, project, r.claim_id, "result.json"))) warnings.push(`${r.claim_id} already has a top-level result, which stays its verdict`);
  return { errors: [...new Set(errors)], warnings, project };
}

function checkProposal(p, { labels }) {
  const errors = [], warnings = [];
  if (!nonEmpty(p.label)) errors.push("missing label");
  if (!nonEmpty(p.claim) || p.claim.length < 20) errors.push("missing or too-short claim statement");
  if (!nonEmpty(p.source?.title)) errors.push("missing source.title");
  if (!p.source?.doi && !p.source?.url) errors.push("source needs a DOI or URL");
  if (!CLAIM_KINDS.includes(p.claim_kind)) errors.push(`claim_kind must be one of ${CLAIM_KINDS.join(", ")}`);
  if (!p.quote) warnings.push("no verbatim quote from the source");
  if (labels.has(String(p.label).trim().toLowerCase())) warnings.push("an existing claim has the same label");
  return { errors, warnings };
}

async function main() {
  const projects = claimProjects();
  const claims = readJson(join(ROOT, "docs/claims.json")).claims;
  const claimIds = new Set(claims.map(c => c.id));
  const labels = new Set(claims.map(c => String(c.label).trim().toLowerCase()));
  const seen = harvested();
  const since = opt("since"), only = opt("post");
  const keep = p => (!only || p.id === only || p.id.startsWith(only)) && (!since || p.created_at >= since);

  const [results, artifacts] = await Promise.all([forumPosts({ kind: "result" }), forumPosts({ kind: "artifact", lab: "claims" })]);
  const today = new Date().toISOString();
  const report = [];

  for (const post of results.filter(keep)) {
    const entry = { post: post.id, url: postUrl(post.id), author: post.author, kind: "result", title: post.title };
    report.push(entry);
    if (seen.has(post.id)) { Object.assign(entry, { status: "already harvested", path: seen.get(post.id) }); continue; }
    const b = block(post.content, "delphi:test-result");
    if (b.missing) { Object.assign(entry, { status: "skipped", errors: ["no delphi:test-result block (not posted with delphi_log_test_result)"] }); continue; }
    if (b.error) { Object.assign(entry, { status: "rejected", errors: [`malformed block: ${b.error}`] }); continue; }
    const { errors, warnings, project } = checkResult(b.data, post, { projects, claimIds });
    Object.assign(entry, { claim: b.data.claim_id, verdict: b.data.verdict, dataKind: b.data.data_kind, warnings });
    if (errors.length) { Object.assign(entry, { status: "rejected", errors }); continue; }
    const result = {
      ...b.data, project, status: "complete",
      ...(b.data.preregistration ? {} : { preregistered: false }),
      agent: { kind: "forum-agent", forum: post.author, date: post.created_at.slice(0, 10) },
      forum: { post: post.id, url: postUrl(post.id), author: post.author, posted_at: post.created_at, harvested_at: today },
    };
    Object.assign(entry, { status: "accepted", path: join(TESTS, project, result.claim_id, `forum-${short(post.id)}`, "result.json"), file: result });
  }

  for (const post of artifacts.filter(p => p.artifact_type === "claim").filter(keep)) {
    const entry = { post: post.id, url: postUrl(post.id), author: post.author, kind: "proposal", title: post.title };
    report.push(entry);
    if (seen.has(post.id)) { Object.assign(entry, { status: "already harvested", path: seen.get(post.id) }); continue; }
    const b = block(post.content, "delphi:claim-proposal");
    if (b.missing) { Object.assign(entry, { status: "skipped", errors: ["no delphi:claim-proposal block (not posted with delphi_propose_claim)"] }); continue; }
    if (b.error) { Object.assign(entry, { status: "rejected", errors: [`malformed block: ${b.error}`] }); continue; }
    const { errors, warnings } = checkProposal(b.data, { labels });
    Object.assign(entry, { warnings });
    if (errors.length) { Object.assign(entry, { status: "rejected", errors }); continue; }
    const file = { ...b.data, status: "proposed", forum: { post: post.id, url: postUrl(post.id), author: post.author, posted_at: post.created_at, harvested_at: today } };
    Object.assign(entry, { status: "accepted", path: join(INBOX, `${short(post.id)}.json`), file });
  }

  const accepted = report.filter(e => e.status === "accepted");
  if (flag("json")) console.log(JSON.stringify(report.map(({ file, ...e }) => e), null, 2));
  else printReport(report);
  if (!WRITE || !accepted.length) {
    if (!WRITE && accepted.length) console.log(`\nDry run. --write puts the ${accepted.length} accepted file(s) in this checkout; --pr opens a pull request.`);
    return;
  }

  let root = ROOT, worktree, branch;
  if (PR) {
    execFileSync("git", ["fetch", "-q", "origin", "main"], { cwd: ROOT });
    branch = `forum-harvest/${today.slice(0, 10)}-${short(accepted[0].post)}`;
    worktree = mkdtempSync(join(tmpdir(), "forum-harvest-"));
    execFileSync("git", ["worktree", "add", "-q", "-b", branch, worktree, "origin/main"], { cwd: ROOT });
    root = worktree;
  }
  try {
    const base = root;
    for (const e of accepted) {
      mkdirSync(dirname(join(base, e.path)), { recursive: true });
      writeFileSync(join(base, e.path), JSON.stringify(e.file, null, 2) + "\n");
      console.log(`wrote ${e.path}`);
    }
    if (!PR) return;
    const git = (...a) => execFileSync("git", a, { cwd: root, encoding: "utf8" });
    git("add", ...accepted.map(e => e.path));
    const tests = accepted.filter(e => e.kind === "result").length, props = accepted.length - tests;
    const title = `Forum harvest: ${[tests && `${tests} test result${tests > 1 ? "s" : ""}`, props && `${props} claim proposal${props > 1 ? "s" : ""}`].filter(Boolean).join(", ")}`;
    git("commit", "-q", "-m", title, "-m", accepted.map(e => `${e.kind} ${e.post} by ${e.author}: ${e.path}`).join("\n"));
    git("push", "-q", "-u", "origin", branch);
    const pr = execFileSync("gh", ["pr", "create", "--base", "main", "--head", branch, "--title", title, "--body", prBody(accepted, report)], { cwd: root, encoding: "utf8" }).trim();
    console.log(`opened ${pr}`);
  } finally {
    if (worktree) { execFileSync("git", ["worktree", "remove", "--force", worktree], { cwd: ROOT }); rmSync(worktree, { recursive: true, force: true }); }
  }
}

function printReport(report) {
  const by = s => report.filter(e => e.status === s);
  console.log(`Forum ${FORUM}: ${report.length} post(s) with results or proposals. accepted ${by("accepted").length}, rejected ${by("rejected").length}, skipped ${by("skipped").length}, already harvested ${by("already harvested").length}.`);
  for (const e of report) {
    if (e.status === "already harvested") continue;
    console.log(`\n[${e.status}] ${e.kind} by ${e.author}: ${e.title}\n  ${e.url}${e.path ? `\n  -> ${e.path}` : ""}`);
    for (const x of e.errors ?? []) console.log(`  error: ${x}`);
    for (const x of e.warnings ?? []) console.log(`  warning: ${x}`);
  }
}

function prBody(accepted, report) {
  const rows = accepted.map(e => `| [${e.kind}](${e.url}) | ${e.author} | ${e.claim ?? e.file.label} | ${e.verdict ? `${e.verdict} (${e.dataKind})` : "proposed"} | \`${e.path}\` |`);
  const notes = accepted.filter(e => e.warnings?.length).map(e => `- [${e.title}](${e.url}): ${e.warnings.join("; ")}`);
  const rejected = report.filter(e => e.status === "rejected").map(e => `- [${e.title}](${e.url}) by ${e.author}: ${e.errors.join("; ")}`);
  return [
    "Harvested from the Science Claw forum by `node scripts/forum/harvest.mjs --pr`. Each file records its post in `forum`; test results credit the poster in `agent.forum`, which the forum leaderboard counts as merged.",
    "",
    "| Post | Agent | Claim | Verdict | File |", "|---|---|---|---|---|", ...rows,
    "",
    "Before merging, check each test against test-data/claim-tests/README.md: the criteria really were fixed before the data were seen, the datasets and checksums are real, and the linked code reproduces `measured`. Proposals go from `claim-sources/forum-proposals/inbox/` into a project's claims.json once assessed.",
    ...(notes.length ? ["", "**Warnings**", ...notes] : []),
    ...(rejected.length ? ["", "**Rejected (not included)**", ...rejected] : []),
    "",
    "Then run `node scripts/site/build-claim-graph.mjs`so docs/claims.json and SUMMARY.md pick the tests up.",
  ].join("\n");
}

main().catch(e => { console.error(e.message); process.exit(1); });
