// Sign every unsigned nanopub in a directory with the operator's key and publish it to a registry.
// Generic version of the per-project claim-sources/<project>/build/publish.mjs, for the record
// types that have no project of their own: problems, approaches and runs (problems/nanopubs/)
// and claim tests (test-data/claim-tests/nanopubs/).
//
// Signing is deterministic for a given file, so promoting a test batch re-signs the same files to
// the same trusty URIs; production is refused for any URI not already on test (BEST_PRACTICES.md
// sections 3 and 4). Every publication is appended to <dir>/../manifest.jsonl (section 8); the
// builders read that file and never regenerate a published record.
//
//   node scripts/release/publish.mjs --registry test --dir problems/nanopubs/unsigned [--only run--] [--dry-run]
//   node scripts/release/publish.mjs --registry production --dir problems/nanopubs/unsigned
//
// --only <prefix> restricts the batch to files whose name starts with the prefix. --dry-run signs
// and verifies without uploading. Keys live in ~/.nanopub/ and are never read from the repo.
import { readFileSync, writeFileSync, appendFileSync, mkdirSync, readdirSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Nanopub } from "@nanopub/nanopub-js";

const ENGINE = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const arg = (name, dflt) => { const i = process.argv.indexOf(name); return i > -1 ? process.argv[i + 1] : dflt; };
const REGISTRIES = {
  test: "https://test.registry.knowledgepixels.com/",
  production: "https://registry.knowledgepixels.com/",
};
const registry = arg("--registry");
if (!REGISTRIES[registry]) throw new Error("--registry must be test or production");
const dirArg = arg("--dir");
if (!dirArg) throw new Error("--dir <path to an unsigned/ directory, relative to  or absolute> is required");
const dir = resolve(ENGINE, dirArg);
if (basename(dir) !== "unsigned") throw new Error("--dir must name an *unsigned* directory");
const signedDir = join(dir, "..", "signed");
const only = arg("--only", "");
const dryRun = process.argv.includes("--dry-run");
const MANIFEST = join(dir, "..", "manifest.jsonl");

const profile = readFileSync(join(homedir(), ".nanopub/profile.yml"), "utf8");
const orcid = profile.match(/^orcid_id:\s*(\S+)/m)?.[1];
const name = profile.match(/^name:\s*(.+)$/m)?.[1]?.trim();
const privateKey = readFileSync(join(homedir(), ".nanopub/id_rsa"), "utf8").replace(/\s+/g, "");
if (!orcid || !name) throw new Error("~/.nanopub/profile.yml has no orcid_id or name");

const commit = execSync("git rev-parse HEAD", { cwd: ENGINE, encoding: "utf8" }).trim();
const manifest = existsSync(MANIFEST) ? readFileSync(MANIFEST, "utf8").split("\n").filter(Boolean).map(l => JSON.parse(l)) : [];
const onTest = new Set(manifest.filter(m => m.registry === "test").map(m => m.trustyUri));
const already = new Set(manifest.filter(m => m.registry === registry).map(m => m.trustyUri));

mkdirSync(signedDir, { recursive: true });
const files = readdirSync(dir).filter(f => f.endsWith(".trig") && f.startsWith(only)).sort();
if (!files.length) throw new Error(`no .trig files in ${dir}${only ? ` starting with ${only}` : ""}`);
let published = 0, skipped = 0, failed = 0;
for (const f of files) {
  const np = Nanopub.fromRdf(readFileSync(join(dir, f), "utf8"), "trig", { privateKey, orcid, name });
  await np.sign({ keyCheck: "strict" });
  if (!(await np.hasValidSignature())) throw new Error(`${f}: signature does not verify`);
  const uri = np.sourceUri;
  if (!/^https:\/\/w3id\.org\/np\/RA[A-Za-z0-9_-]{43}$/.test(uri)) throw new Error(`${f}: unexpected URI ${uri}`);
  writeFileSync(join(signedDir, f), np.rdf());
  if (registry === "production" && !onTest.has(uri)) throw new Error(`${f}: ${uri} was never published to test; refusing production`);
  if (already.has(uri)) { skipped++; continue; }
  if (dryRun) continue;
  let res;
  try {
    res = await np.publish(REGISTRIES[registry], { keyCheck: "strict" });
  } catch (e) {
    failed++; console.error(`${f}: publish failed: ${e.message}`); continue;
  }
  if (!res.response.ok) { failed++; console.error(`${f}: registry answered ${res.response.status} ${await res.response.text()}`); continue; }
  appendFileSync(MANIFEST, JSON.stringify({
    file: `unsigned/${f}`, id: f.replace(/\.trig$/, ""), trustyUri: uri, registry,
    publishedAt: new Date().toISOString(), generatorCommit: commit,
  }) + "\n");
  published++;
}
console.log(`${files.length} signed into ${signedDir}; ${dryRun ? "dry run, nothing published" : `${published} published to ${registry}, ${skipped} already there${failed ? `, ${failed} FAILED (not in the manifest; re-run to retry)` : ""}`}`);
if (failed) process.exit(1);
