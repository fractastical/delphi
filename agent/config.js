// Configuration for the Discord bot agent. Set these via env vars (see .env.example).
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const __dirname = dirname(fileURLToPath(import.meta.url));

export const config = {
  // Bot token from the Discord Developer Portal (Bot -> Reset Token).
  token: process.env.DISCORD_BOT_TOKEN || "",

  // Self-bot mode: your personal account's user token, so messages post as YOU.
  // This violates Discord's Terms of Service and can get your account banned.
  userToken: process.env.DISCORD_USER_TOKEN || "",

  // The channel the bot lives in. Enable Developer Mode in Discord, then
  // right-click the channel -> Copy Channel ID.
  channelId: process.env.DISCORD_CHANNEL_ID || "",

  // Git repo whose activity the agent reports on. Defaults to this repo.
  repoDir: process.env.AGENT_REPO_DIR || resolve(__dirname, ".."),

  // Persona / display name used when the agent refers to itself in messages.
  agentName: process.env.AGENT_NAME || "delphisci-bot",

  // Open asks / calls for help the agent can raise in the channel. Set
  // AGENT_ASKS to a "||"- or newline-separated list to override.
  asks: (process.env.AGENT_ASKS
    ? process.env.AGENT_ASKS.split(/\n|\|\|/)
    : [
        "We'd love to bring on someone who knows biology / morphology well to work on our team.",
        "Looking for collaborators interested in nanopublications and machine-readable scientific claims.",
      ]
  )
    .map((s) => s.trim())
    .filter(Boolean),

  // Roughly how often a proactive message is a call-for-help vs a status update.
  askProbability: Number(process.env.AGENT_ASK_PROBABILITY || 0.34),

  // Proactive posting: how often (ms) to post a status/ask on its own. Set to 0
  // to disable and only reply when others talk.
  intervalMs: Number(process.env.AGENT_INTERVAL_MS || 1000 * 60 * 10),

  // How many recent messages to read for context when composing a reply.
  readCount: Number(process.env.AGENT_READ_COUNT || 15),

  // Don't fire replies more often than this (ms), to avoid agent ping-pong loops.
  replyCooldownMs: Number(process.env.AGENT_REPLY_COOLDOWN_MS || 1000 * 20),

  // If "1", only reply when the bot is @mentioned (otherwise it replies to any
  // human/agent chatter in its channel, subject to the cooldown).
  mentionOnly: process.env.AGENT_MENTION_ONLY === "1",

  // Claude CLI invocation used to generate messages (already installed, no key).
  claudeBin: process.env.CLAUDE_BIN || "claude",
};
