// Promotes the batch already on the test registry to production: posts the same signed files
// (same trusty URIs), after checking that every manifest entry is on test, that each signature
// verifies, and that the signed batch lints clean. Never re-signs.
//
//   APPROVED_BY=https://orcid.org/... DELPHI_PIPELINE=/path/to/pipeline npx tsx publish-production.mts

import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const PRODUCTION_REGISTRY = "https://registry.knowledgepixels.com/np/";
const here = dirname(fileURLToPath(import.meta.url));
const pipeline = process.env.DELPHI_PIPELINE;
const approvedBy = process.env.APPROVED_BY;
if (!pipeline || !approvedBy) throw new Error("Set DELPHI_PIPELINE and APPROVED_BY");

const { Nanopub, verifySignature } = await import(pathToFileURL(resolve(pipeline, "node_modules/@nanopub/nanopub-js/dist/index.js")).href);
const { Parser } = await import(pathToFileURL(resolve(pipeline, "node_modules/n3/lib/index.js")).href);
const npUri = (trig: string): string | undefined => new Parser({ format: "application/trig" }).parse(trig)
  .find((q: any) => q.predicate.value === "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
    && q.object.value === "http://www.nanopub.org/nschema#Nanopublication")?.subject.value;
const { lintBatch } = await import(pathToFileURL(resolve(pipeline, "lint.ts")).href);

const manifestPath = join(here, "nanopubs/manifest.json");
const manifest = JSON.parse(readFileSync(manifestPath, "utf8"));
const pending = manifest.nanopubs.filter((m: any) => !m.productionRegistry);
for (const m of pending)
  if (!m.trustyUri || !m.signedFile || !m.registry?.includes("test.registry"))
    throw new Error(`${m.claim}: not on the test registry yet; promote only what passed on test`);

const batch = [];
for (const m of pending) {
  const trig = readFileSync(join(here, m.signedFile), "utf8");
  // A nanopub loaded with fromRdf carries no signature field or sourceUri, so check the text itself.
  if (!(await verifySignature(trig)).valid) throw new Error(`${m.signedFile}: signature does not verify`);
  const uri = npUri(trig);
  if (uri !== m.trustyUri) throw new Error(`${m.signedFile}: ${uri} is not the URI published on test (${m.trustyUri})`);
  const np = Nanopub.fromRdf(trig, "trig");
  batch.push({ m, np, trig });
}

const findings = lintBatch(batch.map(b => ({ file: b.m.signedFile, trig: b.trig })), { extracted: true });
if (findings.length) {
  for (const f of findings) console.error(`${f.file}: ${f.rule}: ${f.subject} ${f.message}`);
  throw new Error(`${findings.length} lint finding(s); nothing promoted`);
}

for (const { m, np } of batch) {
  const res = await np.publish(PRODUCTION_REGISTRY, { keyCheck: "warn" });
  if (!res.response.ok) throw new Error(`${m.signedFile}: registry answered ${res.response.status}`);
  Object.assign(m, { productionRegistry: PRODUCTION_REGISTRY, productionPublishedAt: new Date().toISOString(),
    promotionApprovedBy: approvedBy, secondReviewer: null });
  writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
  console.log(`${m.signedFile} -> ${m.trustyUri}`);
}
manifest.status = manifest.nanopubs.every((m: any) => m.productionRegistry)
  ? "published to production (promoted from test)"
  : "partly promoted to production";
writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + "\n");
console.log(`promoted ${batch.length} nanopubs to ${PRODUCTION_REGISTRY}`);
