#!/usr/bin/env node
// Builds exec/manifest.json: one entry per claim that has something runnable behind it.
//   kind "lean": a formalized entry in <project>/lean/reports/*.json; re-checked by compiling the
//                module and printing the axioms of each theorem.
//   kind "data": claim-tests/<project>/<claim-id>/ with an analysis script; re-checked by
//                re-running it and comparing its numbers with the committed result.json.
// Usage: node exec/build-manifest.mjs

import { createHash } from "node:crypto";
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = dirname(HERE);
const rel = (p) => relative(ROOT, p);
const readJson = (p) => JSON.parse(readFileSync(p, "utf8"));
const sha256 = (p) => createHash("sha256").update(readFileSync(p)).digest("hex");
const dirs = (p) => (existsSync(p) ? readdirSync(p).filter((d) => statSync(join(p, d)).isDirectory()).sort() : []);

const NETWORK = /\b(requests|urllib|urlopen|http\.client)\b/;
const overrides = readJson(join(HERE, "overrides.json"));

const known = new Map();
const claimsPath = join(ROOT, "docs", "claims.json");
if (existsSync(claimsPath)) for (const c of readJson(claimsPath).claims) known.set(c.id, c);

const entries = [];

for (const project of dirs(join(ROOT, "books"))) {
  const lean = join(ROOT, "books", project, "lean");
  const reports = join(lean, "reports");
  if (!existsSync(reports)) continue;
  const lib = readFileSync(join(lean, "lakefile.toml"), "utf8").match(/^name\s*=\s*"([^"]+)"/m)?.[1];
  for (const file of readdirSync(reports).filter((f) => f.endsWith(".json")).sort()) {
    const module = file.replace(/\.json$/, "");
    const source = join(lean, lib, `${module}.lean`);
    for (const r of readJson(join(reports, file))) {
      if (r.status !== "formalized") continue;
      entries.push({
        id: `lean:${r.claim_id}`,
        claim_id: r.claim_id,
        kind: "lean",
        project,
        module: `${lib}.${module}`,
        cwd: rel(lean),
        source: rel(source),
        source_sha256: existsSync(source) ? sha256(source) : null,
        cmd: ["lake", "env", "lean", rel(source).slice(rel(lean).length + 1)],
        theorems: r.lean_theorems ?? [],
        expects: { compiles: true, sorry: false, axioms: ["propext", "Classical.choice", "Quot.sound"] },
        report: rel(join(reports, file)),
      });
    }
  }
}

for (const project of dirs(join(ROOT, "claim-tests"))) {
  for (const claimId of dirs(join(ROOT, "claim-tests", project))) {
    const dir = join(ROOT, "claim-tests", project, claimId);
    const resultPath = join(dir, "result.json");
    if (!existsSync(resultPath)) continue;
    const result = readJson(resultPath);
    const key = rel(dir);
    const o = overrides[key] ?? {};
    const script = ["analysis.py", "analysis.mjs"].find((f) => existsSync(join(dir, f)));
    const fetch = existsSync(join(dir, "fetch.py")) ? "fetch.py" : null;
    const scriptText = script ? readFileSync(join(dir, script), "utf8") : "";

    let steps = o.steps ?? null;
    if (!steps && script) {
      steps = [];
      if (fetch && !/\bfetch\b/.test(scriptText)) steps.push({ cwd: key, script: fetch });
      steps.push({ cwd: key, script });
    }
    const scanned = [script, fetch].filter(Boolean).map((f) => readFileSync(join(dir, f), "utf8")).join("\n");

    entries.push({
      id: `data:${result.claim_id ?? claimId}`,
      claim_id: result.claim_id ?? claimId,
      kind: "data",
      project,
      dir: key,
      runnable: Boolean(steps?.length),
      ...(steps?.length ? {} : { why_not: o.why_not ?? (result.reason ? `no script; verdict ${result.verdict} (${result.reason})` : "no analysis script committed") }),
      steps: steps ?? [],
      network: o.network ?? NETWORK.test(scanned),
      timeout_s: o.timeout_s ?? 900,
      writes: o.writes ?? [`${key}/result.json`, `${key}/derived`],
      script_sha256: script ? sha256(join(dir, script)) : null,
      result_sha256: sha256(resultPath),
      expects: {
        status: result.status,
        verdict: result.verdict,
        value: result.measured?.value ?? null,
        n: result.measured?.n ?? null,
        unit: result.measured?.unit ?? null,
      },
    });
  }
}

for (const e of entries) {
  const c = known.get(e.claim_id);
  e.label = c?.label ?? null;
  if (!c) e.unknown_claim = true;
}
entries.sort((a, b) => a.id.localeCompare(b.id));

const count = (f) => entries.filter(f).length;
const manifest = {
  built: new Date().toISOString(),
  counts: {
    entries: entries.length,
    claims: new Set(entries.map((e) => e.claim_id)).size,
    lean: count((e) => e.kind === "lean"),
    data: count((e) => e.kind === "data"),
    data_runnable: count((e) => e.kind === "data" && e.runnable),
    data_offline: count((e) => e.kind === "data" && e.runnable && !e.network),
  },
  entries,
};
writeFileSync(join(HERE, "manifest.json"), JSON.stringify(manifest, null, 2) + "\n");
console.log(`exec/manifest.json: ${JSON.stringify(manifest.counts)}`);
const unknown = entries.filter((e) => e.unknown_claim).map((e) => e.claim_id);
if (unknown.length) console.log(`not in docs/claims.json: ${[...new Set(unknown)].join(", ")}`);
