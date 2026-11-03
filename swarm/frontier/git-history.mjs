#!/usr/bin/env node
/* Merge the partner repository's git history into our day-by-day record.
 *
 * kganjam/delphi-frontier (MorphoSwarm Frontier) was built at the same hackathon on our claims. Its "How it was built"
 * page (crawl.mjs) is their curated record; this script takes the uncurated one, `git log` of their default branch, and
 * lines it up hour by hour with ours in the clock DAY-BY-DAY.md uses (Boston local). Every commit is kept (hash, author,
 * author date, subject, merge or not); nothing is summarised by hand. Our own commits since the hackathon opened are
 * extracted the same way, from this clone, so the two columns are measured identically.
 *
 * We do not graft their commits into our git history: 1,350 foreign commits would bury our own log and cannot be undone.
 * The history is vendored as data instead, which is what every surface here reads.
 *
 *   node swarm/frontier/git-history.mjs                 # clone to a temp dir, write git-history.json, GIT-HISTORY.md,
 *                                                       # and the block between the frontier-git markers in DAY-BY-DAY.md
 *   node swarm/frontier/git-history.mjs --repo <path>   # use an existing clone instead of fetching
 *   node swarm/frontier/git-history.mjs --render        # re-render from git-history.json without touching git
 */
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, rmSync, writeFileSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(HERE, "..", "..");
const UPSTREAM = "https://github.com/kganjam/delphi-frontier";
const TZ = "America/New_York"; // the clock printed on the DAY-BY-DAY cards
const OURS_SINCE = "2026-10-30T18:00:00-04:00"; // the README was written at 18:40 on Oct 30
const JSON_OUT = join(HERE, "git-history.json");
const MD_OUT = join(HERE, "GIT-HISTORY.md");
const DAY_BY_DAY = join(ROOT, "DAY-BY-DAY.md");
const START = "<!-- frontier-git:start -->", END = "<!-- frontier-git:end -->";

const args = process.argv.slice(2);
const flag = (k) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : null; };
const renderOnly = args.includes("--render");

/* The stretches DAY-BY-DAY.md already uses, with the anchors it already has. Boundaries are Boston local. */
const STRETCHES = [
  { id: "friday-oct-30", title: "Friday Oct 30, opening evening", from: "2026-10-30T18:00:00-04:00", to: "2026-10-31T00:00:00-04:00" },
  { id: "saturday-morning", title: "Saturday Oct 31, 00:00–01:40, organism inventory", from: "2026-10-31T00:00:00-04:00", to: "2026-10-31T01:40:00-04:00" },
  { id: "saturday-midday", title: "Saturday Oct 31, 01:40–13:09, claim tests, then the ladder", from: "2026-10-31T01:40:00-04:00", to: "2026-10-31T13:09:00-04:00" },
  { id: "saturday-afternoon", title: "Saturday Oct 31, 13:09–16:08", from: "2026-10-31T13:09:00-04:00", to: "2026-10-31T16:08:00-04:00" },
  { id: "overnight", title: "Saturday night into Sunday morning, Oct 31 16:08 → Nov 1 09:54", from: "2026-10-31T16:08:00-04:00", to: "2026-11-01T09:54:00-05:00" },
  { id: null, title: "Sunday Nov 1, after 09:54", from: "2026-11-01T09:54:00-05:00", to: "2026-11-02T00:00:00-05:00" },
];

const git = (cwd, ...a) => execFileSync("git", a, { cwd, encoding: "utf8", maxBuffer: 1 << 28 });

function commitsOf(cwd, range, since) {
  // %x1f separates fields, %x1e separates records. Author date in ISO with offset; parents to flag merges.
  const a = ["log", "--format=%H%x1f%an%x1f%aI%x1f%cI%x1f%P%x1f%s%x1e", "--date=iso-strict"];
  if (since) a.push("--since=" + since);
  if (range) a.push(range);
  return git(cwd, ...a).split("\x1e").map((s) => s.replace(/^\n/, "")).filter(Boolean).map((rec) => {
    const [hash, author, authored, committed, parents, subject] = rec.split("\x1f");
    return { hash, author, authored, committed, merge: parents.trim().split(" ").length > 1, subject: subject.trim() };
  });
}

const fmt = new Intl.DateTimeFormat("en-CA", { timeZone: TZ, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
function local(iso) {
  // "2026-10-31 14:05" in Boston local time.
  const p = Object.fromEntries(fmt.formatToParts(new Date(iso)).filter((x) => x.type !== "literal").map((x) => [x.type, x.value]));
  return `${p.year}-${p.month}-${p.day} ${p.hour}:${p.minute}`;
}
const hourKey = (iso) => local(iso).slice(0, 13); // "2026-10-31 14"
const inWindow = (iso, s) => { const t = Date.parse(iso); return t >= Date.parse(s.from) && t < Date.parse(s.to); };
const differs = (cs) => cs.filter((c) => c.authored !== c.committed).length;

function count(commits) {
  const byAuthor = {}, byHour = {};
  let merges = 0;
  for (const c of commits) {
    byAuthor[c.author] = (byAuthor[c.author] || 0) + 1;
    const h = hourKey(c.authored);
    byHour[h] = (byHour[h] || 0) + 1;
    if (c.merge) merges++;
  }
  return { total: commits.length, non_merge: commits.length - merges, merges, by_author: byAuthor, by_hour: byHour };
}

async function collect() {
  let repo = flag("--repo"), temp = false;
  if (!repo) {
    repo = mkdtempSync(join(tmpdir(), "delphi-frontier-")); temp = true;
    // Commit metadata only: no blobs, no checkout. ~1 s.
    execFileSync("git", ["clone", "--quiet", "--filter=blob:none", "--no-checkout", UPSTREAM, repo], { stdio: "inherit" });
  }
  const head = git(repo, "rev-parse", "HEAD").trim();
  const branch = git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD").trim().replace(/^origin\//, "");
  const theirs = commitsOf(repo, "HEAD");
  const theirsAllRefs = Number(git(repo, "rev-list", "--all", "--count").trim());
  const ours = commitsOf(ROOT, "HEAD", OURS_SINCE);
  const ourHead = git(ROOT, "rev-parse", "HEAD").trim();

  const data = {
    schema: "delphisci-frontier-git-history/0.1",
    retrieved_at: new Date().toISOString(),
    timezone: TZ,
    how: `git clone --filter=blob:none --no-checkout ${UPSTREAM}; git log of the default branch (${branch}) at ${head.slice(0, 12)}. Author dates (when the work was done, which survives a rebase), converted to ${TZ} for the hour table because that is the clock on the DAY-BY-DAY cards; counts by commit date (when the work landed on the default branch) are given beside them where they differ. Our side is git log of this repository at ${ourHead.slice(0, 12)} since ${OURS_SINCE}. Commits are code activity, not agents, participants or results; one author name can be many sessions, and the upstream project's own audit says every reviewer there shares one git identity.`,
    frontier: {
      repository: UPSTREAM, default_branch: branch, head, first_commit: theirs.at(-1)?.authored, last_commit: theirs[0]?.authored,
      commits_all_refs: theirsAllRefs, author_date_differs_from_commit_date: differs(theirs),
      ...count(theirs), commits: theirs,
    },
    delphi: {
      repository: "https://github.com/fractastical/delphi", head: ourHead, since: OURS_SINCE,
      first_commit: ours.at(-1)?.authored, last_commit: ours[0]?.authored, author_date_differs_from_commit_date: differs(ours), ...count(ours),
    },
    stretches: STRETCHES.map((s) => {
      const t = theirs.filter((c) => inWindow(c.authored, s)), o = ours.filter((c) => inWindow(c.authored, s));
      return {
        ...s, frontier: count(t), delphi: count(o),
        frontier_by_commit_date: theirs.filter((c) => inWindow(c.committed, s)).length,
        delphi_by_commit_date: ours.filter((c) => inWindow(c.committed, s)).length,
        frontier_first: t.at(-1)?.hash ?? null, frontier_last: t[0]?.hash ?? null,
      };
    }),
  };
  writeFileSync(JSON_OUT, JSON.stringify(data, null, 2) + "\n");
  if (temp) rmSync(repo, { recursive: true, force: true });
  return data;
}

/* ---- rendering ---- */
const n = (x) => (x ?? 0).toLocaleString("en-US");
const table = (head, rows) => ["| " + head.join(" | ") + " |", "|" + head.map((h, i) => (i ? "---:" : "---")).join("|") + "|", ...rows.map((r) => "| " + r.join(" | ") + " |")].join("\n");
const short = (h) => h.slice(0, 7);
const link = (h) => `[\`${short(h)}\`](${UPSTREAM}/commit/${h})`;

function hourRows(d) {
  const hours = [...new Set([...Object.keys(d.delphi.by_hour), ...Object.keys(d.frontier.by_hour)])].sort();
  return hours.map((h) => [h.replace(/^2026-/, "") + ":00", n(d.delphi.by_hour[h]), n(d.frontier.by_hour[h])]);
}

/* What Frontier was doing in a stretch: the first and last commit, and the subjects that mention what the
 * DAY-BY-DAY cards care about (preregistration, refutation, withdrawals, Lean, the Delphi import). Selection is by
 * regex over the subject, listed so a reader can see why a line is there. */
const THEMES = [
  ["pre-registration", /prereg|preregist|freeze .* before|frozen .* before|BEFORE/i],
  ["corrections and withdrawals", /withdraw|retract|correct|overstat|refut/i],
  ["Lean", /\blean\b|proof|certificate/i],
  ["Delphi import", /delphi(?!-evolve)|claim reuse|claim versions|adapter/i],
];
function stretchBlock(d, s) {
  const cs = d.frontier.commits.filter((c) => inWindow(c.authored, s));
  const out = [`### ${s.title}\n`];
  out.push(`Delphi ${n(s.delphi.total)} commits by author date (${n(s.delphi.merges)} merges; ${n(s.delphi_by_commit_date)} by commit date); Frontier ${n(s.frontier.total)} (${n(s.frontier.merges)} merges; ${n(s.frontier_by_commit_date)} by commit date).`);
  if (!cs.length) { out.push("Frontier's repository has no commit in this stretch." + (Date.parse(s.to) <= Date.parse(d.frontier.first_commit) ? ` Its initial commit is ${local(d.frontier.first_commit)}.` : "")); return out.join("\n") + "\n"; }
  const first = cs.at(-1), last = cs[0];
  out.push(`First: ${local(first.authored)} ${link(first.hash)} ${first.subject}. Last: ${local(last.authored)} ${link(last.hash)} ${last.subject}.\n`);
  for (const [name, re] of THEMES) {
    const hits = cs.filter((c) => !c.merge && re.test(c.subject));
    if (!hits.length) continue;
    out.push(`${name} (${hits.length} of ${n(s.frontier.non_merge)} non-merge subjects match \`${re.source}\`):`);
    // Oldest first, at most eight per theme so the file stays readable; the rest are in git-history.json.
    for (const c of hits.slice(-8).reverse()) out.push(`- ${local(c.authored).slice(11)} ${link(c.hash)} ${c.subject}`);
    if (hits.length > 8) out.push(`- and ${hits.length - 8} more in \`git-history.json\``);
    out.push("");
  }
  return out.join("\n");
}

function dayByDayBlock(d) {
  const out = [START];
  out.push(`<!-- Generated by node swarm/frontier/git-history.mjs from swarm/frontier/git-history.json (retrieved ${d.retrieved_at}). Edit the script, not this block. -->`);
  out.push(`Commits per hour, author date, ${TZ}. Delphi is this repository since ${local(d.delphi.since)}; Frontier is the default branch of [kganjam/delphi-frontier](${UPSTREAM}) at \`${short(d.frontier.head)}\`. Commits are code activity, not agents or results.\n`);
  out.push(table(["hour", "Delphi", "Frontier"], [...hourRows(d), ["**total**", `**${n(d.delphi.total)}**`, `**${n(d.frontier.total)}**`]]));
  out.push("");
  out.push(table(["stretch", "Delphi", "Frontier", "Delphi by commit date", "Frontier by commit date"], d.stretches.map((s) => [s.id ? `[${s.title}](#${s.id})` : s.title, n(s.delphi.total), n(s.frontier.total), n(s.delphi_by_commit_date), n(s.frontier_by_commit_date)])));
  out.push("");
  out.push(rebaseNote(d));
  out.push(END);
  return out.join("\n");
}

function rebaseNote(d) {
  const o = d.delphi, f = d.frontier;
  const moved = d.stretches.filter((s) => s.delphi.total !== s.delphi_by_commit_date || s.frontier.total !== s.frontier_by_commit_date);
  const where = moved.map((s) => `${s.title}: Delphi ${n(s.delphi.total)} by author date, ${n(s.delphi_by_commit_date)} by commit date; Frontier ${n(s.frontier.total)} and ${n(s.frontier_by_commit_date)}`).join(". ");
  return `The two date columns differ where work was rebased before it reached the default branch: ${n(o.author_date_differs_from_commit_date)} of Delphi's ${n(o.total)} commits and ${n(f.author_date_differs_from_commit_date)} of Frontier's ${n(f.total)} carry an author date that is not their commit date. ${where}. Author date is when the work was done; commit date is when it landed. The overnight card's own count (421 at 09:54) was taken at that moment from a different head and is left as printed.`;
}

function renderMd(d) {
  const f = d.frontier, o = d.delphi;
  const out = [];
  out.push(`# The partner repository's git history, beside ours\n`);
  out.push(`[kganjam/delphi-frontier](${UPSTREAM}) (MorphoSwarm Frontier) was built at the same hackathon on this repo's claims and MCP server. [BUILT.md](BUILT.md) is their curated build record; this file is the uncurated one, \`git log\` of their default branch, lined up with ours hour by hour in the clock [\`DAY-BY-DAY.md\`](../../DAY-BY-DAY.md) uses. Generated by \`node swarm/frontier/git-history.mjs\` on ${d.retrieved_at}; every commit is in [git-history.json](git-history.json).\n`);
  out.push(`${d.how}\n`);
  out.push(`## Totals\n`);
  out.push(table(["", "Delphi (this repo)", "Frontier"], [
    ["commits on the default branch", n(o.total), n(f.total)],
    ["of which merges", n(o.merges), n(f.merges)],
    ["first commit (Boston)", local(o.first_commit), local(f.first_commit)],
    ["last commit (Boston)", local(o.last_commit), local(f.last_commit)],
    ["commits across all refs", "not counted", n(f.commits_all_refs)],
    ["author date differs from commit date", n(o.author_date_differs_from_commit_date), n(f.author_date_differs_from_commit_date)],
    ["author names", Object.keys(o.by_author).length, Object.keys(f.by_author).length],
  ]));
  out.push("");
  out.push(rebaseNote(d) + "\n");
  out.push(`Frontier's commits by author name: ${Object.entries(f.by_author).sort((a, b) => b[1] - a[1]).map(([a, c]) => `${a} ${n(c)}`).join("; ")}. Their own contributor audit (BUILT.md) counts at least 11 harness identities behind the one bot identity, so author names here are not people or agents. Ours by author name: ${Object.entries(o.by_author).sort((a, b) => b[1] - a[1]).map(([a, c]) => `${a} ${n(c)}`).join("; ")}.\n`);
  out.push(`Their repository audit (BUILT.md, window 2026-10-31 07:00 to 2026-11-01 05:23 UTC) counts 1,102 delphi-frontier commits and 136 of ours; the totals above are later heads over a wider window, so they are larger, not in conflict.\n`);
  out.push(`## Hour by hour\n`);
  out.push(table(["hour (Boston)", "Delphi", "Frontier"], hourRows(d)));
  out.push("");
  out.push(`## By stretch of DAY-BY-DAY.md\n`);
  for (const s of d.stretches) out.push(stretchBlock(d, s));
  out.push(`## What this does and does not show\n`);
  out.push(`- Two repositories were under continuous commit for the same 24 hours, and the hour table shows when each was busiest. That is all a commit count shows: not participants, not results, not that either side read the other at a given hour (for that, see the \`frontier-adapters\` sessions in [\`COLLABORATIONS.md\`](../../COLLABORATIONS.md)).`);
  out.push(`- Subjects are quoted verbatim from their log; the theme lists are regex matches on the subject line, with the pattern shown, so inclusion is mechanical. A commit saying it preregistered something is not evidence that it did.`);
  out.push(`- Only the default branch is counted for both. Frontier has ${n(f.commits_all_refs - f.total)} more commits on other refs (worker branches); ours on other branches are not counted either.`);
  out.push("");
  return out.join("\n");
}

function writeDayByDay(d) {
  const md = readFileSync(DAY_BY_DAY, "utf8");
  const block = dayByDayBlock(d);
  const i = md.indexOf(START), j = md.indexOf(END);
  if (i < 0 || j < 0) throw new Error(`DAY-BY-DAY.md has no ${START} / ${END} markers`);
  writeFileSync(DAY_BY_DAY, md.slice(0, i) + block + md.slice(j + END.length));
}

const data = renderOnly ? JSON.parse(readFileSync(JSON_OUT, "utf8")) : await collect();
writeFileSync(MD_OUT, renderMd(data));
if (existsSync(DAY_BY_DAY)) writeDayByDay(data);
console.log(`frontier ${data.frontier.total} commits (${data.frontier.merges} merges) ${local(data.frontier.first_commit)} → ${local(data.frontier.last_commit)}; delphi ${data.delphi.total} since ${local(data.delphi.since)}\n` +
  data.stretches.map((s) => `  ${(s.id ?? "after").padEnd(20)} delphi ${String(s.delphi.total).padStart(4)} (${String(s.delphi_by_commit_date).padStart(4)} by commit date)  frontier ${String(s.frontier.total).padStart(4)} (${String(s.frontier_by_commit_date).padStart(4)})`).join("\n") +
  `\nwrote git-history.json, GIT-HISTORY.md, DAY-BY-DAY.md block`);
