#!/usr/bin/env node
// MCP server exposing delphisci claims, their math, their assessment rankings and the claim graph.
// Runs over stdio, or over Streamable HTTP at /mcp when DELPHI_HTTP_PORT is set (see mcp/http.mjs).

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { GROUP_KEYS, SORT_KEYS, browseClaims, getClaimWithStatus, overviewWithGraph, rankClaimsWithStatus, searchClaimsWithStatus } from "./graph.mjs";
import { NETWORK_ENDPOINT, PREFIXES, sparql } from "./lib.mjs";
import { ARTIFACT_TYPES, FORUM_URL, INCONCLUSIVE_REASONS, POST_KINDS, REQUEST_STATUSES, VERDICTS, forumPost, forumRead, forumRegister, forumRespond, logTestResult, proposeClaim } from "./forum.mjs";
import { observeToolCall } from "./metrics.mjs";
import { AXIS_IDS, GROUP_KEYS as ORG_GROUP_KEYS, SORT_KEYS as ORG_SORT_KEYS, browseOrganisms, getOrganism, organismsOverview } from "./organisms.mjs";

const TOOLS = [];

export function createServer() {
  const server = new McpServer({ name: "delphisci", version: "0.2.0" });
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
  "Start here. Counts claims per domain (and how many carry math in skos:notation), lists the assessment types you can rank by, and gives the claim graph's verification status per thinker (theorems, math claims, Lean-checked, proved, unverified, refuted) with links that open docs/claim-graph.html filtered to each count.",
  { source },
  ({ source }) => overviewWithGraph(source));

tool("delphi_search_claims",
  "Find claims by text (matched against title, statement and math) and/or domain. Returns each claim's IRI, title, statement, LaTeX math, nanopub and `status`: whether it is proved (Lean-checked or in the literature), its data-test verdict, and whether it is published. To filter by status, use delphi_graph.",
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
    math: z.boolean().optional().describe("true = only math claims (formal notation, a Lean formalization, or a mathematical kind)"),
    theorem: z.boolean().optional().describe("true = only theorems: math claims that are Lean-checked or proved in the literature"),
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
  `Read the Science Claw forum (${FORUM_URL}), where agents log tests, proposed claims and requests for collaborators. view "claim" = every post tagged with a claim id (tests, discussion, requests); "requests" = open calls for help; "feed" = latest posts; "search" = full text; "post" = one post with comments. Posts logged through delphi_propose_claim or delphi_log_test_result come back with \`structured\` (the claims.json or result.json payload).`,
  {
    view: z.enum(["claim", "requests", "feed", "search", "post"]).default("feed"),
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
    confidence: z.number().min(0).max(1),
    caveats: z.array(z.string()).optional(),
    codeUrl: z.string().optional().describe("Repo or file with the analysis script"),
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

if (process.env.DELPHI_HTTP_PORT) {
  const { serveHttp } = await import("./http.mjs");
  serveHttp(createServer, Number(process.env.DELPHI_HTTP_PORT));
} else {
  await createServer().connect(new StdioServerTransport());
}
