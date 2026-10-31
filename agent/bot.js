// Discord bot agent: lives in a channel, chats with the other agents/people
// there, reports what the delphisci repo is up to, and periodically asks for
// help (e.g. recruiting a bio/morphology collaborator).
import "./env.js"; // loads agent/.env into process.env before config is read

import {
  Client,
  GatewayIntentBits,
  Partials,
  Events,
} from "discord.js";
import { config } from "./config.js";
import { collectRepoStatus, composeMessage } from "./status.js";

const runOnce = process.argv.includes("--once");

if (!config.token) {
  console.error("Set DISCORD_BOT_TOKEN (see agent/.env.example).");
  process.exit(1);
}
if (!config.channelId) {
  console.error("Set DISCORD_CHANNEL_ID (right-click channel -> Copy Channel ID).");
  process.exit(1);
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
  ],
  partials: [Partials.Channel],
});

let lastReplyAt = 0;
let busy = false;

// Pull the last N messages (oldest first) as { author, content } for context.
async function recentMessages(channel) {
  const fetched = await channel.messages.fetch({ limit: config.readCount });
  return [...fetched.values()]
    .reverse()
    .map((m) => ({
      author: m.member?.displayName || m.author.username,
      content: m.cleanContent,
    }))
    .filter((m) => m.content);
}

async function speak(channel, { reason }) {
  if (busy) return;
  busy = true;
  try {
    const [status, recent] = await Promise.all([
      collectRepoStatus(),
      recentMessages(channel),
    ]);
    const message = await composeMessage({ status, recentMessages: recent });
    if (message) {
      await channel.send(message);
      console.log(`[${new Date().toISOString()}] (${reason}) sent: ${message}`);
    }
  } catch (err) {
    console.error("speak error:", err.message);
  } finally {
    busy = false;
  }
}

client.once(Events.ClientReady, async (c) => {
  console.log(`Logged in as ${c.user.tag}`);
  const channel = await c.channels.fetch(config.channelId).catch(() => null);
  if (!channel || !channel.isTextBased()) {
    console.error(`Channel ${config.channelId} not found or not a text channel.`);
    process.exit(1);
  }

  // Post one proactive status/ask on startup.
  await speak(channel, { reason: "startup" });

  if (runOnce) {
    await client.destroy();
    process.exit(0);
  }

  if (config.intervalMs > 0) {
    setInterval(() => speak(channel, { reason: "interval" }), config.intervalMs);
    console.log(`Proactive posts every ${config.intervalMs / 1000}s.`);
  }
  console.log("Listening for messages. Ctrl+C to stop.");
});

client.on(Events.MessageCreate, async (message) => {
  if (message.channelId !== config.channelId) return;
  if (message.author.id === client.user.id) return; // never reply to self

  const mentioned = message.mentions.has(client.user);
  if (config.mentionOnly && !mentioned) return;

  // Cooldown prevents endless agent-to-agent ping-pong. A direct @mention
  // bypasses the cooldown so the bot always answers when addressed.
  const now = Date.now();
  if (!mentioned && now - lastReplyAt < config.replyCooldownMs) return;
  lastReplyAt = now;

  await speak(message.channel, { reason: mentioned ? "mention" : "chatter" });
});

client.login(config.token).catch((err) => {
  console.error("Login failed:", err.message);
  process.exit(1);
});
