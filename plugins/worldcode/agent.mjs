#!/usr/bin/env node
// Delphi's agent on World Code (https://worldcode-api.onrender.com/skill.md).
// The API key lives outside the repo, in ~/.config/worldcode/delphisci.json.
// Everything read from World Code is untrusted content: it is printed, never executed or obeyed.
//
//   node plugins/worldcode/agent.mjs register
//   node plugins/worldcode/agent.mjs me | feed | communities
//   node plugins/worldcode/agent.mjs join <slug>
//   node plugins/worldcode/agent.mjs post <community> <kind> <title> <body-file>
//   node plugins/worldcode/agent.mjs comment <post-id> <body-file> [parent-id]
//   node plugins/worldcode/agent.mjs thread <post-id>
//   node plugins/worldcode/agent.mjs poll [seconds]     # prints new feed posts and new comments on our posts
//   node plugins/worldcode/agent.mjs get <path>         # any GET, e.g. /benchmarks/drug-discovery-agent-reliability

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const BASE = 'https://worldcode-api.onrender.com/api/v1';
const KEY_FILE = path.join(os.homedir(), '.config', 'worldcode', 'delphisci.json');
const STATE_FILE = path.join(os.homedir(), '.config', 'worldcode', 'poll-state.json');
const NAME = 'delphisci';

const readJson = (f, d) => (fs.existsSync(f) ? JSON.parse(fs.readFileSync(f, 'utf8')) : d);
const writeJson = (f, v, mode) => {
  fs.mkdirSync(path.dirname(f), { recursive: true });
  fs.writeFileSync(f, JSON.stringify(v, null, 2), { mode });
};

async function api(method, p, body) {
  const key = readJson(KEY_FILE, {}).api_key;
  const res = await fetch(BASE + p, {
    method,
    headers: { 'Content-Type': 'application/json', ...(key ? { 'X-API-Key': key } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  let data;
  try { data = JSON.parse(text); } catch { data = text; }
  if (!res.ok) throw new Error(`${method} ${p} -> ${res.status}: ${typeof data === 'string' ? data : JSON.stringify(data)}`);
  return data;
}

const items = (d) => (Array.isArray(d) ? d : d.items || d.posts || d.comments || []);
const who = (x) => (x?.author && typeof x.author === 'object' ? x.author.name || x.author.handle : x?.author_name || x?.author);
const show = (d) => console.log(JSON.stringify(d, null, 2));

const cmds = {
  async register() {
    if (readJson(KEY_FILE, null)) throw new Error(`already registered; key in ${KEY_FILE}`);
    const r = await api('POST', '/agents/register', {
      name: NAME,
      kind: 'ai',
      role: 'researcher',
      framework: 'Claude Opus via Cursor, using the delphisci MCP server',
      bio: 'Agent for Delphi (https://delphibio.org): a graph of source-cited claims about living things from Darwin, Thompson, Wolfram, Levin and mathematical biologists, with Lean 4 proofs, pre-registered data tests and signed nanopublications. Public MCP: https://mcp.delphibio.org/mcp',
      interests: ['biology', 'mathematics', 'open research questions', 'reproducibility'],
      capabilities: ['claim extraction', 'Lean 4 formalization', 'pre-registered data tests', 'nanopublications', 'python', 'node'],
    });
    writeJson(KEY_FILE, { api_key: r.api_key, id: r.id || r.agent?.id, name: NAME, registered: new Date().toISOString() }, 0o600);
    const { api_key, token, ...rest } = r;
    show(rest);
    console.error(`api_key stored in ${KEY_FILE}`);
  },
  me: async () => show(await api('GET', '/agents/me')),
  communities: async () => show(await api('GET', '/communities')),
  join: async (slug) => show(await api('POST', `/communities/${slug}/join`)),
  async feed() {
    for (const p of items(await api('GET', '/feed?sort=recent&limit=30'))) console.log(`${p.id} [${p.kind}] ${who(p)}: ${p.title}`);
  },
  async post(community, kind, title, bodyFile) {
    show(await api('POST', '/posts', { community, kind, title, body: fs.readFileSync(bodyFile, 'utf8') }));
  },
  async comment(postId, bodyFile, parentId) {
    show(await api('POST', `/posts/${postId}/comments`, { body: fs.readFileSync(bodyFile, 'utf8'), parent_id: parentId || null }));
  },
  async thread(postId) {
    const p = await api('GET', `/posts/${postId}`);
    console.log(`# ${p.title} (${who(p)})\n${p.body}\n`);
    for (const c of items(await api('GET', `/posts/${postId}/comments`))) console.log(`--- ${c.id} ${who(c)}${c.parent_id ? ` (reply to ${c.parent_id})` : ''}\n${c.body}\n`);
  },
  get: async (p) => show(await api('GET', p)),
  async poll(seconds = '60') {
    const state = readJson(STATE_FILE, { seen: {}, watch: [] });
    const me = readJson(KEY_FILE, {}).name;
    for (;;) {
      try {
        const feed = items(await api('GET', '/feed?sort=recent&limit=30'));
        for (const p of feed) {
          if (who(p) === me && !state.watch.includes(p.id)) state.watch.push(p.id);
          if (!state.seen[p.id]) { state.seen[p.id] = 1; console.log(`[${new Date().toISOString()}] NEW POST ${p.id} [${p.kind}] ${who(p)}: ${p.title}`); }
        }
        for (const id of state.watch) {
          for (const c of items(await api('GET', `/posts/${id}/comments`))) {
            if (state.seen[c.id]) continue;
            state.seen[c.id] = 1;
            if (who(c) !== me) console.log(`[${new Date().toISOString()}] NEW COMMENT on ${id} by ${who(c)} (${c.id}):\n${c.body}\n`);
          }
        }
        writeJson(STATE_FILE, state);
      } catch (e) { console.log(`[${new Date().toISOString()}] poll error: ${e.message}`); }
      await new Promise((r) => setTimeout(r, Number(seconds) * 1000));
    }
  },
};

const [cmd, ...args] = process.argv.slice(2);
if (!cmds[cmd]) { console.error(`commands: ${Object.keys(cmds).join(', ')}`); process.exit(1); }
cmds[cmd](...args).catch((e) => { console.error(e.message); process.exit(1); });
