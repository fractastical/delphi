// Signs nanopubs/unsigned/*.trig with the operator's key, lints the signed batch, and publishes
// it to the TEST registry only, recording each trusty URI in nanopubs/manifest.json.
//
//   NANOPUB_ORCID=https://orcid.org/... NANOPUB_NAME="..." \
//   DELPHI_PIPELINE=/path/to/project-delphi-ontology/pipeline npx tsx publish-test.mts

import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const TEST_REGISTRY = "https://test.registry.knowledgepixels.com/";
const here = dirname(fileURLToPath(import.meta.url));
const pipeline = process.env.DELPHI_PIPELINE;
const orcid = process.env.NANOPUB_ORCID;
const name = process.env.NANOPUB_NAME;
if (!pipeline || !orcid || !name) throw new Error("Set DELPHI_PIPELINE, NANOPUB_ORCID and NANOPUB_NAME");

const { Nanopub } = await import(pathToFileURL(resolve(pipeline, "node_modules/@nanopub/nanopub-js/dist/index.js")).href);
const { lintBatch } = await import(pathToFileURL(resolve(pipeline, "lint.ts")).href);

const privateKey = readFileSync(join(homedir(), ".nanopub/id_rsa"), "utf8").replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
const unsignedDir = join(here, "nanopubs/unsigned");
const signedDir = join(here, "nanopubs/signed-test");
mkdirSync(signedDir, { recursive: true });

const manifestPath = join(here, "nanopubs/manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const entryFor = (file: string) => manifest.nanopubs.find((m: any) => m.file === `nanopubs/unsigned/${file}`);

const signed: { file: string; np: any }[] = [];
for (const file of readdirSync(unsignedDir).filter(f => f.endsWith(".trig") && !entryFor(f)?.trustyUri).sort()) {
  const np = Nanopub.fromRdf(readFileSync(join(unsignedDir, file), "utf8"), "trig", { privateKey, orcid, name });
  await np.sign({ keyCheck: "warn" });
  if (!(await np.hasValidSignature())) throw new Error(`${file}: signature does not verify`);
  writeFileSync(join(signedDir, file), np.rdf());
  signed.push({ file, np });
}

const findings = lintBatch(signed.map(s => ({ file: s.file, trig: s.np.rdf() })), { extracted: true });
if (findings.length) {
  for (const f of findings) console.error(`${f.file}: ${f.rule}: ${f.subject} ${f.message}`);
  throw new Error(`${findings.length} lint finding(s) on the signed batch; nothing published`);
}

for (const { file, np } of signed) {
  const res = await np.publish(TEST_REGISTRY, { keyCheck: "warn" });
  if (!res.response.ok) throw new Error(`${file}: registry answered ${res.response.status}`);
  Object.assign(entryFor(file), { signedFile: `nanopubs/signed-test/${file}`, trustyUri: res.uri, registry: TEST_REGISTRY, publishedAt: new Date().toISOString(), signer: orcid, lintCommit: process.env.LINT_COMMIT ?? null });
  console.log(`${file} -> ${res.uri}`);
}
manifest.status = manifest.nanopubs.every((m: any) => m.trustyUri)
  ? "published to the test registry; not promoted to production"
  : "partly published to the test registry; not promoted to production";
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
console.log(`published ${signed.length} nanopubs to ${TEST_REGISTRY}`);
