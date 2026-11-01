#!/usr/bin/env node
// Build the scouting queue: untested claims ranked by testability, each joined to the datasets its
// dataset-resolvability assessors already named, so a scout starts from the models' guesses and
// confirms or rejects them against the live source.
//
//   node test-data/dataset-scouting/build-queue.mjs                                  # all untested claims -> queue.json
//   node test-data/dataset-scouting/build-queue.mjs --project thompson-growth-form --chapters 1-5 --min-testability 0.4 --out queue/thompson-ch01-05.json
//   node test-data/dataset-scouting/build-queue.mjs --ids thompson1917-ch02-06,darwin1859-ch05-06
//
// Needs docs/claims.json (node scripts/site/build-claim-graph.mjs). No dependencies (Node 20+).

import { existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO = resolve(HERE, "../..");
const SOURCES = join(REPO, "claim-sources");

// Claim id prefix -> claim-sources project directory.
export const PROJECT_OF = id =>
  id.startsWith("darwin1859-") ? "darwin-origin"
  : id.startsWith("thompson1917-") ? "thompson-growth-form"
  : id.startsWith("wolfram2002-") ? "wolfram-nks"
  : id.startsWith("levin-") ? "levin-papers"
  : id.startsWith("aristotle-") ? "aristotle-biology"
  : "math-bio-claims";

const camel = s => s.replace(/-([a-z])/g, (_, c) => c.toUpperCase());
const args = Object.fromEntries(process.argv.slice(2).map((a, i, arr) => a.startsWith("--") ? [camel(a.slice(2)), arr[i + 1]?.startsWith("--") || arr[i + 1] == null ? true : arr[i + 1]] : []).filter(x => x.length));

function readJsonLoose(path) {
  try { return JSON.parse(readFileSync(path, "utf8")); } catch (e) { console.error(`skipping ${path.slice(REPO.length + 1)}: ${e.message}`); return null; }
}

// All raw assessments, keyed by claim id, with the assessor's short name.
function loadAssessments() {
  const byClaim = new Map();
  if (!existsSync(SOURCES)) return byClaim;
  for (const project of readdirSync(SOURCES)) {
    const raw = join(SOURCES, project, "assessment", "raw");
    if (!existsSync(raw)) continue;
    for (const assessor of readdirSync(raw)) {
      const dir = join(raw, assessor);
      let files = [];
      try { files = readdirSync(dir).filter(f => f.endsWith(".json")); } catch { continue; }
      for (const f of files) {
        const d = readJsonLoose(join(dir, f));
        const list = Array.isArray(d) ? d : d?.assessments ?? [];
        for (const a of list) {
          if (!a?.claim_id) continue;
          if (!byClaim.has(a.claim_id)) byClaim.set(a.claim_id, []);
          byClaim.get(a.claim_id).push({ assessor, ...a });
        }
      }
    }
  }
  return byClaim;
}

const slug = s => String(s).toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "");

// Merge the assessors' candidate_datasets by normalised name: how many assessors named it, the URLs they gave, roles.
function mergeDatasets(assessments) {
  const out = new Map();
  for (const a of assessments) {
    for (const ds of a.candidate_datasets ?? []) {
      const name = typeof ds === "string" ? ds : ds?.name;
      if (!name) continue;
      const key = slug(name).replace(/-(database|db|the)$/g, "");
      if (!out.has(key)) out.set(key, { id: key, name, suggested_by: [], urls: [], roles: [] });
      const e = out.get(key);
      if (!e.suggested_by.includes(a.assessor)) e.suggested_by.push(a.assessor);
      if (ds?.url && !e.urls.includes(ds.url)) e.urls.push(ds.url);
      if (ds?.role && !e.roles.includes(ds.role)) e.roles.push(ds.role);
    }
  }
  return [...out.values()].sort((a, b) => b.suggested_by.length - a.suggested_by.length || a.name.localeCompare(b.name));
}

function chapterOf(id) {
  const m = id.match(/-ch(\d+)-/);
  return m ? Number(m[1]) : null;
}

export function buildQueue({ project, chapters, minTestability = 0, ids, thinker, limit } = {}) {
  const claimsPath = join(REPO, "docs/claims.json");
  if (!existsSync(claimsPath)) throw new Error("docs/claims.json missing; run node scripts/site/build-claim-graph.mjs");
  const { claims, built } = JSON.parse(readFileSync(claimsPath, "utf8"));
  const tested = new Set();
  const testsDir = join(REPO, "test-data/claim-tests");
  for (const p of existsSync(testsDir) ? readdirSync(testsDir) : []) {
    const pd = join(testsDir, p);
    try { for (const c of readdirSync(pd)) tested.add(c); } catch {}
  }
  const scouted = new Set();
  for (const p of readdirSync(HERE)) {
    const pd = join(HERE, p);
    if (["queue", "merged", "node_modules"].includes(p)) continue;
    try { for (const c of readdirSync(pd)) if (existsSync(join(pd, c, "datasets.json"))) scouted.add(c); } catch {}
  }
  const wanted = ids ? new Set(String(ids).split(",").map(s => s.trim())) : null;
  let [chLo, chHi] = chapters ? String(chapters).split("-").map(Number) : [null, null];
  if (chapters && chHi == null) chHi = chLo;
  const assessments = loadAssessments();

  const rows = claims
    .filter(c => !c.evidence && !tested.has(c.id) && c.testability != null)
    .filter(c => (wanted ? wanted.has(c.id) : true))
    .filter(c => !project || PROJECT_OF(c.id) === project)
    .filter(c => !thinker || String(c.thinker).toLowerCase().includes(String(thinker).toLowerCase()))
    .filter(c => chLo == null || (chapterOf(c.id) != null && chapterOf(c.id) >= chLo && chapterOf(c.id) <= chHi))
    .filter(c => c.testability >= Number(minTestability))
    .map(c => {
      const as = assessments.get(c.id) ?? [];
      return {
        id: c.id, project: PROJECT_OF(c.id), thinker: c.thinker, work: c.work, chapter: c.chapter ?? null,
        label: c.label, statement: c.statement, kind: c.kind, math: c.math,
        testability: c.testability, truth: c.truth, already_scouted: scouted.has(c.id),
        assessor_verdicts: Object.fromEntries(as.map(a => [a.assessor, a.verdict ?? null])),
        operationalizations: as.filter(a => a.operationalization).map(a => ({ assessor: a.assessor, text: a.operationalization })),
        obstacles: [...new Set(as.flatMap(a => a.obstacles ?? []))],
        candidate_datasets: mergeDatasets(as),
      };
    })
    .sort((a, b) => b.testability - a.testability);
  const out = limit ? rows.slice(0, Number(limit)) : rows;
  return { built_from: built, generated: new Date().toISOString().slice(0, 19) + "Z", filters: { project, chapters, minTestability, ids, thinker, limit },
    count: out.length, already_scouted: out.filter(r => r.already_scouted).length, claims: out };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const q = buildQueue(args);
  const out = resolve(HERE, args.out ?? "queue.json");
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, JSON.stringify(q, null, 2) + "\n");
  const byProject = {};
  for (const c of q.claims) byProject[c.project] = (byProject[c.project] ?? 0) + 1;
  const withDs = q.claims.filter(c => c.candidate_datasets.length).length;
  console.log(`${q.count} claims queued (${q.already_scouted} already scouted) -> ${out.slice(REPO.length + 1)}`);
  console.log(`by project: ${Object.entries(byProject).map(([k, v]) => `${k} ${v}`).join(", ")}`);
  console.log(`${withDs} have assessor-named datasets; ${q.claims.reduce((n, c) => n + c.candidate_datasets.length, 0)} distinct dataset suggestions in total`);
}
