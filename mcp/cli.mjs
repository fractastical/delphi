#!/usr/bin/env node
// Same queries as the MCP server, for agents and people without MCP. Prints JSON.
//
//   node mcp/cli.mjs overview [--source network]
//   node mcp/cli.mjs search --text fixation --math-only
//   node mcp/cli.mjs claim fisher-kpp-speed
//   node mcp/cli.mjs rank --type dataset-resolvability/0.1.0 --limit 10
//   node mcp/cli.mjs graph --thinker turing --sort disagreement
//   node mcp/cli.mjs graph --group-by thinker
//   node mcp/cli.mjs sparql 'SELECT ...'

import { browseClaims } from "./graph.mjs";
import { getClaim, overview, rankClaims, searchClaims, sparql } from "./lib.mjs";

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
  overview: () => overview(opts.source),
  search: () => searchClaims({ text: positional[0], ...opts }),
  claim: () => getClaim({ id: positional[0] ?? opts.id, source: opts.source }),
  rank: () => rankClaims({ type: positional[0], ...opts }),
  graph: () => browseClaims({ text: positional[0], ...opts }),
  sparql: () => sparql(positional[0] ?? opts.query, opts.source),
};

if (!commands[cmd]) {
  console.error(`Usage: node mcp/cli.mjs <${Object.keys(commands).join("|")}> [args] [--source local|network]`);
  process.exit(1);
}
try {
  console.log(JSON.stringify(await commands[cmd](), null, 2));
} catch (e) {
  console.error(e?.message ?? e);
  process.exit(1);
}
