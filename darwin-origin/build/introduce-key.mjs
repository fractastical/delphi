// Publish an introduction declaring the local ~/.nanopub key for the profile's ORCID, so
// nanopubs signed with it are attributable. Test first, then production with --registry production.
//
//   node build/introduce-key.mjs --registry test|production
import { readFileSync, appendFileSync, writeFileSync, mkdirSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { createIntroNanopub } from "@nanopub/nanopub-js";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const REGISTRIES = { test: "https://test.registry.knowledgepixels.com/", production: "https://registry.knowledgepixels.com/" };
const registry = process.argv[process.argv.indexOf("--registry") + 1];
if (!REGISTRIES[registry]) throw new Error("--registry must be test or production");

const profile = readFileSync(join(homedir(), ".nanopub/profile.yml"), "utf8");
const agent = profile.match(/^orcid_id:\s*(\S+)/m)?.[1];
const name = profile.match(/^name:\s*(.+)$/m)?.[1]?.trim();
const privateKey = readFileSync(join(homedir(), ".nanopub/id_rsa"), "utf8").replace(/\s+/g, "");

const np = await createIntroNanopub({ agent, name, privateKey, license: "https://creativecommons.org/licenses/by/4.0/" });
await np.sign({ keyCheck: "off" });
if (!(await np.hasValidSignature())) throw new Error("introduction signature does not verify");
mkdirSync(join(ROOT, "nanopubs/intro"), { recursive: true });
writeFileSync(join(ROOT, `nanopubs/intro/introduction-${registry}.trig`), np.rdf());
const res = await np.publish(REGISTRIES[registry], { keyCheck: "off" });
if (!res.response.ok) throw new Error(`registry answered ${res.response.status} ${await res.response.text()}`);
appendFileSync(join(ROOT, "nanopubs/manifest.jsonl"), JSON.stringify({
  file: `intro/introduction-${registry}.trig`, id: "introduction", trustyUri: res.uri, registry, publishedAt: new Date().toISOString(),
}) + "\n");
console.log(`introduction ${res.uri} published to ${registry}`);
