// Sign every unsigned nanopub in a directory with the publisher's key and publish it.
// Same logic as claim-sources/darwin-origin/build/publish.mjs: deterministic signing, production
// refused for any URI never published to test, manifest appended per publication.
//
//   node scripts/release/self-assessment/build/publish.mjs --registry test --dir nanopubs/rubric-unsigned [--dry-run]
//   node scripts/release/self-assessment/build/publish.mjs --registry test --dir nanopubs/assessments-unsigned
import { readFileSync, writeFileSync, appendFileSync, mkdirSync, readdirSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { basename, dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const HERE = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(HERE, "../../..");
// The nanopub library is installed in the Darwin project; reuse it rather than add a second copy.
const { Nanopub } = await import(pathToFileURL(join(REPO, "claim-sources/darwin-origin/node_modules/@nanopub/nanopub-js/dist/node.js")).href);

const arg = (name, dflt) => { const i = process.argv.indexOf(name); return i > -1 ? process.argv[i + 1] : dflt; };
const REGISTRIES = { test: "https://test.registry.knowledgepixels.com/", production: "https://registry.knowledgepixels.com/" };
const registry = arg("--registry");
if (!REGISTRIES[registry]) throw new Error("--registry must be test or production");
const dir = join(HERE, arg("--dir", "nanopubs/assessments-unsigned"));
const signedDir = join(dir, "..", basename(dir).replace("unsigned", "signed"));
if (signedDir === dir) throw new Error("--dir must name an *unsigned* directory");
const dryRun = process.argv.includes("--dry-run");
const MANIFEST = join(HERE, "nanopubs/manifest.jsonl");

const profile = readFileSync(join(homedir(), ".nanopub/profile.yml"), "utf8");
const orcid = profile.match(/^orcid_id:\s*(\S+)/m)?.[1];
const name = profile.match(/^name:\s*(.+)$/m)?.[1]?.trim();
const privateKey = readFileSync(join(homedir(), ".nanopub/id_rsa"), "utf8").replace(/\s+/g, "");
if (!orcid || !name) throw new Error("~/.nanopub/profile.yml has no orcid_id or name");

const commit = execSync("git rev-parse HEAD", { cwd: REPO, encoding: "utf8" }).trim();
const manifest = existsSync(MANIFEST) ? readFileSync(MANIFEST, "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l)) : [];
const onTest = new Set(manifest.filter(m => m.registry === "test").map(m => m.trustyUri));
const already = new Set(manifest.filter(m => m.registry === registry).map(m => m.trustyUri));

mkdirSync(signedDir, { recursive: true });
const files = readdirSync(dir).filter(f => f.endsWith(".trig")).sort();
let published = 0, skipped = 0;
for (const f of files) {
  const np = Nanopub.fromRdf(readFileSync(join(dir, f), "utf8"), "trig", { privateKey, orcid, name });
  await np.sign({ keyCheck: "strict" });
  if (!(await np.hasValidSignature())) throw new Error(`${f}: signature does not verify`);
  const uri = np.sourceUri;
  if (!/^https:\/\/w3id\.org\/np\/RA[A-Za-z0-9_-]{43}$/.test(uri)) throw new Error(`${f}: unexpected URI ${uri}`);
  writeFileSync(join(signedDir, f), np.rdf());
  if (registry === "production" && !onTest.has(uri)) throw new Error(`${f}: ${uri} was never published to test; refusing production`);
  if (already.has(uri)) { skipped++; continue; }
  if (dryRun) { console.log(`${f} -> ${uri} (dry run)`); continue; }
  const res = await np.publish(REGISTRIES[registry], { keyCheck: "strict" });
  if (!res.response.ok) throw new Error(`${f}: registry answered ${res.response.status} ${await res.response.text()}`);
  appendFileSync(MANIFEST, JSON.stringify({ file: `${basename(dir)}/${f}`, id: f.replace(/\.trig$/, ""), trustyUri: uri, registry, publishedAt: new Date().toISOString(), generatorCommit: commit }) + "\n");
  console.log(`${f} -> ${uri}`);
  published++;
}
console.log(`${files.length} signed into ${signedDir}; ${dryRun ? "dry run, nothing published" : `${published} published to ${registry}, ${skipped} already there`}`);
