// MorphoEval audits from github.com/fractastical/morpholib and the claims here they test or model.
// Reads test-data/morpholib/links.json (see its README) and docs/claims.json; view "live" asks the
// published network which morpholib claims exist now, to show what links.json is missing.

import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { REPO, sparql } from "./lib.mjs";

const LINKS = join(REPO, "test-data/morpholib/links.json");
const CLAIMS = join(REPO, "docs/claims.json");
export const MORPHOLIB_VIEWS = ["summary", "list", "audit", "claim", "live"];
export const REGISTRIES = ["production", "test", "unconfirmed", "unpublished"];
export const RELATIONS = ["tests", "models", "any", "none"];
const NOTE = "verdict and score grade whether the simulation reproduces the specimens, not whether the claim is true; thompsonVerdict is morpholib's verdict on Thompson's claim itself. tests = the audit measured the claim's assertion on specimens; models = it simulates the claim's mechanism. Neither sets a claim's data-test evidence.";

let cache = null;
function load() {
  const stamp = `${statSync(LINKS).mtimeMs}:${statSync(CLAIMS).mtimeMs}`;
  if (cache?.stamp === stamp) return cache.data;
  const { source, claims: audits, links } = JSON.parse(readFileSync(LINKS, "utf8"));
  const delphi = new Map(JSON.parse(readFileSync(CLAIMS, "utf8")).claims.map(c => [c.id, c]));
  const byAudit = new Map(audits.map(a => [a.id, []]));
  const byClaim = new Map();
  for (const l of links) {
    byAudit.get(l.morpholib)?.push(l);
    (byClaim.get(l.claim) ?? byClaim.set(l.claim, []).get(l.claim)).push(l);
  }
  cache = { stamp, data: { source, audits, byId: new Map(audits.map(a => [a.id, a])), byAudit, byClaim, delphi } };
  return cache.data;
}

const has = (value, needle) => String(value ?? "").toLowerCase().includes(needle.toLowerCase());
const shortId = id => String(id).trim().replace(/^.*\/claim\//, "").replace(/^morphoeval-/, "");
const count = (xs, f) => xs.reduce((m, x) => { const k = f(x) ?? "none"; m[k] = (m[k] ?? 0) + 1; return m; }, {});

function claimRef(d, id) {
  const c = d.delphi.get(id);
  return c ? { id, title: c.label, thinker: c.thinker, verification: c.verification, evidence: c.evidence ?? undefined, nanopub: c.nanopub, registry: c.registry } : { id, missing: true };
}
const linkedClaims = (d, a) => d.byAudit.get(a.id).map(l => ({ relation: l.relation, note: l.note, ...claimRef(d, l.claim) }));
const row = (d, a) => ({
  id: a.id, label: a.label, organism: a.organism, verdict: a.verdict, score: a.score, weightOfEvidence: a.weight_of_evidence,
  thompson: a.thompson ? `${a.thompson.id} (${a.thompson.verdict ?? "no verdict"})` : undefined,
  registry: a.registry, nanopub: a.nanopub, report: a.report,
  claims: d.byAudit.get(a.id).map(l => `${l.relation} ${l.claim}`),
});

function summary(d) {
  const linked = d.audits.filter(a => d.byAudit.get(a.id).length);
  const links = [...d.byAudit.values()].flat();
  const thinkers = count([...d.byClaim.keys()], id => d.delphi.get(id)?.thinker);
  return {
    source: d.source, note: NOTE,
    audits: d.audits.length, linkedAudits: linked.length,
    byRegistry: count(d.audits, a => a.registry), byVerdict: count(d.audits, a => a.verdict),
    thompsonAudits: d.audits.filter(a => a.thompson).length,
    links: links.length, byRelation: count(links, l => l.relation),
    claimsLinked: d.byClaim.size, claimsTested: [...d.byClaim.values()].filter(ls => ls.some(l => l.relation === "tests")).length,
    claimsLinkedByThinker: thinkers,
    next: "view \"list\" with filters, \"audit\" with id, \"claim\" with a delphisci claim id, \"live\" for what is published now",
  };
}

function list(d, { text, registry, verdict, relation, thompson, thinker, sort = "score", limit = 50 }) {
  const hits = d.audits.filter(a => {
    const ls = d.byAudit.get(a.id);
    return (!text || has(`${a.id} ${a.label} ${a.organism} ${a.thompson?.claim ?? ""}`, text))
      && (!registry || a.registry === registry)
      && (!verdict || has(a.verdict, verdict))
      && (thompson == null || !!a.thompson === thompson)
      && (!relation || (relation === "none" ? !ls.length : relation === "any" ? ls.length > 0 : ls.some(l => l.relation === relation)))
      && (!thinker || ls.some(l => has(d.delphi.get(l.claim)?.thinker, thinker)));
  });
  const key = { score: a => a.score ?? -1, woe: a => a.weight_of_evidence ?? -1, links: a => d.byAudit.get(a.id).length };
  if (!key[sort]) throw new Error(`sort must be one of ${Object.keys(key).join(", ")}`);
  return { note: NOTE, matched: hits.length,
    audits: hits.sort((a, b) => key[sort](b) - key[sort](a)).slice(0, Math.min(Number(limit) || 50, 500)).map(a => row(d, a)) };
}

function audit(d, id) {
  const a = d.byId.get(shortId(id));
  if (!a) return { found: false, id, hint: "Find ids with view \"list\" and text, e.g. text: \"nautilus\"" };
  return { note: NOTE, ...a, linked: linkedClaims(d, a) };
}

function forClaim(d, id) {
  const cid = String(id).trim().replace(/^https:\/\/w3id\.org\/delphi\/resource\/claim\//, "");
  const ls = d.byClaim.get(cid) ?? [];
  return { note: NOTE, claim: claimRef(d, cid),
    audits: ls.map(l => ({ relation: l.relation, note: l.note, ...row(d, d.byId.get(l.morpholib)), claims: undefined })) };
}

// Both vocabularies: older bundles use probknow, newer ones delphi; every one links its code to the repo.
const LIVE = `PREFIX np: <http://www.nanopub.org/nschema#>
PREFIX npx: <http://purl.org/nanopub/x/>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX schema: <https://schema.org/>
SELECT DISTINCT ?np ?claim ?label WHERE {
  GRAPH ?a { ?code schema:codeRepository <https://github.com/fractastical/morpholib> . ?claim a ?type .
    FILTER(?type IN (<https://w3id.org/delphi/ontology/Claim>, <https://w3id.org/probknow/ontology/Claim>))
    OPTIONAL { ?claim rdfs:label ?label } }
  GRAPH ?h { ?np np:hasAssertion ?a }
  FILTER NOT EXISTS { GRAPH ?i { ?x npx:invalidates ?np } }
} LIMIT 5000`;

async function live(d) {
  const rows = await sparql(LIVE, "network");
  const known = new Map(d.audits.map(a => [a.claim, a]));
  const published = rows.map(r => {
    const a = known.get(r.claim);
    return { id: shortId(r.claim), nanopub: r.np, label: r.label ?? a?.label, inLinks: !!a, nanopubChanged: a ? a.nanopub !== r.np : undefined };
  });
  const onNetwork = new Set(rows.map(r => r.claim));
  return {
    published: published.length,
    notInLinks: published.filter(p => !p.inLinks),
    nanopubChanged: published.filter(p => p.nanopubChanged),
    inLinksMarkedProductionButNotFound: d.audits.filter(a => a.registry === "production" && !onNetwork.has(a.claim)).map(a => a.id),
    linksFile: { ...d.source, audits: d.audits.length },
    note: "Production registry only; test-registry audits (most Thompson ones) are not on this endpoint. Refresh links.json as in test-data/morpholib/README.md.",
    claims: published,
  };
}

export async function morpholibTool({ view, id, ...filters } = {}) {
  const d = load();
  const filtered = Object.values(filters).some(v => v != null);
  const v = view ?? (id ? (d.byId.has(shortId(id)) ? "audit" : "claim") : filtered ? "list" : "summary");
  if (!MORPHOLIB_VIEWS.includes(v)) throw new Error(`view must be one of ${MORPHOLIB_VIEWS.join(", ")}`);
  if ((v === "audit" || v === "claim") && !id) throw new Error(`view "${v}" needs id`);
  return { summary: () => summary(d), list: () => list(d, filters), audit: () => audit(d, id), claim: () => forClaim(d, id), live: () => live(d) }[v]();
}
