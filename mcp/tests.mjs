// Tests of claims against data: every result.json under test-data/claim-tests/, joined to the claim
// labels and testability scores in docs/claims.json. The same counts as test-data/claim-tests/SUMMARY.md.

import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { REPO } from "./lib.mjs";
import { CLAIMS_JSON } from "./graph.mjs";

const TESTS = join(REPO, "test-data/claim-tests");
const GITHUB = "https://github.com/fractastical/delphi/blob/main";
export const VERDICTS = ["supports", "mixed", "refutes", "inconclusive"];
export const DATA_KINDS = ["biological", "physical", "computational", "none"];
export const TEST_VIEWS = ["summary", "list", "claim", "candidates"];

let cache = null;

// Every run, newest file state; a claim's top-level result.json is its headline run.
function load() {
  // Results land deep in the tree, where directory mtimes don't change; rescan at most every 30 s.
  const stamp = `${Math.floor(Date.now() / 30000)}:${statSync(CLAIMS_JSON).mtimeMs}`;
  if (cache?.stamp === stamp) return cache;
  const runs = [];
  const walk = dir => {
    for (const f of readdirSync(dir, { withFileTypes: true })) {
      const p = join(dir, f.name);
      if (f.isDirectory() && !["derived", "data", "nanopubs", "__pycache__", "node_modules"].includes(f.name)) walk(p);
      else if (f.name === "result.json") {
        try {
          const r = JSON.parse(readFileSync(p, "utf8"));
          const path = relative(REPO, p);
          runs.push({ ...r, path, headline: path.split("/").length === 5 });
        } catch {}
      }
    }
  };
  if (existsSync(TESTS)) walk(TESTS);
  const claims = JSON.parse(readFileSync(CLAIMS_JSON, "utf8")).claims;
  const byId = Object.fromEntries(claims.map(c => [c.id, c]));
  cache = { stamp, runs, claims, byId, built: JSON.parse(readFileSync(CLAIMS_JSON, "utf8")).built };
  return cache;
}

// "Claude Fable 5.1 (Cursor cloud agent)", "claude-fable-5-1-thinking-high" -> "claude-fable-5.1".
const canonicalModel = m => (m ? String(m).toLowerCase().replace(/\(.*?\)/g, "").trim().replace(/\s+/g, "-")
  .replace(/-thinking(-\w+)?$/, "").replace(/(\d)-(\d)/g, "$1.$2") : "unknown");

// Who produced the completed tests in the repo, from each result.json's `agent`: by forum name when
// the test came through the forum (agent.forum), otherwise by model.
export function testContributors() {
  const { runs } = load();
  const by = new Map();
  for (const r of runs.filter(r => r.status === "complete")) {
    const a = r.agent ?? {};
    const key = a.forum ? `forum:${a.forum}` : `model:${canonicalModel(a.model)}`;
    const c = by.get(key) ?? by.set(key, { forum: a.forum ?? null, model: a.forum ? null : canonicalModel(a.model), runs: 0, claims: new Set(), sessions: new Set(),
      ...Object.fromEntries(VERDICTS.map(v => [v, 0])), onOrganisms: 0 }).get(key);
    c.runs++;
    c.claims.add(r.claim_id);
    if (a.run) c.sessions.add(a.run);
    if (r.verdict in c) c[r.verdict]++;
    if (r.data_kind === "biological") c.onOrganisms++;
  }
  return [...by.values()].map(c => ({ ...c, claims: c.claims.size, sessions: c.sessions.size }))
    .sort((x, y) => y.claims - x.claims || y.runs - x.runs);
}

const has = (v, needle) => String(v ?? "").toLowerCase().includes(needle.toLowerCase());
const row = (r, byId) => ({
  claim: r.claim_id, title: byId[r.claim_id]?.label, thinker: byId[r.claim_id]?.thinker, project: r.project,
  status: r.status, verdict: r.verdict ?? null, confidence: r.confidence ?? null, dataKind: r.data_kind ?? null,
  preregistered: r.preregistered !== false, math: byId[r.claim_id]?.math ?? null,
  hypothesis: r.hypothesis, path: r.path, url: `${GITHUB}/${r.path}`,
});

// Completed tests counted once per claim, as in docs/claims.json: the claim's `evidence` field.
function summary() {
  const { runs, claims, built } = load();
  const tested = claims.filter(c => c.evidence);
  const pending = runs.filter(r => r.status === "preregistered");
  const thinkers = [...new Set(tested.map(c => c.thinker))];
  const n = (cs, f) => cs.filter(f).length;
  const tally = cs => ({ tested: cs.length, ...Object.fromEntries(VERDICTS.map(v => [v, n(cs, c => c.evidence === v)])),
    ...Object.fromEntries(DATA_KINDS.map(k => [k, n(cs, c => c.evidence_kind === k)])),
    mathTested: n(cs, c => c.math), mathSupportedInOrganisms: n(cs, c => c.math && c.evidence === "supports" && c.evidence_kind === "biological") });
  const rows = thinkers.map(t => ({ thinker: t, ...tally(tested.filter(c => c.thinker === t)) }));
  const total = { ...tally(tested), completedRuns: n(runs, r => r.status === "complete"), preregistered: pending.length,
    untestedWithTestability: n(claims, c => !c.evidence && c.testability != null) };
  const cell = v => (v ? String(v) : "·");
  const line = (name, r) => `| ${name} | ${r.tested} | ${VERDICTS.map(v => cell(r[v])).join(" | ")} | ${DATA_KINDS.map(k => cell(r[k])).join(" | ")} | ${cell(r.mathTested)} |`;
  const markdown = [
    `**${total.tested} claims tested against data** (${VERDICTS.map(v => `${total[v]} ${v}`).join(", ")}), from ${total.completedRuns} completed runs; ` +
      `${total.biological} tested on organisms. ${total.preregistered} tests pre-registered and awaiting data. ` +
      `${total.mathSupportedInOrganisms} math claims supported by organism data. Claims built ${built}.`,
    "",
    `| Thinker | Tested | ${VERDICTS.join(" | ")} | ${DATA_KINDS.join(" | ")} | math |`,
    `|---|${"---:|".repeat(1 + VERDICTS.length + DATA_KINDS.length + 1)}`,
    ...rows.map(r => line(r.thinker, r)),
    line("**All**", total),
    "",
    "A claim with several runs counts once. Only `biological` data shows a claim holds in organisms; `computational` shows it holds as mathematics. A data verdict never makes a claim a theorem.",
    `Next: view "list" with verdict/dataKind/thinker filters, view "claim" with an id for the full result.json, or view "candidates" for untested claims ranked by testability (${total.untestedWithTestability} of them).`,
  ].join("\n");
  return { markdown, built, total, thinkers: rows, pending: pending.map(r => row(r, load().byId)) };
}

function list({ thinker, project, verdict, dataKind, status = "complete", text, math, limit = 50 }) {
  const { runs, byId } = load();
  const hits = runs.filter(r =>
    (status === "any" || r.status === status)
    && (status !== "complete" || r.headline || !runs.some(o => o.claim_id === r.claim_id && o.headline && o.status === "complete"))
    && (!thinker || has(byId[r.claim_id]?.thinker, thinker))
    && (!project || has(r.project, project))
    && (!verdict || r.verdict === verdict)
    && (!dataKind || r.data_kind === dataKind)
    && (math == null || (byId[r.claim_id]?.math ?? false) === math)
    && (!text || has(`${r.claim_id} ${byId[r.claim_id]?.label ?? ""} ${r.hypothesis ?? ""}`, text)));
  hits.sort((a, b) => (b.confidence ?? -1) - (a.confidence ?? -1) || a.claim_id.localeCompare(b.claim_id));
  return { matched: hits.length, tests: hits.slice(0, Math.min(Number(limit) || 50, 500)).map(r => row(r, byId)) };
}

function claimTests({ id }) {
  if (!id) throw new Error('view "claim" needs id, e.g. "darwin1859-ch12-11"');
  const { runs, byId } = load();
  const short = id.replace(/^.*\//, "");
  const mine = runs.filter(r => r.claim_id === short);
  const c = byId[short];
  if (!mine.length) return { claim: short, title: c?.label ?? null, tests: [],
    note: c ? "No test yet. Its testability score is " + (c.testability ?? "unscored") + "; see test-data/claim-tests/README.md to add one." : "Unknown claim id." };
  return { claim: short, title: c?.label, statement: c?.statement, thinker: c?.thinker, evidence: c?.evidence ?? null,
    tests: mine.sort((a, b) => b.headline - a.headline).map(({ headline, ...r }) => ({ headline, url: `${GITHUB}/${r.path}`, ...r })) };
}

// Dataset scouting records (test-data/dataset-scouting/merged/scouting.json): where the data for an
// untested claim are, by claim id. Absent until the swarm has run and merge.mjs has been called.
const SCOUTING = join(REPO, "test-data/dataset-scouting/merged/scouting.json");
let scoutCache = null;
function scouting() {
  if (!existsSync(SCOUTING)) return {};
  const m = statSync(SCOUTING).mtimeMs;
  if (scoutCache?.m !== m) {
    try { scoutCache = { m, byId: Object.fromEntries(JSON.parse(readFileSync(SCOUTING, "utf8")).claims.map(c => [c.id, c])) }; }
    catch { scoutCache = { m, byId: {} }; }
  }
  return scoutCache.byId;
}
const SCOUT_ORDER = { "data-ready": 0, partial: 1, gap: 2, "not-empirically-resolvable": 3 };

// Untested claims (no completed or pre-registered run) ranked by testability: what to test next.
// `scouted` filters on the scouting status ("data-ready", "partial", "gap", "any", "none");
// sort "data" puts claims whose data has been located first.
function candidates({ thinker, math, minTestability = 0, text, scouted, sort, limit = 25 }) {
  const { runs, claims } = load();
  const taken = new Set(runs.map(r => r.claim_id));
  const scout = scouting();
  const hits = claims.filter(c => !c.evidence && !taken.has(c.id) && c.testability != null && c.testability >= minTestability
    && (!thinker || has(c.thinker, thinker)) && (math == null || c.math === math)
    && (!text || has(`${c.label} ${c.statement}`, text))
    && (!scouted || scouted === "any" ? true : scouted === "none" ? !scout[c.id] : scout[c.id]?.status === scouted));
  const rank = c => SCOUT_ORDER[scout[c.id]?.status] ?? 9;
  hits.sort((a, b) => (sort === "data" ? rank(a) - rank(b) : 0) || b.testability - a.testability);
  return { matched: hits.length, scouted: hits.filter(c => scout[c.id]).length,
    how: "Pre-register before looking at data: test-data/claim-tests/README.md. Log results with delphi_log_test_result or a pull request. `scouting` says where the data are (test-data/dataset-scouting/COVERAGE.md).",
    claims: hits.slice(0, Math.min(Number(limit) || 25, 500)).map(c => ({ id: c.id, title: c.label, thinker: c.thinker, kind: c.kind, math: c.math,
      testability: c.testability, truth: c.truth, statement: c.statement,
      scouting: scout[c.id] ? { status: scout[c.id].status, datasets: scout[c.id].datasets.filter(d => ["holds", "partial"].includes(d.verdict)).map(d => ({ name: d.name, verdict: d.verdict, url: d.access_url ?? d.landing_url })),
        summary: scout[c.id].summary, next_step: scout[c.id].next_step } : null })) };
}

export function claimTestsTool({ view, id, ...args } = {}) {
  const v = view ?? (id ? "claim" : Object.values(args).some(x => x != null) ? "list" : "summary");
  if (v === "summary") return summary();
  if (v === "list") return list(args);
  if (v === "claim") return claimTests({ id });
  if (v === "candidates") return candidates(args);
  throw new Error(`view must be one of ${TEST_VIEWS.join(", ")}`);
}
