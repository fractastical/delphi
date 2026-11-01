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
//   node mcp/cli.mjs tests                              (claims tested against data, by verdict and data kind)
//   node mcp/cli.mjs tests list --verdict refutes --data-kind biological
//   node mcp/cli.mjs tests claim --id darwin1859-ch12-11
//   node mcp/cli.mjs tests candidates --thinker thompson --math   (untested, by testability)
//   node mcp/cli.mjs organisms --overview
//   node mcp/cli.mjs organisms --has-axis genome --missing-axis traits --rank species
//   node mcp/cli.mjs organisms --group-by class
//   node mcp/cli.mjs organism columba-livia
//   node mcp/cli.mjs morpholib                         (MorphoEval audits and the claims they test or model)
//   node mcp/cli.mjs morpholib list --relation tests --thinker thompson
//   node mcp/cli.mjs morpholib --id thompson1917-ch11-08
//   node mcp/cli.mjs morpholib live                     (what is published now vs test-data/morpholib/links.json)
//   node mcp/cli.mjs replications [claim-id] [--quorum 2] [--trusted ed25519:..] [--peers]
//   node mcp/cli.mjs forum --view claim --claim levin-2022-tame-19
//   node mcp/cli.mjs forum --view requests
//   node mcp/cli.mjs propose-claim proposal.json      (fields as in delphi_propose_claim)
//   node mcp/cli.mjs log-result result.json            (fields as in delphi_log_test_result)
//   node mcp/cli.mjs laws --kind biological --status accepted     (Lean laws; same handlers as sim-engine/lean-cli.mjs)
//   node mcp/cli.mjs law kimura-substitution-rate
//   node mcp/cli.mjs lawset current
//   node mcp/cli.mjs check design.json --lawset current
//   node mcp/cli.mjs propose Law.lean --meta meta.json
//   node mcp/cli.mjs verify
//   node mcp/cli.mjs source [--refresh]                         (Lean law source: local, or remote mirror/github)
//   node mcp/cli.mjs changes 1.3.0                              (lawset releases after 1.3.0)

import { readFileSync } from "node:fs";
import { replicationsTool } from "./federation.mjs";
import { forumRead, logTestResult, proposeClaim } from "./forum.mjs";
import { browseClaims, getClaimWithStatus, overviewWithGraph, rankClaimsWithStatus, searchClaimsWithStatus } from "./graph.mjs";
import { sparql } from "./lib.mjs";
import { browseOrganisms, getOrganism, organismsOverview } from "./organisms.mjs";
import { morpholibTool } from "./morpholib.mjs";
import { claimTestsTool } from "./tests.mjs";
import { COMMANDS as LEAN } from "../sim-engine/lean-cli.mjs";

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
  tests: () => claimTestsTool({ view: positional[0], ...opts }),
  morpholib: () => morpholibTool({ view: positional[0], ...opts }),
  replications: () => replicationsTool({ claim: positional[0] ?? opts.claim, quorum: opts.quorum, trusted: opts.trusted ? String(opts.trusted).split(",") : undefined, includePeers: Boolean(opts.peers) }),
  organism: () => getOrganism({ id: positional[0] ?? opts.id, includeMentions: opts.includeMentions !== false }),
  forum: () => forumRead({ view: positional[0] ?? opts.view ?? "feed", limit: 25, ...opts }),
  "propose-claim": () => proposeClaim(JSON.parse(readFileSync(positional[0], "utf8"))),
  "log-result": () => logTestResult(JSON.parse(readFileSync(positional[0], "utf8"))),
};
// Lean law subcommands: parsed again from raw argv by the shared CLI so numbers stay strings (lawset "1.2.0").
const { parseArgs } = await import("../sim-engine/lean-cli.mjs");
for (const [name, fn] of Object.entries(LEAN)) commands[name] = () => fn(parseArgs(rest));
// LeanBio subcommands (pipeline/leanbio/tools.mjs), for parity with the leanbio_* MCP tools.
const { LEANBIO_TOOLS } = await import("../pipeline/leanbio/tools.mjs");
const lb = Object.fromEntries(LEANBIO_TOOLS.map(t => [t.name, t]));
commands["leanbio-queue"] = () => lb.leanbio_queue.handler({ limit: Number(positional[0] || 20) });
commands["leanbio-ground"] = () => lb.leanbio_ground.handler({ text: positional.join(" ") });
commands["leanbio-claim"] = () => lb.leanbio_claim.handler({ id: positional[0] });

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
