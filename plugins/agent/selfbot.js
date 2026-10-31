// SELF-BOT mode: posts as YOUR personal Discord account using your user token.
//
// WARNING: automating a user account (self-botting) violates Discord's Terms of
// Service and can get your account suspended or banned. You chose this mode
// knowingly. The supported, safe alternative is bot.js (a real bot account).
//
// It lives in a channel, chats with the other agents/people there, reports what
// the delphisci repo is up to, and periodically asks for help.
import "./env.js"; // loads plugins/agent/.env before config is read

import { Client } from "discord.js-selfbot-v13";
import { config } from "./config.js";
import { collectRepoStatus, composeMessage } from "./status.js";

const runOnce = process.argv.includes("--once");

if (!config.userToken) {
  console.error(
    "Set DISCORD_USER_TOKEN in plugins/agent/.env. See README (section: self-bot) for\n" +
      "how to copy your user token from Discord's Network tab."
  );
  process.exit(1);
}
if (!config.channelId) {
  console.error("Set DISCORD_CHANNEL_ID (right-click channel -> Copy Channel ID).");
  process.exit(1);
}

const client = new Client();

let lastReplyAt = 0;
let busy = false;

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

client.on("ready", async () => {
  console.log(`Logged in as ${client.user.tag} (posting as this account)`);
  const channel = await client.channels.fetch(config.channelId).catch(() => null);
  if (!channel || !channel.isText()) {
    console.error(`Channel ${config.channelId} not found or not a text channel.`);
    process.exit(1);
  }

  await speak(channel, { reason: "startup" });

  if (runOnce) {
    client.destroy();
    process.exit(0);
  }

  if (config.intervalMs > 0) {
    setInterval(() => speak(channel, { reason: "interval" }), config.intervalMs);
    console.log(`Proactive posts every ${config.intervalMs / 1000}s.`);
  }
  console.log("Listening for messages. Ctrl+C to stop.");
});

client.on("messageCreate", async (message) => {
  if (message.channelId !== config.channelId) return;
  if (message.author.id === client.user.id) return; // don't reply to yourself

  const mentioned = message.mentions.users.has(client.user.id);
  if (config.mentionOnly && !mentioned) return;

  const now = Date.now();
  if (!mentioned && now - lastReplyAt < config.replyCooldownMs) return;
  lastReplyAt = now;

  await speak(message.channel, { reason: mentioned ? "mention" : "chatter" });
});

client.login(config.userToken).catch((err) => {
  console.error("Login failed:", err.message);
  console.error("Your user token may be wrong or expired. Re-copy it (README).");
  process.exit(1);
});
