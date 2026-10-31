#!/usr/bin/env node
// Delfie on Moltbook (https://www.moltbook.com), the social network for AI agents.
// Thin client for the Moltbook API. Because some venue networks reset TLS to moltbook.com,
// requests can be relayed through our Fly machine with --relay (uses `fly ssh console`).
//
//   node plugins/agent/moltbook.mjs status                     # claim status
//   node plugins/agent/moltbook.mjs home                       # dashboard: notifications, feed
//   node plugins/agent/moltbook.mjs feed sort=new limit=10 [submolt=science]
//   node plugins/agent/moltbook.mjs search q="biology agents" [type=posts]
//   node plugins/agent/moltbook.mjs post submolt=general title="..." content="..." [url=...]
//   node plugins/agent/moltbook.mjs post-get <id>              # post + comments
//   node plugins/agent/moltbook.mjs comment <postId> content="..." [parent_id=...]
//   node plugins/agent/moltbook.mjs upvote <postId> | follow <name> | subscribe <submolt> | submolts
//   node plugins/agent/moltbook.mjs verify verification_code=... answer=...
//   node plugins/agent/moltbook.mjs raw GET /agents/me
//
// Credentials: MOLTBOOK_API_KEY, or ~/.config/moltbook/credentials.json {"api_key": ...}.
// Add --relay to run the HTTP call on the Fly app (MOLTBOOK_RELAY_APP, default delphisci-mcp).

import { readFileSync } from "node:fs";
import { homedir } from "node:os";
import { join } from "node:path";
import { spawnSync } from "node:child_process";

const BASE = "https://www.moltbook.com/api/v1";
let creds = {};
try { creds = JSON.parse(readFileSync(join(homedir(), ".config", "moltbook", "credentials.json"), "utf8")); } catch {}
const KEY = process.env.MOLTBOOK_API_KEY ?? creds.api_key;
if (!KEY) { console.error("No API key: set MOLTBOOK_API_KEY or ~/.config/moltbook/credentials.json"); process.exit(1); }

const args = process.argv.slice(2);
const relay = args.includes("--relay") || process.env.MOLTBOOK_RELAY === "1";
const [cmd, ...rest] = args.filter((a) => a !== "--relay");
const isKv = (a) => /^[a-z_]+=/i.test(a) && !a.startsWith("/");
const positional = rest.filter((a) => !isKv(a));
const kv = Object.fromEntries(rest.filter(isKv).map((a) => { const i = a.indexOf("="); return [a.slice(0, i), a.slice(i + 1)]; }));
const qs = (o) => { const u = new URLSearchParams(o); const s = u.toString(); return s ? "?" + s : ""; };

// Runs the request either locally or inside the Fly machine; returns { status, body }.
async function request(method, path, body) {
  const code = `const r = await fetch(${JSON.stringify(BASE + path)}, { method: ${JSON.stringify(method)}, headers: { "Authorization": "Bearer " + ${JSON.stringify(KEY)}, "Content-Type": "application/json" }${body ? `, body: ${JSON.stringify(JSON.stringify(body))}` : ""} });
console.log(JSON.stringify({ status: r.status, body: await r.text() }));`;
  if (!relay) {
    const r = await fetch(BASE + path, { method, headers: { Authorization: `Bearer ${KEY}`, "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
    return { status: r.status, body: await r.text() };
  }
  // `fly machine exec` goes through the Fly API (no WireGuard tunnel), so it is the more reliable
  // path; `fly ssh console` is the fallback.
  const app = process.env.MOLTBOOK_RELAY_APP ?? "delphisci-mcp";
  const b64 = Buffer.from(code).toString("base64");
  const nodeCmd = `node --input-type=module -e "import('data:text/javascript;base64,${b64}')"`;
  const attempts = [];
  const machine = process.env.MOLTBOOK_RELAY_MACHINE ?? machineId(app);
  if (machine) attempts.push(["machine", "exec", machine, "-a", app, nodeCmd]);
  attempts.push(["ssh", "console", "-a", app, "-C", nodeCmd]);
  for (const a of attempts) {
    const out = spawnSync("fly", a, { encoding: "utf8", timeout: 60_000 });
    const line = (out.stdout ?? "").split("\n").find((l) => l.startsWith("{\"status\""));
    if (line) return JSON.parse(line);
    console.error(`relay via fly ${a[0]} failed: ${(out.stderr || out.stdout || "").split("\n").find((l) => /error/i.test(l)) ?? "no output"}`);
  }
  throw new Error("relay failed");
}

let cachedMachine;
function machineId(app) {
  if (cachedMachine !== undefined) return cachedMachine;
  const out = spawnSync("fly", ["machine", "list", "-a", app, "--json"], { encoding: "utf8", timeout: 30_000 });
  try { cachedMachine = JSON.parse(out.stdout).find((m) => m.state === "started")?.id ?? null; } catch { cachedMachine = null; }
  return cachedMachine;
}

async function call(method, path, body) {
  const { status, body: text } = await request(method, path, body);
  let json; try { json = JSON.parse(text); } catch { json = { raw: text }; }
  if (status >= 400 || json.success === false) { console.error(`HTTP ${status}`); console.error(JSON.stringify(json, null, 2)); process.exit(1); }
  return json;
}
const out = (j) => console.log(JSON.stringify(j, null, 2));

// Print the id and any verification challenge (de-obfuscated) for created content.
function showChallenge(res) {
  const obj = res.post ?? res.comment ?? res;
  console.log(`${obj.id} status=${obj.verification_status ?? "published"}`);
  const v = obj.verification ?? res.verification;
  if (v) {
    console.log(`  challenge: ${v.challenge_text}`);
    console.log(`  readable : ${v.challenge_text.replace(/[^a-z0-9 ,?.]/gi, "").toLowerCase()}`);
    console.log(`  answer with: node plugins/agent/moltbook.mjs verify${relay ? " --relay" : ""} verification_code=${v.verification_code} answer=<number>`);
  }
  return res;
}

const commands = {
  status: () => call("GET", "/agents/status").then(out),
  me: () => call("GET", "/agents/me").then(out),
  home: () => call("GET", "/home").then(out),
  feed: () => call("GET", "/posts" + qs(kv)).then(out),
  search: () => call("GET", "/search" + qs(kv)).then(out),
  submolts: () => call("GET", "/submolts").then(out),
  subscribe: () => call("POST", `/submolts/${positional[0]}/subscribe`).then(out),
  post: () => call("POST", "/posts", kv).then(out),
  "post-get": async () => { const p = await call("GET", `/posts/${positional[0]}`); const c = await call("GET", `/posts/${positional[0]}/comments`); out({ post: p, comments: c }); },
  comment: () => call("POST", `/posts/${positional[0]}/comments`, kv).then(showChallenge),
  upvote: () => call("POST", `/posts/${positional[0]}/upvote`).then(out),
  follow: () => call("POST", `/agents/${positional[0]}/follow`).then(out),
  verify: () => call("POST", "/verify", kv).then(out),
  notifications: () => call("GET", "/notifications").then(out),
  raw: () => call(positional[0], positional[1], Object.keys(kv).length ? kv : undefined).then(out),
  // Publish drafts from plugins/agent/moltbook-drafts.json: `publish <draftId>` or `publish all`.
  // Prints any verification challenge (de-obfuscated) so it can be answered with `verify`.
  publish: async () => {
    const drafts = JSON.parse(readFileSync(new URL("./moltbook-drafts.json", import.meta.url), "utf8"));
    const chosen = positional[0] === "all" ? drafts : drafts.filter((d) => d.id === positional[0]);
    if (!chosen.length) { console.error(`Drafts: ${drafts.map((d) => d.id).join(", ")}`); process.exit(1); }
    for (const d of chosen) {
      const res = d.type === "post"
        ? await call("POST", "/posts", { submolt_name: d.submolt_name, title: d.title, content: d.content, ...(d.url ? { url: d.url } : {}) })
        : await call("POST", `/posts/${d.post_id}/comments`, { content: d.content, ...(d.parent_id ? { parent_id: d.parent_id } : {}) });
      process.stdout.write(`${d.id}: ${d.type} `);
      showChallenge(res);
    }
  },
};
if (!commands[cmd]) { console.error(`Commands: ${Object.keys(commands).join(", ")}`); process.exit(cmd ? 1 : 0); }
await commands[cmd]();
