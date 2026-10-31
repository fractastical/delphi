#!/usr/bin/env node
// Where every record stands: for each project and record type, how many exist, are built as
// nanopubs, signed, on the test registry, on production, uncommitted, and missing from origin/main.
// Also checks that docs/claims.json matches what scripts/site/load-claims.mjs builds from the repo now.
//
//   npm run status [-- --json] [-- --no-fetch]
import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { basename, dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { loadClaims } from "../site/load-claims.mjs";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "../..");
const json = process.argv.includes("--json");
const git = (...args) => execFileSync("git", args, { cwd: ROOT, encoding: "utf8", maxBuffer: 1 << 28 });
const ls = (dir, re = /./) => { try { return readdirSync(dir).filter(f => re.test(f)).sort(); } catch { return []; } };
const isDir = p => existsSync(p) && statSync(p).isDirectory();
const readJson = p => JSON.parse(readFileSync(p, "utf8"));

if (!process.argv.includes("--no-fetch")) { try { git("fetch", "-q", "origin", "main"); } catch { /* offline: compare with the last fetch */ } }

// Git state of every path: uncommitted (untracked or modified) and blob on origin/main.
const dirty = new Set(git("status", "--porcelain", "--untracked-files=all", "-z").split("\0").filter(Boolean).map(l => l.slice(3)));
const onMain = new Map(git("ls-tree", "-r", "-z", "origin/main").split("\0").filter(Boolean)
  .map(l => { const [meta, path] = l.split("\t"); return [path, meta.split(" ")[2]]; }));
const head = new Map(git("ls-tree", "-r", "-z", "HEAD").split("\0").filter(Boolean)
  .map(l => { const [meta, path] = l.split("\t"); return [path, meta.split(" ")[2]]; }));
const gitState = paths => ({
  uncommitted: paths.filter(p => dirty.has(p)).length,
  notOnMain: paths.filter(p => dirty.has(p) || !onMain.has(p) || onMain.get(p) !== head.get(p)).length,
});

// Publication records, normalised to { file: "<dir>/<name>.trig", registry: "test" | "production" }.
function manifest(npDir) {
  const out = [];
  const jsonl = join(npDir, "manifest.jsonl");
  if (existsSync(jsonl)) for (const l of readFileSync(jsonl, "utf8").split("\n").filter(Boolean)) {
    const m = JSON.parse(l);
    out.push({ file: m.file, registry: m.registry });
  }
  const legacy = join(npDir, "manifest.json");
  if (existsSync(legacy)) for (const m of readJson(legacy).nanopubs ?? []) {
    const file = m.file.replace(/^nanopubs\//, "");
    if (m.trustyUri) out.push({ file, registry: "test" });
    if (m.productionRegistry) out.push({ file, registry: "production" });
  }
  return out;
}

const projects = ls(join(ROOT, "claim-sources")).map(d => join(ROOT, "claim-sources", d))
  .filter(p => isDir(p) && !basename(p).startsWith("."));

const rows = [];
for (const project of projects) {
  const name = relative(ROOT, project);
  const npDir = join(project, "nanopubs");
  const published = manifest(npDir);
  const on = (file, reg) => published.some(m => m.file === file && m.registry === reg);
  for (const dir of ls(npDir).filter(d => (d === "unsigned" || d.endsWith("-unsigned")) && isDir(join(npDir, d)))) {
    const files = ls(join(npDir, dir), /\.trig$/);
    const signedDirs = [dir.replace(/unsigned$/, "signed"), ...(dir === "unsigned" ? ["signed-test"] : [])].map(d => join(npDir, d));
    rows.push({
      project: name, kind: dir === "unsigned" ? "claims" : dir.replace(/-unsigned$/, ""),
      records: files.length, built: files.length,
      signed: files.filter(f => signedDirs.some(d => existsSync(join(d, f)))).length,
      test: files.filter(f => on(`${dir}/${f}`, "test")).length,
      production: files.filter(f => on(`${dir}/${f}`, "production")).length,
      ...gitState(files.map(f => relative(ROOT, join(npDir, dir, f)))),
    });
  }
  // Lean proofs: `formalized` entries in lean/reports. None is a nanopub yet.
  const reports = ls(join(project, "lean/reports"), /\.json$/).map(f => join(project, "lean/reports", f));
  if (reports.length) rows.push({
    project: name, kind: "lean proofs",
    records: reports.flatMap(f => readJson(f)).filter(r => r.status === "formalized").length,
    built: 0, signed: 0, test: 0, production: 0, ...gitState(reports.map(f => relative(ROOT, f))),
  });
  // Data tests: complete results in test-data/claim-tests/<project>/, built into test-data/claim-tests/nanopubs/unsigned/<id>.trig.
  const testDir = join(ROOT, "test-data/claim-tests", basename(project));
  if (isDir(testDir)) {
    const results = ls(testDir).map(id => join(testDir, id, "result.json")).filter(existsSync);
    const complete = results.filter(f => readJson(f).status === "complete");
    const built = complete.map(f => join(ROOT, "test-data/claim-tests/nanopubs/unsigned", `${readJson(f).claim_id}.trig`)).filter(existsSync);
    rows.push({
      project: name, kind: "data tests", records: complete.length, built: built.length,
      signed: 0, test: 0, production: 0, preregistered: results.length - complete.length,
      ...gitState([...results, ...built].map(f => relative(ROOT, f))),
    });
  }
}

// docs/claims.json against a fresh build from the repo.
const committed = readJson(join(ROOT, "docs/claims.json"));
const fresh = new Map(loadClaims().map(c => [c.id, c]));
const was = new Map(committed.claims.map(c => [c.id, c]));
const drift = { added: [...fresh.keys()].filter(id => !was.has(id)).length, removed: [...was.keys()].filter(id => !fresh.has(id)).length, changed: 0 };
for (const [id, c] of fresh) {
  const o = was.get(id);
  if (o && (o.verification !== c.verification || (o.evidence ?? null) !== (c.evidence ?? null)
    || (o.registry ?? null) !== (c.registry || null) || o.data_test?.confidence !== c.dataTest?.confidence)) drift.changed++;
}
const derived = {
  file: "docs/claims.json", built: committed.built, ...drift,
  stale: drift.added + drift.removed + drift.changed > 0, ...gitState(["docs/claims.json"]),
};
// The number the project exists to raise: math claims shown to hold in organisms.
const math = [...fresh.values()].filter(c => c.math);
const evidence = {
  math: math.length,
  supportedInOrganisms: math.filter(c => c.evidenceKind === "biological" && c.evidence === "supports").length,
  testedOnOrganisms: math.filter(c => c.evidenceKind === "biological").length,
  testedOtherwise: math.filter(c => c.evidence && c.evidenceKind !== "biological").length,
};

const gaps = rows.flatMap(r => {
  const g = [];
  if (r.built < r.records) g.push(`${r.records - r.built} not built as nanopubs`);
  else if (r.production < r.built) g.push(r.test < r.built ? `${r.built - r.test} not on test` : `${r.built - r.production} on test only`);
  if (r.preregistered) g.push(`${r.preregistered} pre-registered, not yet run`);
  if (r.notOnMain) g.push(`${r.notOnMain} files not on origin/main${r.uncommitted ? ` (${r.uncommitted} uncommitted)` : ""}`);
  return g.length ? [`${r.project} ${r.kind}: ${g.join("; ")}`] : [];
});
if (derived.stale) gaps.push(`docs/claims.json is stale: ${drift.added} claims added, ${drift.removed} removed, ${drift.changed} changed status since ${derived.built}`);
else if (derived.notOnMain) gaps.push("docs/claims.json is current but not on origin/main");

if (json) {
  console.log(JSON.stringify({ evidence, rows, derived, gaps }, null, 2));
} else {
  const cols = ["project", "kind", "records", "built", "signed", "test", "production", "uncommitted", "notOnMain"];
  const head = ["Project", "Record", "Records", "Built", "Signed", "Test", "Production", "Uncommitted", "Not on main"];
  const cell = (r, c) => (typeof r[c] === "number" && c !== "records" && r[c] < r.records ? `${r[c]} !` : String(r[c] ?? ""));
  console.log(`| ${head.join(" | ")} |\n|${head.map((_, i) => (i < 2 ? "---|" : "---:|")).join("")}`);
  for (const r of rows) console.log(`| ${cols.map(c => (c === "uncommitted" || c === "notOnMain" ? String(r[c] || "·") : cell(r, c))).join(" | ")} |`);
  console.log(`\nMath in biology: ${evidence.supportedInOrganisms} of ${evidence.math} math claims supported by data measured on organisms; ${evidence.testedOnOrganisms} tested on organisms, ${evidence.testedOtherwise} tested only on simulation, mathematics or physical data.`);
  console.log(`\n${derived.file}: built ${derived.built}, ${derived.stale ? "STALE" : "current"}${derived.notOnMain ? ", not on origin/main" : ""}`);
  console.log(gaps.length ? `\nGaps:\n${gaps.map(g => `- ${g}`).join("\n")}` : "\nNo gaps.");
}
