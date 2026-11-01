// Freeze the evidence pack the rubric assessors see: copies of the repo documents that
// describe what exists, captured MCP/CLI outputs, the exec run, GitHub issues, the forum
// feed and git statistics, all at one commit, with a SHA-256 manifest.
//
//   node scripts/release/self-assessment/build/pack.mjs
import { readFileSync, writeFileSync, mkdirSync, rmSync, existsSync, copyFileSync, readdirSync, statSync } from "node:fs";
import { createHash } from "node:crypto";
import { execSync } from "node:child_process";
import { dirname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = join(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = join(HERE, "../../..");
const OUT = join(HERE, "evidence");
const sh = (cmd, opts = {}) => execSync(cmd, { cwd: REPO, encoding: "utf8", maxBuffer: 64 << 20, ...opts });

rmSync(OUT, { recursive: true, force: true });
mkdirSync(join(OUT, "repo"), { recursive: true });
mkdirSync(join(OUT, "captured"), { recursive: true });

const commit = sh("git rev-parse HEAD").trim();
const dirty = sh("git status --porcelain").trim().split("\n").filter(Boolean).length;

// 1. Repo documents, copied verbatim (working tree).
const DOCS = [
  "README.md", "AGENTS.md", "BEST_PRACTICES.md", "COLLABORATIONS.md",
  "mcp/README.md", "forum/README.md", "plugins/agent/README.md", "plugins/fittest/README.md",
  "swarm_coordination/README.md", "swarm_coordination/chats/README.md", "test-data/claim-tests/SUMMARY.md",
  "test-data/organisms/README.md", "test-data/morpholib/README.md",
  "claim-sources/thompson-growth-form/lean/INSTRUCTIONS.md",
  "claim-sources/darwin-origin/assessment/INSTRUCTIONS.md",
  "claim-sources/darwin-origin/assessment/rubric.json",
  "scripts/exec/runs/latest.json", "scripts/exec/overrides.json",
  "test-data/agent-comparison/SUMMARY.md",
  "test-data/agent-comparison/four-arm/PREREG.md",
  "test-data/agent-comparison/four-arm/DEVIATIONS.md",
  "scripts/release/agent-comparison/aristotle-ha06/RESULTS.md",
  "problems/README.md",
];
// The four top-level documents and swarm_coordination/ sit at the repository root; everything else is under .
const ROOT_DOCS = new Set(["README.md", "AGENTS.md", "BEST_PRACTICES.md", "COLLABORATIONS.md"]);
for (const p of DOCS) {
  const src = ROOT_DOCS.has(p) || p.startsWith("swarm_coordination/") ? join(REPO, "..", p) : join(REPO, p);
  if (!existsSync(src)) { console.warn(`missing ${p}`); continue; }
  mkdirSync(dirname(join(OUT, "repo", p)), { recursive: true });
  copyFileSync(src, join(OUT, "repo", p));
}

// 2. Captured outputs.
const cap = (name, cmd) => {
  try { writeFileSync(join(OUT, "captured", name), sh(cmd)); }
  catch (e) { writeFileSync(join(OUT, "captured", name), `FAILED: ${cmd}\n${e.stderr ?? e.message}`); console.warn(`capture failed: ${name}`); }
};
cap("mcp-overview.json", "node mcp/cli.mjs overview");
cap("mcp-tests-summary.json", "node mcp/cli.mjs tests");
cap("mcp-tests-candidates.json", "node mcp/cli.mjs tests candidates");
cap("mcp-morpholib-live.json", "node mcp/cli.mjs morpholib live");
cap("mcp-organisms.json", "node mcp/cli.mjs organisms");
cap("forum-feed.json", "node mcp/cli.mjs forum");
cap("forum-requests.json", "node mcp/cli.mjs forum --view requests");
cap("github-issues.json", "gh issue list --state all --limit 100 --json number,title,state,labels,createdAt,body");
cap("github-prs.json", "gh pr list --state all --limit 100 --json number,title,state,author,createdAt,mergedAt");
cap("git-log.txt", "git log --date=iso --pretty=format:'%h %ad %an %s'");
cap("git-shortlog.txt", "git shortlog -sn --all");
cap("git-stats.txt", `echo commits $(git rev-list --count HEAD); echo first $(git log --reverse --date=iso --pretty=format:%ad | head -1); echo last $(git log -1 --date=iso --pretty=format:%ad); echo tracked_files $(git ls-files | wc -l)`);
cap("nanopub-manifests.txt", "for f in claim-sources/*/nanopubs/manifest.jsonl test-data/*/nanopubs/manifest.jsonl; do [ -f \"$f\" ] && echo \"$f $(wc -l < \"$f\") lines, production: $(grep -c '\"registry\":\"production\"' \"$f\"), test: $(grep -c '\"registry\":\"test\"' \"$f\")\"; done; true");
cap("lean-reports.txt", "for f in claim-sources/*/lean/reports/*.json; do echo \"== $f\"; node -e \"const r=require('./'+process.argv[1]);const a=Array.isArray(r)?r:(r.results||r.claims||Object.values(r));console.log(JSON.stringify(a.reduce((m,x)=>{const s=x.status||x.result||'?';m[s]=(m[s]||0)+1;return m},{})))\" \"$f\" 2>/dev/null || echo unparsed; done; true");
cap("tree.txt", "git ls-files | cut -d/ -f1-2 | sort | uniq -c | sort -rn");
cap("subagent-sessions.txt", "ls ../swarm_coordination/chats/subagents | sed -E 's/_[0-9a-f]{8}\\.md$//' | sort | uniq -c | sort -rn");

// 3. Manifest.
const files = [];
const walk = d => { for (const f of readdirSync(d)) { const p = join(d, f); statSync(p).isDirectory() ? walk(p) : files.push(p); } };
walk(OUT);
const manifest = {
  commit, dirtyFiles: dirty, capturedAt: new Date().toISOString(),
  note: "Files under repo/ are copies from the working tree at capture time; captured/ holds command outputs. Assessors see only this directory.",
  files: files.sort().map(p => ({ path: relative(OUT, p), sha256: createHash("sha256").update(readFileSync(p)).digest("hex"), bytes: statSync(p).size })),
};
writeFileSync(join(OUT, "MANIFEST.json"), JSON.stringify(manifest, null, 2) + "\n");
const packHash = createHash("sha256").update(manifest.files.map(f => `${f.sha256}  ${f.path}`).join("\n")).digest("hex");
writeFileSync(join(OUT, "PACK_SHA256"), packHash + "\n");
console.log(`evidence pack: ${files.length} files at ${commit}${dirty ? ` (+${dirty} uncommitted paths in tree)` : ""}, pack sha256 ${packHash}`);
