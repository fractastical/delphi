// Sign every unsigned nanopub in a directory with the publisher's key and publish it.
// Signing is deterministic for a given file, so promoting a test batch re-signs the same
// files to the same trusty URIs; production is refused for any URI not already on test.
//
//   node build/publish.mjs --registry test [--dir nanopubs/unsigned] [--dry-run]
//   node build/publish.mjs --registry production --dir nanopubs/unsigned
import { readFileSync, writeFileSync, appendFileSync, mkdirSync, readdirSync, existsSync } from "node:fs";
import { homedir } from "node:os";
import { execSync } from "node:child_process";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Nanopub } from "@nanopub/nanopub-js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const arg = (name, dflt) => { const i = process.argv.indexOf(name); return i > -1 ? process.argv[i + 1] : dflt; };
const REGISTRIES = {
  test: "https://test.registry.knowledgepixels.com/",
  production: "https://registry.knowledgepixels.com/",
};
const registry = arg("--registry");
if (!REGISTRIES[registry]) throw new Error("--registry must be test or production");
const dir = join(ROOT, arg("--dir", "nanopubs/unsigned"));
const signedDir = join(dir, "..", basename(dir).replace(/^unsigned/, "signed"));
const dryRun = process.argv.includes("--dry-run");
const MANIFEST = join(ROOT, "nanopubs/manifest.jsonl");

const profile = readFileSync(join(homedir(), ".nanopub/profile.yml"), "utf8");
const orcid = profile.match(/^orcid_id:\s*(\S+)/m)?.[1];
const name = profile.match(/^name:\s*(.+)$/m)?.[1]?.trim();
const privateKey = readFileSync(join(homedir(), ".nanopub/id_rsa"), "utf8").replace(/\s+/g, "");
if (!orcid || !name) throw new Error("~/.nanopub/profile.yml has no orcid_id or name");

const commit = execSync("git rev-parse HEAD", { cwd: ROOT, encoding: "utf8" }).trim();
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
  if (dryRun) continue;
  const res = await np.publish(REGISTRIES[registry], { keyCheck: "strict" });
  if (!res.response.ok) throw new Error(`${f}: registry answered ${res.response.status} ${await res.response.text()}`);
  appendFileSync(MANIFEST, JSON.stringify({
    file: `${basename(dir)}/${f}`, id: f.replace(/\.trig$/, ""), trustyUri: uri, registry,
    publishedAt: new Date().toISOString(), generatorCommit: commit,
  }) + "\n");
  published++;
}
console.log(`${files.length} signed into ${signedDir}; ${dryRun ? "dry run, nothing published" : `${published} published to ${registry}, ${skipped} already there`}`);
