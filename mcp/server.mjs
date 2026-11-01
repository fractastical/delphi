#!/usr/bin/env node
// MCP server exposing delphisci claims, their math, their assessment rankings and the claim graph.
// Runs over stdio, or over Streamable HTTP at /mcp when DELPHI_HTTP_PORT is set (see mcp/http.mjs).

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { GROUP_KEYS, SORT_KEYS, browseClaims, getClaimWithStatus, overviewWithGraph, rankClaimsWithStatus, searchClaimsWithStatus } from "./graph.mjs";
import { NETWORK_ENDPOINT, PREFIXES, sparql } from "./lib.mjs";
import { ARTIFACT_TYPES, FORUM_URL, INCONCLUSIVE_REASONS, LEADERBOARD_SORTS, POST_KINDS, REQUEST_STATUSES, VERDICTS, forumPost, forumRead, forumRegister, forumRespond, logTestResult, proposeClaim } from "./forum.mjs";
import { observeToolCall } from "./metrics.mjs";
import { DATA_KINDS as TEST_DATA_KINDS, TEST_VIEWS, VERDICTS as TEST_VERDICTS, claimTestsTool } from "./tests.mjs";
import { AXIS_IDS, GROUP_KEYS as ORG_GROUP_KEYS, SORT_KEYS as ORG_SORT_KEYS, browseOrganisms, getOrganism, organismsOverview } from "./organisms.mjs";
import { MORPHOLIB_VIEWS, REGISTRIES, RELATIONS, morpholibTool } from "./morpholib.mjs";
import { replicationsTool } from "./federation.mjs";
import { LEAN_TOOLS } from "../sim-engine/tools/lean-tools.mjs";
import { LEANBIO_TOOLS } from "../pipeline/leanbio/tools.mjs";
import { OMICS_TOOLS } from "../sim-engine/tools/omics-tools.mjs";
import { VALIDATE_TOOLS } from "../sim-engine/tools/validate-tools.mjs";

const TOOLS = [];
export const VERSION = "0.6.1";
// Hosted (HTTP) mode never offers tools that run a Lean build or write files.
const HOSTED = !!process.env.DELPHI_HTTP_PORT;

export function createServer() {
  const server = new McpServer({ name: "delphisci", version: VERSION });
  for (const [name, description, inputSchema, fn, annotations = { readOnlyHint: true }] of TOOLS) {
    server.registerTool(name, { description, inputSchema, annotations }, async (args, extra) => {
      const start = performance.now();
      let ok = true;
      try { return json(await fn(args, extra)); }
      catch (e) { ok = false; return { isError: true, content: [{ type: "text", text: String(e?.message ?? e) }] }; }
      finally { observeToolCall(name, ok, (performance.now() - start) / 1000); }
    });
  }
  return server;
}

const source = z.enum(["local", "network"]).default("local").describe(
  `"local" = TriG files in this repo, including unpublished drafts and assessments. "network" = what is published, via ${NETWORK_ENDPOINT}.`);

// Tools built from repo snapshots have no network copy; say so rather than answer from local data.
const localOnly = what => z.enum(["local", "network"]).default("local").describe(`Only "local": ${what} has no published copy to query.`);
const rejectNetwork = (name, fn) => ({ source, ...args }) => {
  if (source === "network") throw new Error(`${name} only reads repo files; source "network" is not supported. Use delphi_search_claims, delphi_get_claim, delphi_rank_claims or delphi_sparql for published data.`);
  return fn(args);
};

// A result with a `markdown` field is sent as that text first, so clients show a readable table,
// followed by the rest as JSON.
const json = ({ markdown, ...data }) => ({ content: [
  ...(markdown ? [{ type: "text", text: markdown }] : []),
  { type: "text", text: JSON.stringify(data, null, 2) },
] });
const tool = (...spec) => TOOLS.push(spec);

tool("delphi_overview",
  "Start here. Counts claims per domain (and how many carry math in skos:notation), lists the assessment types you can rank by, and gives the claim graph's status per thinker: theorems, math claims, Lean-checked, proved in the literature, refuted, and claims tested against data with their verdicts (supports, mixed, refutes, inconclusive) and how many were tested on organisms, with links that open docs/claim-graph.html filtered to each count. For test details or what to test next, use delphi_claim_tests.",
  { source },
  ({ source }) => overviewWithGraph(source));

tool("delphi_search_claims",
  "Find claims by text (matched against title, statement and math) and/or domain. Returns each claim's IRI, title, statement, LaTeX math, nanopub and `status`: whether it is proved (Lean-checked or in the literature), its data-test verdict, and whether it is published. Claims with a completed data test also carry `testContract` (expected observation, disconfirming observation, admissible dataset constraints, inference method; `explicit` is false when derived from the pre-registration fields) and any `revisions` of the verdict with who prompted them. To filter by status, use delphi_graph.",
  {
    text: z.string().optional().describe("Case-insensitive substring, e.g. \"fixation\" or \"\\\\sqrt\""),
    domain: z.string().optional().describe("Substring of the domain IRI, e.g. \"math\", \"turing\", \"darwin\""),
    mathOnly: z.boolean().default(false).describe("Only claims that have a formal statement (skos:notation)"),
    limit: z.number().int().min(1).max(500).default(20),
    source,
  },
  searchClaimsWithStatus);

tool("delphi_get_claim",
  "Everything about one claim: all assertion fields (statement, math, assumptions/context, proposed test, sources), every assessment with its per-dimension scores, and `status`: proof (Lean theorems or literature), data-test verdict with its result file, and publication registry.",
  {
    id: z.string().describe("Claim IRI or its short id, e.g. \"fisher-kpp-speed\" or \"darwin1859-ch09-03\""),
    source,
  },
  getClaimWithStatus);

tool("delphi_rank_claims",
  "Rank claims by an assessment type: mean overall score across assessors (one score per assessor), with assessor count, spread (max - min, i.e. disagreement), verdict counts and each claim's proof/data-test `status`. Omit `type` to list the available types.",
  {
    type: z.string().optional().describe("Assessment type, e.g. \"dataset-resolvability/0.1.0\""),
    domain: z.string().optional().describe("Substring of the domain IRI"),
    minAssessors: z.number().int().min(1).default(1),
    limit: z.number().int().min(1).max(500).default(20),
    source,
  },
  rankClaimsWithStatus);

tool("delphi_graph",
  "The claim graph from docs/claim-graph.html. With no arguments, returns its verification status table: per thinker, how many claims are theorems, math claims, Lean-checked, proved in the literature, partly proved, unverified or refuted, as markdown with every count linking to the graph filtered to it. With filters (or view: \"claims\"), lists claims (including drafts) with thinker, year, work, verification, math/theorem flags, testability and model truth scores (p_true per model, mean `truth`, `disagreement` = max - min), each with a `graph` link that opens it in the page; or groupBy for counts and means. Truth scores are unpublished opinions, not verification; `built` says when the snapshot was made.",
  {
    view: z.enum(["status", "claims"]).optional().describe("status = the per-thinker verification table (default when no filters are given); claims = list claims"),
    text: z.string().optional().describe("Case-insensitive substring of title, statement or quote"),
    thinker: z.string().optional().describe("Substring, e.g. \"darwin\", \"turing\""),
    work: z.string().optional().describe("Substring of the work title"),
    status: z.enum(["untested", "proved", "partial", "refuted"]).optional(),
    verification: z.enum(["lean", "literature", "partial", "untested", "refuted"]).optional()
      .describe("Status with proved split by how: lean = machine-checked in Lean 4, literature = proved in the literature"),
    evidence: z.enum(["supports", "mixed", "refutes", "inconclusive", "any", "none"]).optional()
      .describe("Data-test verdict; any = tested, none = not tested"),
    evidenceKind: z.enum(["biological", "physical", "computational", "none"]).optional()
      .describe("What the test's data measured: biological = organisms (shows the claim holds in biology), computational = simulation or mathematics. E.g. math: true, evidence: \"supports\", evidenceKind: \"biological\" lists math shown to hold in organisms"),
    morpholib: z.enum(["tests", "models", "any"]).optional()
      .describe("Only claims linked to a MorphoEval audit in github.com/fractastical/morpholib: tests = it measured the claim's assertion on specimens, models = it simulates the claim's mechanism"),
    math: z.boolean().optional().describe("true = only math claims (formal notation, a Lean formalization, or a mathematical kind)"),
    theorem: z.boolean().optional().describe("true = only theorems: math claims that are Lean-checked or proved in the literature"),
    formalization: z.enum(["one", "several", "identity", "contingent", "not-mathematical", "any", "none"]).optional()
      .describe("How a math claim maps onto formal statements: one = a single agreed formalization; several = non-equivalent readings (listed in formalization.readings), so a proof of one says nothing about the others; identity = provable from the model's own bookkeeping, true and uninformative about organisms; contingent = a dataset can touch it; not-mathematical; any = classified; none = not yet classified. A claim can carry several tags (the Price equation is identity + contingent)"),
    kind: z.string().optional().describe("Substring of the claim kind, e.g. \"mechanism\", \"theorem\""),
    yearFrom: z.number().int().optional(),
    yearTo: z.number().int().optional(),
    minTruth: z.number().min(0).max(1).optional(),
    maxTruth: z.number().min(0).max(1).optional(),
    minTruthAssessors: z.number().int().min(0).default(0).describe("Only claims scored by at least this many models"),
    published: z.boolean().optional().describe("true = only claims on the production nanopub registry; false = only unpublished/test"),
    sort: z.enum(SORT_KEYS).default("truth").describe("truth (high first), truth-asc, disagreement, testability, year"),
    groupBy: z.enum(GROUP_KEYS).optional().describe("Return per-group counts and means instead of claims"),
    limit: z.number().int().min(1).max(500).default(20),
    source: localOnly("the claim graph (docs/claims.json)"),
  },
  rejectNetwork("delphi_graph", browseClaims));

tool("delphi_claim_tests",
  "Tests of claims against data (test-data/claim-tests/): how many claims are tested, with what verdicts, on what kind of data, and which to test next. view \"summary\" (default with no arguments) = counts per thinker by verdict and data kind, plus pre-registered tests awaiting data; \"list\" = test runs with filters, each with hypothesis and a GitHub link to its result.json; \"claim\" = every run for one claim id with the full result.json (criteria, datasets with checksums, method, measured values, caveats); \"candidates\" = untested claims ranked by testability, i.e. what to test next, each with its dataset-scouting status and located datasets when a scout has checked it. A claim with several runs counts once in the summary. Only dataKind \"biological\" shows a claim holds in organisms.",
  {
    view: z.enum(TEST_VIEWS).optional().describe("summary | list | claim | candidates. Defaults to claim if id is given, list if any filter is given, else summary"),
    id: z.string().optional().describe("Claim id for view \"claim\", e.g. \"darwin1859-ch12-11\""),
    thinker: z.string().optional().describe("Substring, e.g. \"darwin\", \"levin\""),
    project: z.string().optional().describe("Substring of the test project, e.g. \"wolfram-nks\""),
    verdict: z.enum(TEST_VERDICTS).optional(),
    dataKind: z.enum(TEST_DATA_KINDS).optional().describe("biological = organisms; physical; computational = simulation or mathematics; none"),
    status: z.enum(["complete", "preregistered", "abandoned", "any"]).optional().describe("For view \"list\"; default complete"),
    math: z.boolean().optional().describe("true = only math claims"),
    minTestability: z.number().min(0).max(1).optional().describe("For view \"candidates\""),
    scouted: z.enum(["data-ready", "partial", "gap", "not-empirically-resolvable", "any", "none"]).optional().describe("For view \"candidates\": filter by dataset-scouting status (test-data/dataset-scouting/), i.e. whether public data for the claim has been located"),
    sort: z.enum(["testability", "data"]).optional().describe("For view \"candidates\": \"data\" puts claims whose data has been located first"),
    text: z.string().optional().describe("Substring of claim id, title, statement or hypothesis"),
    limit: z.number().int().min(1).max(500).optional(),
    source: localOnly("test-data/claim-tests"),
  },
  rejectNetwork("delphi_claim_tests", claimTestsTool));

tool("delphi_morpholib",
  "MorphoEval audits from github.com/fractastical/morpholib: published morphogenesis models (Turing, Murray, Vogel, Raup, Thompson's transformations, ...) run against real specimens, each a claim nanopub with rubric assessments, and which claims here they test (measured the claim's assertion on specimens) or model (simulate its mechanism). view \"summary\" (default) = counts by registry, verdict and relation; \"list\" = audits with filters; \"audit\" = one audit with its linked claims; \"claim\" = the audits linked to one delphisci claim id; \"live\" = what is published on the network now, and what test-data/morpholib/links.json is missing. An audit's verdict grades the simulation, not the claim; thompsonVerdict is the verdict on Thompson's claim.",
  {
    view: z.enum(MORPHOLIB_VIEWS).optional().describe("Defaults to audit or claim if id is given, list if any filter is given, else summary"),
    id: z.string().optional().describe("Audit id (e.g. \"thompson1917-t1917-027\", \"vogel-phyllotaxis\") or a delphisci claim id (e.g. \"thompson1917-ch11-08\")"),
    text: z.string().optional().describe("Substring of audit id, label, organism or Thompson claim"),
    registry: z.enum(REGISTRIES).optional(),
    verdict: z.string().optional().describe("Substring of the audit verdict, e.g. \"mostly\", \"not faithful\""),
    relation: z.enum(RELATIONS).optional().describe("tests / models = audits with such a link; any = linked; none = linked to no claim here"),
    thompson: z.boolean().optional().describe("true = only audits of a specific Thompson (1917) claim"),
    thinker: z.string().optional().describe("Only audits linked to a claim by this thinker, e.g. \"thompson\""),
    sort: z.enum(["score", "woe", "links"]).optional().describe("score (default), woe = weight of evidence, links = most linked"),
    limit: z.number().int().min(1).max(500).optional(),
  },
  morpholibTool);

tool("delphi_replications",
  "Independent re-runs of a claim's Lean proof or data test, as signed attestations (ed25519, content-addressed, verified here), and what they add up to. Without `claim`: how many claims with an executable test are replicated, contested, single-witness or unattested, and which have witnesses. With `claim`: each of its tests with every witness (signer, operator, outcome, time, repo commit). Status counts only attestations of the test's current hash, one vote per signer, quorum over distinct operators: replicated = quorum or more operators reproduced it and none diverged; contested = some reproduced and some drifted or failed; single-witness = fewer than quorum; stale-only = witnesses exist but the test has since changed. Signers are keys, not verified people, and operators are self-declared: pass `trusted` to count only keys you choose. includePeers also asks this node's configured peers (mcp/peers.json, DELPHI_PEERS) and verifies what they return. To add a witness, re-run with `node scripts/exec/run.mjs --claim ID`, then `node scripts/federation/cli.mjs attest`.",
  {
    claim: z.string().optional().describe("Claim id, e.g. \"darwin1859-ch01-09\""),
    quorum: z.number().int().min(1).max(20).default(2).describe("Distinct operators that must reproduce a test for status \"replicated\""),
    trusted: z.array(z.string().regex(/^ed25519:[0-9a-f]{64}$/)).max(200).optional().describe("Only count attestations signed by these public keys (\"ed25519:<hex>\")"),
    includePeers: z.boolean().default(false).describe("Also query this node's configured federation peers"),
  },
  replicationsTool);

const axis = z.enum(AXIS_IDS);
tool("delphi_organisms",
  "Rank or filter the animal taxa Darwin and Thompson mention (test-data/organisms/merged) by dataset coverage: score 0-100 = weighted share of data axes with a vendored dataset (genome graded by assembly level, bioelectric, barcode, traits, morphology3d, phylogeny, occurrence, fossil, conservation, taxonomy). Call with no filters for the overview, or e.g. hasAxis=[genome] missingAxis=[traits]. Measures completeness of our records, not dataset reliability.",
  {
    text: z.string().optional().describe("Substring of accepted name or slug"),
    taxonClass: z.string().optional().describe("Substring of class/phylum, e.g. \"Aves\", \"Gastropoda\""),
    rank: z.string().optional().describe("Exact rank, e.g. \"species\", \"genus\", \"family\""),
    project: z.string().optional().describe("\"darwin\" or \"thompson\""),
    hasAxis: z.array(axis).default([]).describe("Only taxa covered on all these axes"),
    missingAxis: z.array(axis).default([]).describe("Only taxa with no dataset on any of these axes"),
    genomeLevel: z.enum(["complete", "chromosome", "scaffold", "contig", "none"]).optional(),
    minScore: z.number().min(0).max(100).optional(),
    maxScore: z.number().min(0).max(100).optional(),
    minMentions: z.number().int().min(0).default(0),
    sort: z.enum(ORG_SORT_KEYS).default("score").describe("score (high first), score-asc, mentions, datasets, name"),
    groupBy: z.enum(ORG_GROUP_KEYS).optional().describe("Return per-group counts, mean score and axis coverage instead of taxa"),
    overview: z.boolean().default(false).describe("Return axis-level totals for the whole set instead of taxa"),
    limit: z.number().int().min(1).max(1000).default(20),
    source: localOnly("the organism set (test-data/organisms/merged)"),
  },
  rejectNetwork("delphi_organisms", ({ overview, ...args }) => (overview ? organismsOverview() : browseOrganisms(args))));

tool("delphi_get_organism",
  "One taxon: identifiers (GBIF/NCBI/Wikidata/WoRMS), lineage, names as written, coverage score and missing axes, every dataset record (with counts, distributions, integrity) and every located mention in the books.",
  {
    id: z.string().describe("Taxon key (gbif:2495414), slug (columba-livia), accepted name or vernacular"),
    includeMentions: z.boolean().default(true),
    source: localOnly("the organism set (test-data/organisms/merged)"),
  },
  rejectNetwork("delphi_get_organism", getOrganism));

tool("delphi_sparql",
  `Run a read-only SPARQL query. SELECT returns rows, ASK { boolean }, CONSTRUCT and DESCRIBE { triples } as N-Triples. Nanopubs are named graphs: join GRAPH ?h { ?np np:hasAssertion ?a } with GRAPH ?a { ... }. Each of these prefixes is added unless the query declares it:\n${PREFIXES}`,
  { query: z.string(), source },
  ({ query, source }) => sparql(query, source));

const WRITE = { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true };
const apiKey = z.string().optional().describe("Forum API key from delphi_forum_register. Optional if the client sends X-Claw-Api-Key or, locally, if credentials are saved.");
const claimIds = z.array(z.string()).describe("delphisci claim ids, e.g. [\"levin-2022-tame-19\"]; find them with delphi_search_claims");

tool("delphi_forum_read",
  `Read the Science Claw forum (${FORUM_URL}), where agents log tests, proposed claims and requests for collaborators. view "claim" = every post tagged with a claim id (tests, discussion, requests); "requests" = open calls for help; "feed" = latest posts; "search" = full text; "post" = one post with comments; "leaderboard" = agents ranked by points (claims tested, proposals, artifacts, collaborations, karma) with their GitHub repos and how many of their tests were merged into the repo, plus who produced the tests in test-data/claim-tests. Posts logged through delphi_propose_claim or delphi_log_test_result come back with \`structured\` (the claims.json or result.json payload).`,
  {
    view: z.enum(["claim", "requests", "feed", "search", "post", "leaderboard"]).default("feed"),
    rankBy: z.enum(LEADERBOARD_SORTS).optional().describe("For view \"leaderboard\": points (default), tests, proposals, karma"),
    claim: z.string().optional().describe("Claim id for view \"claim\""),
    q: z.string().optional().describe("Query for view \"search\""),
    postId: z.string().optional().describe("Post id for view \"post\""),
    lab: z.string().optional().describe("Feed filter: general, artifacts, collab, claims, datasets, math, organisms, tooling, results"),
    kind: z.enum(["artifact", "request", "result", "question", "discussion"]).optional(),
    status: z.enum(REQUEST_STATUSES).optional(),
    sort: z.enum(["new", "hot", "top"]).optional(),
    limit: z.number().int().min(1).max(100).default(25),
  },
  forumRead,
  { readOnlyHint: true, openWorldHint: true });

tool("delphi_forum_register",
  "Register an agent on the Science Claw forum and get its API key (shown once). Needed before any forum write. Run locally, the key is saved for later calls if no credentials exist yet.",
  {
    name: z.string().min(2).max(32).describe("Agent handle"),
    description: z.string().max(500).describe("What the agent does"),
    skills: z.array(z.string()).default([]).describe("e.g. [\"bioinformatics\", \"lean4\"]"),
    links: z.array(z.string()).default([]),
  },
  forumRegister,
  WRITE);

tool("delphi_propose_claim",
  "Propose a new candidate law of biology for the claim set. Posts it to the forum's claims lab as readable text plus a JSON block in the claims.json format (label, claim, quote, source, claim_kind, scope, measurable quantities, candidate data), which maintainers harvest, assess and publish as a nanopub. State the claim as its author did, quote the source, and say what would test it.",
  {
    title: z.string().min(5).max(200).describe("Short label, e.g. \"Cell size scales with genome size across eukaryotes\""),
    statement: z.string().min(20).max(2000).describe("The claim in one or two precise sentences"),
    quote: z.string().max(2000).optional().describe("Verbatim supporting sentence from the source"),
    source: z.object({
      title: z.string(), authors: z.string().optional(), year: z.number().int().optional(),
      doi: z.string().optional(), url: z.string().optional(),
    }).describe("Where the claim is made; give a DOI or URL"),
    section: z.string().optional().describe("Chapter/section/page"),
    kind: z.enum(["empirical-generalization", "mechanism", "prediction", "experimental-result", "simulation-result", "historical-inference", "mathematical", "definition", "other"]),
    scope: z.string().optional().describe("Taxa, systems or conditions the claim covers"),
    math: z.string().optional().describe("LaTeX formal statement, if any"),
    measurableQuantities: z.array(z.string()).optional(),
    candidateData: z.string().optional().describe("Public datasets that could test it"),
    relatedClaims: z.array(z.string()).optional().describe("Existing claim ids it refines, generalises or contradicts"),
    notes: z.string().max(4000).optional(),
    apiKey,
  },
  proposeClaim,
  WRITE);

tool("delphi_log_test_result",
  `Log a test of one or more claims against data or simulation. Posts to the forum's results lab, tagged with the claim ids so it appears on each claim's thread, as text plus a JSON block in the test-data/claim-tests result.json format. Follow the test rules: pass and fail criteria fixed before looking at data (link the pre-registration), only real public data with download URL and SHA-256, numbers produced by a runnable script. verdict: ${VERDICTS.join(", ")}.`,
  {
    claims: claimIds.min(1),
    title: z.string().max(300).optional(),
    project: z.string().optional().describe("Claim project, e.g. levin-papers, darwin-origin"),
    hypothesis: z.string().describe("What must be true of the data if the claim holds"),
    passCriterion: z.string().describe("Pre-registered measured value and threshold that confirm it"),
    failCriterion: z.string().describe("Pre-registered result that refutes it"),
    preregistration: z.string().optional().describe("Link or commit where the criteria were fixed before the analysis"),
    testContract: z.object({
      expected_observation: z.string(), disconfirming_observation: z.string(), admissible_datasets: z.string(), inference_method: z.string(),
    }).optional().describe("What the data should show if the claim holds, what would show it false, constraints a dataset must meet to count, and how the observation becomes a verdict (test-data/claim-tests/README.md)"),
    datasets: z.array(z.object({
      id: z.string(), name: z.string(), landing_url: z.string().optional(), doi: z.string().nullable().optional(),
      version: z.string().optional(), license: z.string().optional(),
      files: z.array(z.object({
        download_url: z.string(), retrieved_at: z.string().optional(), byte_size: z.number().optional(), sha256: z.string().optional(),
      })).default([]),
      role: z.string().optional(),
    })).min(1),
    method: z.string().describe("Two to five sentences: the analysis actually run"),
    measured: z.object({
      value: z.union([z.number(), z.string(), z.null()]), unit: z.string().optional(), n: z.number().optional(),
      uncertainty: z.string().optional(), extra: z.record(z.string(), z.any()).optional(),
    }),
    verdict: z.enum(VERDICTS),
    reason: z.enum(INCONCLUSIVE_REASONS).optional().describe("Required when verdict is inconclusive"),
    dataKind: z.enum(TEST_DATA_KINDS).describe("What the data the verdict rests on measured: biological = organisms (the only kind that shows a claim holds in biology), physical, computational = simulation or mathematics, none = no data used"),
    confidence: z.number().min(0).max(1),
    caveats: z.array(z.string()).optional(),
    codeUrl: z.string().optional().describe("Repo or file with the analysis script that produced `measured`; needed for the test to be merged into the repo"),
    apiKey,
  },
  logTestResult,
  WRITE);

tool("delphi_forum_post",
  "Post a request for collaborators (with the deliverable and skills wanted), a question, a discussion, or an artifact you made (url required), optionally tagged with claim ids. For new claims use delphi_propose_claim; for test results use delphi_log_test_result.",
  {
    kind: z.enum(POST_KINDS),
    title: z.string().min(5).max(300),
    content: z.string().max(40000),
    claims: claimIds.optional(),
    lab: z.string().optional().describe("Defaults: request -> collab, artifact -> artifacts, otherwise general"),
    url: z.string().optional(),
    artifactType: z.enum(ARTIFACT_TYPES).optional(),
    skillsWanted: z.array(z.string()).optional(),
    apiKey,
  },
  forumPost,
  WRITE);

tool("delphi_forum_respond",
  "Act on a forum post: comment (or reply with parentId), offer to collaborate on a request (content = what you will deliver), set a request's status (author only), or upvote/downvote.",
  {
    action: z.enum(["comment", "offer", "status", "upvote", "downvote"]),
    postId: z.string(),
    content: z.string().max(10000).optional(),
    parentId: z.string().optional(),
    skills: z.array(z.string()).optional(),
    status: z.enum(REQUEST_STATUSES).optional(),
    apiKey,
  },
  forumRespond,
  WRITE);

// ── Lean laws ──────────────────────────────────────────────────────────────
// Handlers and descriptions come from sim-engine/tools/lean-tools.mjs, which reads every law through the one
// loader lib/lean-source.mjs (lean/registry/, or lean/laws.json + constraints.json until it exists). Results
// are the provenance envelope { result, provenance, scope }. lean/registry/check-exposed.mjs fails if a law
// is missing here.
const leanT = Object.fromEntries(LEAN_TOOLS.map(t => [t.name, t]));
const lawStatus = z.enum(["proposed", "candidate", "accepted", "contested", "retired"]);
const leanTool = (name, shape) => tool(name, leanT[name].description, shape, args => leanT[name].handler(args));

leanTool("lean_laws_list", {
  kind: z.enum(["physical", "biological"]).optional(),
  status: z.union([lawStatus, z.array(lawStatus)]).optional().describe("One status or a list"),
  scope: z.string().optional().describe("Substring of the law level or scope, e.g. \"genotype\""),
  lawset: z.string().optional().describe("Only laws in this lawset version, or \"current\""),
  text: z.string().optional().describe("Substring of law_id, label or statement"),
});
leanTool("lean_law_get", {
  id: z.string().describe("law_id from lean_laws_list, e.g. \"kimura-substitution-rate\""),
  version: z.string().optional().describe("A specific (e.g. archived) law version; omit for the current one"),
});
leanTool("lean_lawset_get", { version: z.string().default("current").describe("Semver, or \"current\"") });
leanTool("lean_check", {
  design: z.record(z.string(), z.any()).optional().describe("SI-unit design: SL_m, mass_kg, finArea_m2, CLmax, airspeed_m_s, genotype_edits, ..."),
  spec: z.record(z.string(), z.any()).optional().describe("Alias of design"),
  lawset: z.string().default("current"),
});
leanTool("lean_verify", {});
// Self-update: where the laws come from (local files, or a remote mirror/github ref re-checked every TTL), and
// what changed between lawsets. See lean/registry/SELF-UPDATE.md.
leanTool("lean_source_status", {
  refresh: z.boolean().optional().describe("Check the remote now instead of waiting for the TTL (at most once per 30 s)"),
});
leanTool("lean_changes", {
  since_version: z.string().optional().describe("Lawset version you last saw, e.g. \"1.3.0\" (exclusive), or \"current\"; omit for all releases"),
});
if (!HOSTED) leanTool("lean_propose", {
  file: z.string().optional().describe("Path to a .lean file"),
  source: z.string().optional().describe("Lean source text, if no file"),
  meta: z.record(z.string(), z.any()).default({}).describe("law_id, kind, statement_en, hypotheses, sources (see lean/registry/README.md)"),
});

// LeanBio: the formalization queue, grounding, and per-claim records (pipeline/leanbio/). Read-only; leanbio_ground
// calls Gilda / MyGene.info / OLS4 on a cache miss unless offline is set. In hosted mode it is forced offline so the
// public server makes no outbound calls on behalf of anonymous clients and never writes the cache.
const lb = Object.fromEntries(LEANBIO_TOOLS.map(t => [t.name, t]));
tool("leanbio_queue", lb.leanbio_queue.description, {
  limit: z.number().int().min(1).max(500).default(20),
  min_belief: z.number().min(0).max(1).optional().describe("Only items at or above this belief"),
  relation: z.string().optional().describe("Relation type, e.g. ScalingLaw, Bound, Equality, Dynamics, Inhibition"),
  origin: z.enum(["claim", "draft"]).optional(),
}, args => lb.leanbio_queue.handler(args));
tool("leanbio_ground", lb.leanbio_ground.description, {
  text: z.string().optional().describe("Free text to annotate"),
  entity: z.string().optional().describe("One entity name or identifier, instead of text"),
  kind: z.enum(["any", "gene", "taxon"]).default("any"),
  context: z.string().optional().describe("Context for an entity, e.g. \"zebrafish\""),
  offline: z.boolean().default(false).describe("Answer from the cache only"),
}, args => lb.leanbio_ground.handler({ ...args, offline: HOSTED ? true : args.offline }));
tool("leanbio_claim", lb.leanbio_claim.description, {
  id: z.string().describe("Claim id (docs/claims.json), e.g. \"maynardsmith-hitchhiking\", or \"draft:<repo path>\""),
  draft: z.boolean().default(true).describe("Include the unsigned nanopub draft (TriG)"),
}, args => lb.leanbio_claim.handler(args));

// Multi-omics cards (sim-engine/tools/omics-tools.mjs over omics/index/, shipped in the image and the npm package).
// Proxy-species data, kind borrowed; absence means not recorded.
const om = Object.fromEntries(OMICS_TOOLS.map(t => [t.name, t]));
const omicsLayer = z.enum(["genomic", "transcriptomic", "proteomic", "pathway", "ptm"]);
tool("omics_gene", om.omics_gene.description, {
  symbol: z.string().optional().describe("ZFIN symbol (e.g. kcnk5b), ZDB-GENE id, or human orthologue symbol (e.g. KCNK5)"),
  id: z.string().optional().describe("Alias of symbol"),
  layers: z.array(omicsLayer).optional().describe("Only these layers (default all)"),
  features: z.array(z.string()).optional().describe("Only these features, e.g. allele_phenotype, expressed_in"),
}, args => om.omics_gene.handler(args));
tool("omics_part", om.omics_part.description, {
  part_id: z.string().describe("UBERON:xxxxxxx or CL:xxxxxxx (underscore form accepted)"),
  layer: omicsLayer.optional(),
  limit: z.number().optional().describe("Max genes returned (default 100)"),
}, args => om.omics_part.handler(args));
tool("omics_search", om.omics_search.description, {
  term: z.string().describe("e.g. \"pectoral fin\", \"GO:0030326\", \"Wnt signaling\""),
  feature: z.string().optional(),
  layer: omicsLayer.optional(),
  limit: z.number().optional().describe("Max matching terms (default 25)"),
}, args => om.omics_search.handler(args));

// The design score (scorer v1.0.0, weights frozen: sim-engine/validate/score-weights.json and
// SCORER-PREREGISTRATION.md). In hosted mode network and BLAST are forced off: the public server answers from its
// shipped data and cache, makes no outbound calls for anonymous clients, and never runs minutes-long BLAST jobs.
const dsc = VALIDATE_TOOLS.find(t => t.name === "design_score");
tool("design_score", dsc.description, {
  organism: z.union([z.string(), z.record(z.string(), z.any())]).optional().describe("A repository organism/design id (zebrafish-adult, flying-fish, winged-zebrafish, tff, ...) or an inline organism document"),
  specimen: z.record(z.string(), z.any()).optional().describe("Instead of an organism: a raw specimen record {SL_m, mass_kg, depth_SL, ...}"),
  ageDays: z.number().optional(),
  conditions: z.record(z.string(), z.any()).optional(),
  exclude: z.array(z.string()).optional().describe("Reference ids or groups to leave out of the nearest-neighbour search"),
  reference_set_excluding: z.array(z.string()).optional().describe("Leave-out scoring (e.g. organism:zebrafish); use it whenever the design IS a real organism"),
  containment: z.array(z.record(z.string(), z.any())).optional().describe("partedit.js containment results [{part, refused}]"),
  network: z.boolean().optional().describe("Allow cached network calls (forced off on the hosted server)"),
  blast: z.boolean().optional().describe("Run NCBI BLAST for genes without an alignment (forced off on the hosted server)"),
  lawset: z.string().optional(),
  taxon: z.string().optional(),
  label: z.string().optional(),
  spec: z.record(z.string(), z.any()).optional().describe("Optional DesignSpec for the S component"),
}, args => dsc.handler(HOSTED ? { ...args, network: false, blast: false } : args));

if (process.env.DELPHI_HTTP_PORT) {
  const { serveHttp } = await import("./http.mjs");
  serveHttp(createServer, Number(process.env.DELPHI_HTTP_PORT), VERSION);
} else {
  await createServer().connect(new StdioServerTransport());
}
