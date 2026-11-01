// Sign problems/nanopubs/unsigned/*.trig with the operator's key, lint the signed batch with the
// upstream pipeline linter, and publish to the TEST registry (or, with --registry production and
// only for files already on test, promote). Records every publication in nanopubs/manifest.json.
// BEST_PRACTICES.md sections 2-4 and 8.
//
//   DELPHI_PIPELINE=/path/to/project-delphi-ontology/pipeline \
//   node problems/build/publish.mjs --registry test [--dry-run]
import { readFileSync, writeFileSync, mkdirSync, readdirSync, rmSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { execSync, spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(HERE, "..");
const pipeline = process.env.DELPHI_PIPELINE;
if (!pipeline) throw new Error("Set DELPHI_PIPELINE to a checkout of project-delphi-ontology/pipeline (with npm install done)");
const { Nanopub } = await import(pathToFileURL(join(REPO, "claim-sources/darwin-origin/node_modules/@nanopub/nanopub-js/dist/node.js")).href);

const arg = (name, dflt) => { const i = process.argv.indexOf(name); return i > -1 ? process.argv[i + 1] : dflt; };
const REGISTRIES = { test: "https://test.registry.knowledgepixels.com/", production: "https://registry.knowledgepixels.com/" };
const registry = arg("--registry");
if (!REGISTRIES[registry]) throw new Error("--registry must be test or production");
const dryRun = process.argv.includes("--dry-run");
if (registry === "production" && !process.env.PROMOTE_APPROVED_BY) throw new Error("Promotion needs PROMOTE_APPROVED_BY=<ORCID of the human who reviewed the batch on test>");

const profile = readFileSync(join(homedir(), ".nanopub/profile.yml"), "utf8");
const orcid = profile.match(/^orcid_id:\s*(\S+)/m)?.[1];
const name = profile.match(/^name:\s*(.+)$/m)?.[1]?.trim();
const privateKey = readFileSync(join(homedir(), ".nanopub/id_rsa"), "utf8").replace(/\s+/g, "");
if (!orcid || !name) throw new Error("~/.nanopub/profile.yml has no orcid_id or name");

const commit = execSync("git rev-parse HEAD", { cwd: REPO, encoding: "utf8" }).trim();
// The nanopubs link to problems.json, approaches/*.json and INSTRUCTIONS.md at the generator
// commit, so those must be committed (and pushed) before signing. The build outputs under
// nanopubs/ are committed together with the publication (BEST_PRACTICES.md section 3).
const dirty = execSync("git status --porcelain -- problems/problems.json problems/approaches problems/build problems/dropped-links.json", { cwd: REPO, encoding: "utf8" }).trim();
if (dirty && !dryRun) throw new Error(`problem sources have uncommitted changes; commit and push before signing so the commit-pinned links resolve:\n${dirty}`);
const generatorCommits = new Set(JSON.parse(readFileSync(join(HERE, "nanopubs/manifest.json"), "utf8")).nanopubs.filter(m => !m.trustyUri).map(m => m.generatorCommit));
if (!dryRun && (generatorCommits.size > 1 || (generatorCommits.size === 1 && !generatorCommits.has(commit)))) throw new Error(`unsigned nanopubs were built at ${[...generatorCommits].join(", ")} but HEAD is ${commit}; rebuild so the pinned links match`);
const lintCommit = execSync("git rev-parse HEAD", { cwd: pipeline, encoding: "utf8" }).trim();

const unsignedDir = join(HERE, "nanopubs/unsigned");
const signedDir = join(HERE, "nanopubs", registry === "test" ? "signed-test" : "signed-production");
mkdirSync(signedDir, { recursive: true });
const manifestPath = join(HERE, "nanopubs/manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const entryFor = file => manifest.nanopubs.find(m => m.file === `nanopubs/unsigned/${file}`);

// Sign (or, for promotion, re-read the signed test file so the trusty URI is the same).
const batch = [];
for (const file of readdirSync(unsignedDir).filter(f => f.endsWith(".trig")).sort()) {
  const entry = entryFor(file);
  if (!entry) throw new Error(`${file} is not in the manifest; run build-nanopubs.mjs`);
  if (registry === "test") {
    if (entry.trustyUri) continue;
    const np = Nanopub.fromRdf(readFileSync(join(unsignedDir, file), "utf8"), "trig", { privateKey, orcid, name });
    await np.sign({ keyCheck: "strict" });
    if (!(await np.hasValidSignature())) throw new Error(`${file}: signature does not verify`);
    batch.push({ file, np, entry });
  } else {
    if (!entry.trustyUri || !entry.signedFile) throw new Error(`${file}: never published to test; refusing production`);
    if (entry.productionPublishedAt) continue;
    if (entry.generatorCommit !== JSON.parse(readFileSync(manifestPath, "utf8")).nanopubs.find(m => m.file === entry.file).generatorCommit) throw new Error(`${file}: generator commit changed since test`);
    const np = Nanopub.fromRdf(readFileSync(join(REPO, "problems", entry.signedFile), "utf8"), "trig", { privateKey, orcid, name });
    if (!(await np.hasValidSignature())) throw new Error(`${file}: signed test file does not verify`);
    batch.push({ file, np, entry });
  }
}
if (!batch.length) { console.log("nothing to publish"); process.exit(0); }

// Lint the signed batch with the upstream linter. Problems and approaches are not delphi:Claim,
// so the dataset rule does not apply; dummy-data and count rules do.
const lintDir = join(tmpdir(), `delphi-problems-lint-${process.pid}`);
mkdirSync(lintDir, { recursive: true });
for (const b of batch) writeFileSync(join(lintDir, b.file), b.np.rdf());
const lint = spawnSync("npx", ["tsx", "lint.ts", lintDir], { cwd: pipeline, encoding: "utf8" });
rmSync(lintDir, { recursive: true, force: true });
if (lint.status !== 0) throw new Error(`lint findings on the signed batch; nothing published:\n${lint.stdout}${lint.stderr}`);
console.log(`lint: ${lint.stdout.trim().split("\n").pop()} (linter ${lintCommit.slice(0, 8)})`);

let published = 0;
for (const { file, np, entry } of batch) {
  const uri = np.sourceUri;
  if (!/^https:\/\/w3id\.org\/np\/RA[A-Za-z0-9_-]{43}$/.test(uri)) throw new Error(`${file}: unexpected URI ${uri}`);
  if (dryRun) { console.log(`${file} -> ${uri} (dry run)`); continue; }
  if (registry === "test") writeFileSync(join(signedDir, file), np.rdf());
  const res = await np.publish(REGISTRIES[registry], { keyCheck: "strict" });
  if (!res.response.ok) {
    writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
    throw new Error(`${file}: registry answered ${res.response.status} ${await res.response.text()}; manifest saved with ${published} publications`);
  }
  if (registry === "test") Object.assign(entry, { signedFile: `nanopubs/signed-test/${file}`, trustyUri: uri, registry: REGISTRIES.test, publishedAt: new Date().toISOString(), signer: orcid, signCommit: commit, lintCommit });
  else Object.assign(entry, { productionRegistry: REGISTRIES.production, productionPublishedAt: new Date().toISOString(), promotionApprovedBy: process.env.PROMOTE_APPROVED_BY, productionLintCommit: lintCommit });
  console.log(`${file} -> ${uri}`);
  published++;
}
if (!dryRun) {
  const all = manifest.nanopubs;
  manifest.status = all.every(m => m.productionPublishedAt) ? "published to production (promoted from test)"
    : all.every(m => m.trustyUri) ? "published to the test registry; not promoted to production"
    : "partly published to the test registry; not promoted to production";
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
}
console.log(`${batch.length} in batch; ${dryRun ? "dry run, nothing published" : `${published} published to ${registry}`}`);
