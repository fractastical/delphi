#!/usr/bin/env node
// MCP server (stdio) exposing delphisci claims, their math and their assessment rankings.

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { GROUP_KEYS, SORT_KEYS, browseClaims } from "./graph.mjs";
import { NETWORK_ENDPOINT, PREFIXES, getClaim, overview, rankClaims, searchClaims, sparql } from "./lib.mjs";

const server = new McpServer({ name: "delphisci", version: "0.1.0" });

const source = z.enum(["local", "network"]).default("local").describe(
  `"local" = TriG files in this repo, including unpublished drafts and assessments. "network" = what is published, via ${NETWORK_ENDPOINT}.`);

const json = data => ({ content: [{ type: "text", text: JSON.stringify(data, null, 2) }] });
const tool = (name, description, inputSchema, fn) =>
  server.registerTool(name, { description, inputSchema, annotations: { readOnlyHint: true } }, async args => {
    try { return json(await fn(args)); }
    catch (e) { return { isError: true, content: [{ type: "text", text: String(e?.message ?? e) }] }; }
  });

tool("delphi_overview",
  "Start here. Counts claims per domain (and how many carry math in skos:notation), and lists the assessment types you can rank by.",
  { source },
  ({ source }) => overview(source));

tool("delphi_search_claims",
  "Find claims by text (matched against title, statement and math) and/or domain. Returns each claim's IRI, title, statement, LaTeX math and nanopub.",
  {
    text: z.string().optional().describe("Case-insensitive substring, e.g. \"fixation\" or \"\\\\sqrt\""),
    domain: z.string().optional().describe("Substring of the domain IRI, e.g. \"math\", \"turing\", \"darwin\""),
    mathOnly: z.boolean().default(false).describe("Only claims that have a formal statement (skos:notation)"),
    limit: z.number().int().min(1).max(500).default(20),
    source,
  },
  searchClaims);

tool("delphi_get_claim",
  "Everything about one claim: all assertion fields (statement, math, assumptions/context, proposed test, sources) plus every assessment with its per-dimension scores.",
  {
    id: z.string().describe("Claim IRI or its short id, e.g. \"fisher-kpp-speed\" or \"darwin1859-ch09-03\""),
    source,
  },
  getClaim);

tool("delphi_rank_claims",
  "Rank claims by an assessment type: mean overall score across assessors (one score per assessor), with assessor count, spread (max - min, i.e. disagreement) and verdict counts. Omit `type` to list the available types.",
  {
    type: z.string().optional().describe("Assessment type, e.g. \"dataset-resolvability/0.1.0\""),
    domain: z.string().optional().describe("Substring of the domain IRI"),
    minAssessors: z.number().int().min(1).default(1),
    limit: z.number().int().min(1).max(500).default(20),
    source,
  },
  rankClaims);

tool("delphi_graph",
  "The claim graph from docs/claim-graph.html: every claim (including drafts) with thinker, year, work, proof status, testability and model truth scores (p_true per model, mean `truth`, `disagreement` = max - min). Filter, then sort or group by thinker/decade/status. Not nanopub-backed: truth scores are unpublished; `built` says when the snapshot was made.",
  {
    text: z.string().optional().describe("Case-insensitive substring of title, statement or quote"),
    thinker: z.string().optional().describe("Substring, e.g. \"darwin\", \"turing\""),
    work: z.string().optional().describe("Substring of the work title"),
    status: z.enum(["untested", "proved", "partial", "refuted"]).optional(),
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
  },
  browseClaims);

tool("delphi_sparql",
  `Run a read-only SPARQL SELECT. Nanopubs are named graphs: join GRAPH ?h { ?np np:hasAssertion ?a } with GRAPH ?a { ... }. These prefixes are added if the query has none:\n${PREFIXES}`,
  { query: z.string(), source },
  ({ query, source }) => sparql(query, source));

await server.connect(new StdioServerTransport());
