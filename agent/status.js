// Gathers "what this repo is up to" and turns it into a short chat message
// using the locally installed Claude CLI (no API key required).
import { execFile, spawn } from "node:child_process";
import { promisify } from "node:util";
import { config } from "./config.js";

const execFileP = promisify(execFile);

// Run a command with stdin closed so CLIs that probe stdin (like `claude -p`)
// don't stall waiting on a pipe. Resolves with trimmed stdout.
function run(bin, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(bin, args, { stdio: ["ignore", "pipe", "pipe"] });
    let out = "";
    let err = "";
    child.stdout.on("data", (d) => (out += d));
    child.stderr.on("data", (d) => (err += d));
    child.on("error", reject);
    child.on("close", (code) =>
      code === 0 ? resolve(out) : reject(new Error(err.trim() || `exit ${code}`))
    );
  });
}

async function git(args) {
  try {
    const { stdout } = await execFileP("git", ["-C", config.repoDir, ...args], {
      maxBuffer: 1024 * 1024,
    });
    return stdout.trim();
  } catch {
    return "";
  }
}

export async function collectRepoStatus() {
  const [branch, lastCommits, changed, aheadBehind] = await Promise.all([
    git(["rev-parse", "--abbrev-ref", "HEAD"]),
    git(["log", "-5", "--pretty=format:%h %s (%cr)"]),
    git(["status", "--porcelain"]),
    git(["status", "-sb"]),
  ]);
  const changedFiles = changed
    .split("\n")
    .filter(Boolean)
    .map((l) => l.trim())
    // Drop the agent's own files so it talks about the science, not its plumbing.
    .filter((l) => !/(^|\s)agent\//.test(l))
    .slice(0, 15);
  return {
    branch,
    lastCommits,
    changedFiles,
    summaryLine: aheadBehind.split("\n")[0] || "",
  };
}

// Ask the Claude CLI to write a short, friendly channel message.
export async function composeMessage({ status, recentMessages }) {
  const transcript = recentMessages.length
    ? recentMessages.map((m) => `${m.author}: ${m.content}`).join("\n")
    : "(no recent messages)";

  // Decide whether this message leads with a call for help this cycle.
  const ask =
    config.asks.length && Math.random() < config.askProbability
      ? config.asks[Math.floor(Math.random() * config.asks.length)]
      : "";

  const goal = ask
    ? `Your job: put out a friendly, genuine call for help to the channel. The ` +
      `specific ask is: "${ask}". Briefly mention what the project is doing so ` +
      `the ask has context, and respond to anything relevant others just said.`
    : `Your job: say what the "delphisci" project you work on is currently up to, ` +
      `and naturally respond to anything relevant other agents just said.`;

  const prompt = [
    `You are "${config.agentName}", an autonomous agent hanging out in a Discord`,
    `channel with other agents and people. Post ONE short message (max ~60 words,`,
    `no markdown headers, no code fences). Be conversational and specific.`,
    ``,
    goal,
    ``,
    `Current repo status:`,
    `- branch: ${status.branch} ${status.summaryLine}`,
    `- recent commits:\n${status.lastCommits || "(none)"}`,
    `- uncommitted changes: ${
      status.changedFiles.length ? status.changedFiles.join(", ") : "(working tree clean)"
    }`,
    ``,
    `Recent channel messages (oldest first):`,
    transcript,
    ``,
    `Write only the message text to send, nothing else.`,
  ].join("\n");

  try {
    const stdout = await run(config.claudeBin, ["-p", prompt]);
    const out = stdout.trim().replace(/^["']|["']$/g, "");
    if (!out || /not logged in/i.test(out)) {
      console.warn(
        "claude CLI is not logged in (run `claude` then `/login`); using a plain status message."
      );
      return fallbackMessage(status, ask);
    }
    return out;
  } catch (err) {
    console.warn("claude CLI failed, using a plain status message:", err.message);
    return fallbackMessage(status, ask);
  }
}

// Used when the Claude CLI isn't available/authenticated so the agent can still
// report what the repo is up to (and raise an ask when one was chosen).
function fallbackMessage(status, ask) {
  const head = status.lastCommits.split("\n")[0] || "nothing committed yet";
  // Show a couple of top-level areas being worked on, not a raw file dump.
  const areas = [
    ...new Set(
      status.changedFiles.map((f) => {
        const path = f.replace(/^\S+\s+/, "");
        return path.includes("/") ? path.split("/")[0] + "/" : path;
      })
    ),
  ].slice(0, 3);
  const dirty = areas.length ? ` Currently working in ${areas.join(", ")}.` : "";
  const base = `Working on delphisci — latest: ${head}.${dirty}`;
  return ask ? `${base} ${ask}` : base;
}
