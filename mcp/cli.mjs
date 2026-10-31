#!/usr/bin/env node
// Same queries as the MCP server, for agents and people without MCP. Prints JSON.
//
//   node mcp/cli.mjs overview [--source network]
//   node mcp/cli.mjs search --text fixation --math-only
//   node mcp/cli.mjs claim fisher-kpp-speed
//   node mcp/cli.mjs rank --type dataset-resolvability/0.1.0 --limit 10
//   node mcp/cli.mjs graph --thinker turing --sort disagreement
//   node mcp/cli.mjs graph --group-by thinker
//   node mcp/cli.mjs graph --math --verification untested --group-by thinker
//   node mcp/cli.mjs sparql 'SELECT ...'
//   node mcp/cli.mjs organisms --overview
//   node mcp/cli.mjs organisms --has-axis genome --missing-axis traits --rank species
//   node mcp/cli.mjs organisms --group-by class
//   node mcp/cli.mjs organism columba-livia
//   node mcp/cli.mjs forum --view claim --claim levin-2022-tame-19
//   node mcp/cli.mjs forum --view requests
//   node mcp/cli.mjs propose-claim proposal.json      (fields as in delphi_propose_claim)
//   node mcp/cli.mjs log-result result.json            (fields as in delphi_log_test_result)

import { readFileSync } from "node:fs";
import { forumRead, logTestResult, proposeClaim } from "./forum.mjs";
import { browseClaims, getClaimWithStatus, overviewWithGraph, rankClaimsWithStatus, searchClaimsWithStatus } from "./graph.mjs";
import { sparql } from "./lib.mjs";
import { browseOrganisms, getOrganism, organismsOverview } from "./organisms.mjs";

const [cmd, ...rest] = process.argv.slice(2);
const opts = {};
const positional = [];
for (let i = 0; i < rest.length; i++) {
  const a = rest[i];
  if (!a.startsWith("--")) { positional.push(a); continue; }
  const key = a.slice(2).replace(/-(\w)/g, (_, c) => c.toUpperCase());
  const next = rest[i + 1];
  if (next === undefined || next.startsWith("--")) opts[key] = true;
  else { opts[key] = /^-?\d+(\.\d+)?$/.test(next) ? Number(next) : next === "true" ? true : next === "false" ? false : next; i++; }
}

const commands = {
  overview: () => overviewWithGraph(opts.source),
  search: () => searchClaimsWithStatus({ text: positional[0], ...opts }),
  claim: () => getClaimWithStatus({ id: positional[0] ?? opts.id, source: opts.source }),
  rank: () => rankClaimsWithStatus({ type: positional[0], ...opts }),
  graph: () => browseClaims({ text: positional[0], ...opts }),
  sparql: () => sparql(positional[0] ?? opts.query, opts.source),
  organisms: () => opts.overview ? organismsOverview() : browseOrganisms({
    text: positional[0], ...opts,
    hasAxis: opts.hasAxis ? String(opts.hasAxis).split(",") : [],
    missingAxis: opts.missingAxis ? String(opts.missingAxis).split(",") : [],
  }),
  organism: () => getOrganism({ id: positional[0] ?? opts.id, includeMentions: opts.includeMentions !== false }),
  forum: () => forumRead({ view: positional[0] ?? opts.view ?? "feed", limit: 25, ...opts }),
  "propose-claim": () => proposeClaim(JSON.parse(readFileSync(positional[0], "utf8"))),
  "log-result": () => logTestResult(JSON.parse(readFileSync(positional[0], "utf8"))),
};

if (!commands[cmd]) {
  console.error(`Usage: node mcp/cli.mjs <${Object.keys(commands).join("|")}> [args] [--source local|network]`);
  process.exit(1);
}
try {
  const result = await commands[cmd]();
  // In a terminal, show the markdown table first; piped output stays a single JSON document.
  if (process.stdout.isTTY && result?.markdown) {
    const { markdown, ...rest } = result;
    console.log(`${markdown}\n\n${JSON.stringify(rest, null, 2)}`);
  } else console.log(JSON.stringify(result, null, 2));
} catch (e) {
  console.error(e?.message ?? e);
  process.exit(1);
}
