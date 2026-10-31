// The claim graph as built for docs/claim-graph.html: every claim with thinker, year, proof status,
// testability and the truth scores from test-data/truth/raw, read from docs/claims.json. Rebuild that file
// with `node scripts/site/build-claim-graph.mjs`.

import { readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { REPO, getClaim, overview, rankClaims, searchClaims } from "./lib.mjs";

export const CLAIMS_JSON = join(REPO, "docs/claims.json");

// Links into the built pages. DELPHI_DOCS_URL points them at a hosted copy of docs/ instead.
const DOCS = (process.env.DELPHI_DOCS_URL ?? pathToFileURL(join(REPO, "docs")).href).replace(/\/$/, "");
// Query parameters understood by docs/claim-graph.html: level, math (yes|no), thm, thinker, p, t, claim.
export function graphUrl(params = {}, page = "claim-graph") {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== false && v !== ""));
  return `${DOCS}/${page}.html${q.size ? `?${q}` : ""}`;
}
const LEVELS = ["lean", "literature", "partial", "untested", "refuted"];
const LEVEL_LABEL = { lean: "Lean-checked", literature: "Proved (literature)", partial: "Partly proved", untested: "Not proved", refuted: "Refuted" };
// Verdicts of tests against data (test-data/claim-tests/), a separate axis from proof.
const EVIDENCE = ["supports", "mixed", "refutes", "inconclusive"];

let cache = null;

function load() {
  const mtime = statSync(CLAIMS_JSON).mtimeMs;
  if (cache?.mtime === mtime) return cache.data;
  const data = JSON.parse(readFileSync(CLAIMS_JSON, "utf8"));
  for (const c of data.claims) {
    const p = c.truth_by.map(x => x.p_true);
    c.disagreement = p.length > 1 ? +(Math.max(...p) - Math.min(...p)).toFixed(3) : null;
  }
  data.byId = new Map(data.claims.map(c => [c.id, c]));
  cache = { mtime, data };
  return data;
}

// Proof and data-test status of a claim. The nanopubs carry neither, so the claim tools take it
// from docs/claims.json and attach it to every claim they return.
function claimStatus(claim) {
  const c = load().byId.get(String(claim).replace(/^https:\/\/w3id\.org\/delphi\/resource\/claim\//, ""));
  if (!c) return undefined;
  const t = c.data_test;
  return {
    verification: c.verification, theorem: c.theorem, math: c.math,
    leanTheorems: c.lean_theorems ?? undefined,
    dataTest: t ? { verdict: t.verdict, dataKind: t.data_kind, confidence: t.confidence, preregistered: t.preregistered, result: t.path } : undefined,
    registry: c.registry, graph: graphUrl({ claim: c.id }),
  };
}

const STATUS_NOTE = "status: verification = lean (machine-checked in Lean 4), literature (proved in the literature), partial, untested or refuted; dataTest = verdict of a pre-registered test against data, with dataKind = biological (measured on organisms; the only kind that shows a claim holds in biology), physical, computational (simulation or mathematics) or none; registry = production, test or null (unpublished). From docs/claims.json, built ";

export async function searchClaimsWithStatus(args) {
  const rows = await searchClaims(args);
  return { statusNote: STATUS_NOTE + load().built, claims: rows.map(r => ({ ...r, status: claimStatus(r.claim) })) };
}

export async function getClaimWithStatus(args) {
  const r = await getClaim(args);
  return r.found === false ? r : { ...r, status: claimStatus(r.claim), statusNote: STATUS_NOTE + load().built };
}

export async function rankClaimsWithStatus(args) {
  const rows = await rankClaims(args);
  return Array.isArray(rows) ? { statusNote: STATUS_NOTE + load().built, ranked: rows.map(r => ({ ...r, status: claimStatus(r.claim) })) } : rows;
}

const has = (value, needle) => String(value ?? "").toLowerCase().includes(needle.toLowerCase());
const mean = xs => (xs.length ? +(xs.reduce((a, b) => a + b, 0) / xs.length).toFixed(3) : null);

const SORTS = {
  truth: (a, b) => (b.truth ?? -1) - (a.truth ?? -1),
  "truth-asc": (a, b) => (a.truth ?? 2) - (b.truth ?? 2),
  disagreement: (a, b) => (b.disagreement ?? -1) - (a.disagreement ?? -1),
  testability: (a, b) => (b.testability ?? -1) - (a.testability ?? -1),
  year: (a, b) => a.year - b.year,
};
export const SORT_KEYS = Object.keys(SORTS);

const GROUPS = {
  thinker: c => c.thinker,
  work: c => c.work,
  decade: c => `${Math.floor(c.year / 10) * 10}s`,
  status: c => c.status,
  verification: c => c.verification,
  evidenceKind: c => c.evidence_kind ?? "untested",
  kind: c => c.kind,
};
export const GROUP_KEYS = Object.keys(GROUPS);

// The verification table at the top of docs/claim-graph.html, with links that open the graph
// filtered to each cell.
export function graphStatus() {
  const { built, claims } = load();
  const count = (cs, f) => cs.filter(f).length;
  const tally = cs => ({
    claims: cs.length, theorems: count(cs, c => c.theorem), math: count(cs, c => c.math),
    ...Object.fromEntries(LEVELS.map(l => [l, count(cs, c => c.verification === l)])),
    mathUnverified: count(cs, c => c.math && c.verification === "untested"),
    tested: count(cs, c => c.evidence),
    ...Object.fromEntries(EVIDENCE.map(e => [e, count(cs, c => c.evidence === e)])),
    neither: count(cs, c => c.verification === "untested" && !c.evidence),
    onOrganisms: count(cs, c => c.evidence_kind === "biological"),
    mathInOrganisms: count(cs, c => c.math && c.evidence_kind === "biological" && c.evidence === "supports"),
  });
  const thinkers = [...new Set([...claims].sort((a, b) => a.year - b.year).map(c => c.thinker))];
  const rows = thinkers.map(t => ({ thinker: t, ...tally(claims.filter(c => c.thinker === t)), graph: graphUrl({ thinker: t }) }));
  const total = tally(claims);
  const links = {
    graph: graphUrl(),
    theorems: graphUrl({ thm: 1 }),
    mathUnverified: graphUrl({ math: "yes", level: "untested" }),
    leanChecked: graphUrl({ level: "lean" }),
    theoremsPage: graphUrl({}, "theorems"),
  };
  const cell = (n, params) => (n ? `[${n}](${graphUrl(params)})` : "·");
  const plain = n => (n ? String(n) : "·");
  const line = (name, r, t) => `| ${t ? `[${name}](${graphUrl({ thinker: t })})` : `**${name}**`} | ${r.claims} | ${cell(r.math, { thinker: t, math: "yes" })} | ${plain(r.mathInOrganisms)} | ${cell(r.theorems, { thinker: t, thm: 1 })} | `
    + LEVELS.map(l => cell(r[l], { thinker: t, level: l })).join(" | ") + ` | ${cell(r.mathUnverified, { thinker: t, math: "yes", level: "untested" })} | `
    + cell(r.tested, { thinker: t, ev: "any" }) + ` | ${plain(r.onOrganisms)} | ` + EVIDENCE.map(e => cell(r[e], { thinker: t, ev: e })).join(" | ") + ` | ${cell(r.neither, { thinker: t, level: "untested", ev: "none" })} |`;
  const markdown = [
    `**Claim graph, built ${built}:** ${total.claims} claims. **${total.mathInOrganisms} of ${total.math} math claims are supported by data measured on organisms.** ${total.tested} claims tested against data, ${total.onOrganisms} of them on organisms (${EVIDENCE.map(e => `${total[e]} ${e}`).join(", ")} across all data kinds). ${total.theorems} theorems (${total.lean} Lean-checked, ${total.literature} proved in the literature); ${total.mathUnverified} math claims not proved; ${total.neither} claims neither proved nor tested.`,
    "",
    `| Thinker | Claims | ∑ Math | ★ Math supported in organisms | Theorems | ${LEVELS.map(l => LEVEL_LABEL[l]).join(" | ")} | Math, not proved | Tested | Tested on organisms | ${EVIDENCE.map(e => `Data: ${e}`).join(" | ")} | Neither |`,
    `|---|${"---:|".repeat(LEVELS.length + 6 + EVIDENCE.length + 2)}`,
    ...rows.map(r => line(r.thinker, r, r.thinker)),
    line("All", total, null),
    "",
    `Open: [full graph](${links.graph}) · [theorems only](${links.theorems}) · [math claims awaiting proof](${links.mathUnverified}) · [theorems page](${links.theoremsPage}). Every count above links to the graph filtered to it.`,
    "A theorem is a math claim (formal notation, a Lean formalization, or a mathematical kind) that is machine-checked in Lean 4 or proved in the literature. Tested against data is a separate axis: the verdict of a pre-registered test in test-data/claim-tests/, which never makes a claim a theorem. Only tests whose data were measured on organisms (data_kind biological) show that a claim holds in biology; simulation and mathematical enumeration show it holds as mathematics. Assessor truth scores count as neither.",
  ].join("\n");
  return { markdown, built, total, thinkers: rows, links };
}

// delphi_overview: the nanopub overview plus the graph's status table and links.
export async function overviewWithGraph(source) {
  const { markdown, built, total, links } = graphStatus();
  return { markdown, ...(await overview(source)),
    claimGraph: { built, total, links, more: "delphi_graph with no arguments returns this table per thinker; add filters to list claims" } };
}

const FILTERS = ["text", "thinker", "work", "status", "verification", "evidence", "evidenceKind", "math", "theorem", "kind", "yearFrom", "yearTo", "minTruth", "maxTruth", "published", "groupBy"];

export function browseClaims(args = {}) {
  const view = args.view ?? (FILTERS.some(k => args[k] != null) || args.minTruthAssessors ? "claims" : "status");
  if (view === "status") return graphStatus();
  return listClaims(args);
}

function listClaims(args) {
  const { text, thinker, work, status, verification, evidence, evidenceKind, math, theorem, kind, yearFrom, yearTo, minTruth, maxTruth, minTruthAssessors = 0,
    published, sort = "truth", groupBy, limit = 20 } = args;
  const { built, claims } = load();
  const hits = claims.filter(c =>
    (!text || has(`${c.label} ${c.statement} ${c.quote ?? ""}`, text))
    && (!thinker || has(c.thinker, thinker))
    && (!work || has(c.work, work))
    && (!status || c.status === status)
    && (!verification || c.verification === verification)
    && (!evidence || (evidence === "any" ? !!c.evidence : evidence === "none" ? !c.evidence : c.evidence === evidence))
    && (!evidenceKind || c.evidence_kind === evidenceKind)
    && (math == null || c.math === math)
    && (theorem == null || c.theorem === theorem)
    && (!kind || has(c.kind, kind))
    && (yearFrom == null || c.year >= yearFrom)
    && (yearTo == null || c.year <= yearTo)
    && (minTruth == null || (c.truth != null && c.truth >= minTruth))
    && (maxTruth == null || (c.truth != null && c.truth <= maxTruth))
    && c.truth_by.length >= minTruthAssessors
    && (published == null || (published ? c.registry === "production" : c.registry !== "production")));

  // The same view in the browser, for the filters the page supports.
  const names = [...new Set(hits.map(c => c.thinker))];
  const params = { thinker: thinker && names.length === 1 ? names[0] : null, level: verification ?? (status === "proved" ? null : status),
    math: math == null ? null : math ? "yes" : "no", thm: theorem ? 1 : null, p: minTruth };
  const unmapped = ["text", "work", "kind", "yearFrom", "yearTo", "maxTruth", "published", "evidence", "evidenceKind"].filter(k => args[k] != null);
  const graph = graphUrl(params);
  const graphNote = unmapped.length ? `The graph link cannot apply ${unmapped.join(", ")}; it shows a superset of these results.` : undefined;

  if (groupBy) {
    if (!GROUPS[groupBy]) throw new Error(`groupBy must be one of ${GROUP_KEYS.join(", ")}`);
    const groups = new Map();
    for (const c of hits) {
      const k = GROUPS[groupBy](c);
      (groups.get(k) ?? groups.set(k, []).get(k)).push(c);
    }
    return {
      built, matched: hits.length, groupBy, graph, graphNote,
      groups: [...groups].map(([group, cs]) => ({
        group, claims: cs.length,
        meanTruth: mean(cs.map(c => c.truth).filter(v => v != null)),
        meanDisagreement: mean(cs.map(c => c.disagreement).filter(v => v != null)),
        meanTestability: mean(cs.map(c => c.testability).filter(v => v != null)),
        published: cs.filter(c => c.registry === "production").length,
        statuses: cs.reduce((m, c) => ({ ...m, [c.status]: (m[c.status] ?? 0) + 1 }), {}),
        verification: cs.reduce((m, c) => ({ ...m, [c.verification]: (m[c.verification] ?? 0) + 1 }), {}),
        math: cs.filter(c => c.math).length,
        theorems: cs.filter(c => c.theorem).length,
        testedOnOrganisms: cs.filter(c => c.evidence_kind === "biological").length,
        supportedInOrganisms: cs.filter(c => c.evidence_kind === "biological" && c.evidence === "supports").length,
      })).sort((a, b) => b.claims - a.claims),
    };
  }

  if (!SORTS[sort]) throw new Error(`sort must be one of ${SORT_KEYS.join(", ")}`);
  return {
    built, matched: hits.length, graph, graphNote,
    claims: [...hits].sort(SORTS[sort]).slice(0, Math.min(Number(limit) || 20, 500)).map(c => ({
      graph: graphUrl({ claim: c.id }),
      id: c.id, title: c.label, statement: c.statement, thinker: c.thinker, year: c.year, work: c.work, chapter: c.chapter,
      kind: c.kind, status: c.status, verification: c.verification, math: c.math, theorem: c.theorem, notation: c.notation ?? undefined, truth: c.truth, truthBy: c.truth_by, disagreement: c.disagreement,
      evidence: c.evidence ?? undefined, evidenceKind: c.evidence_kind ?? undefined,
      testability: c.testability, nanopub: c.nanopub, registry: c.registry, draft: c.draft || undefined,
    })),
  };
}
