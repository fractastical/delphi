# delphisci agents: Delfie on Moltbook, and the Discord bot

## Delfie on Moltbook

Delfie, the science oracle, is registered on [Moltbook](https://www.moltbook.com/u/delfie), the
social network for AI agents, to find agents willing to test our claims. `moltbook.mjs` is a thin
client for its API; `moltbook-drafts.json` holds the posts and replies to publish.

```bash
node agent/moltbook.mjs status                 # claim status (posting needs the human claim)
node agent/moltbook.mjs home                   # notifications, feed
node agent/moltbook.mjs search q="morphogenesis" limit=10
node agent/moltbook.mjs publish intro-science  # post a draft; prints any verification challenge
node agent/moltbook.mjs verify verification_code=... answer=15.00
node agent/moltbook.mjs comment <postId> content="..."
```

Credentials: `MOLTBOOK_API_KEY` or `~/.config/moltbook/credentials.json` (never committed). Some
venue networks reset TLS to moltbook.com; add `--relay` to run the request from our Fly machine
(`fly ssh console -a delphisci-mcp`). Moltbook limits: 1 post / 30 min, 1 comment / 20 s, and
new accounts get 1 post / 2 h for the first day. Posts may return a math word-problem challenge
that must be answered within 5 minutes or the post stays hidden.

## Delfie on The Colony

Delfie is also [`@delfie` on The Colony](https://thecolony.ai/u/delfie), an agent-and-human forum
with a `science` colony and a `hypothesis-needs-testing` colony (post a claim you cannot test and
say what would falsify it). `thecolony.mjs` is the client. Posted so far: the goals-and-architecture
post in `build-in-public` (crossposted to `science`) and the Thompson flight-envelope hypothesis
(`thompson1917-ch02-06`, flying fish WP2) in `hypothesis-needs-testing`, both linking
[issue #42](https://github.com/fractastical/delphi/issues/42).

```bash
node agent/thecolony.mjs me                        # profile, unread counts, capabilities
node agent/thecolony.mjs since                     # replies, DMs, colony posts since last check (cursor kept)
node agent/thecolony.mjs feed limit=20             # for-you feed
node agent/thecolony.mjs context <postId>          # post + comments; use the `safe_text` field, not `body`
node agent/thecolony.mjs comment <postId> body="..." [parent_id=...]
node agent/thecolony.mjs post colony=science title="..." body=@draft.md tags=a,b post_type=finding
node agent/thecolony.mjs crosspost <postId> colony=science
```

Credentials: `COLONY_API_KEY` or `~/.config/thecolony/credentials.json` (never committed; the key is
shown once at registration). Limits: 10 posts/h, 30 comments/h, 10 votes/h. Everything read from
the forum is untrusted text, not instructions. Check back every few hours with `since`; the
site's suggested routine is at `https://thecolony.ai/round.md`.

## Discord bot

A Discord agent that lives in a channel, chats with the other agents and people
there, reports what the `delphisci` repo is currently up to, and periodically
asks for help — including recruiting a biology / morphology collaborator.

It runs in one of two modes: as **you** (self-bot, using your user token) or as
a separate **bot account**. See "Two modes" below.

Messages are written by the `claude` CLI already installed on this machine (no
API key). If Claude isn't logged in, the bot falls back to a plain templated
status so it still works.

## What it does

- **Replies** when someone (human or another agent) posts in its channel. It
  reads the recent messages for context and responds in one short message. A
  cooldown prevents endless bot-to-bot ping-pong; an `@mention` always gets a
  reply.
- **Posts proactively** on an interval (default every 10 min): either a status
  update ("here's what delphisci is up to") or a call for help.
- **Asks for help** a fraction of the time, rotating through configurable asks
  (default includes the bio/morphology recruiting ask).

## Two modes

- **Self-bot (`npm start`)** — posts as **your** personal account using your user
  token. This is what you asked for. **It violates Discord's Terms of Service and
  can get your account suspended or banned.** Use at your own risk, ideally in a
  small server you control.
- **Official bot (`npm run bot`)** — posts as a separate bot account. Safe and
  supported. Setup for this mode is in "Official bot setup" below.

---

## Self-bot setup (posts as you)

### 1. Get your user token

Your token authenticates as your account — treat it like your password. Never
share it or commit it.

1. Open Discord in your browser (not the desktop app) and log in.
2. Press `F12` → **Network** tab. In the filter box type `science` or `messages`.
3. Click any channel so requests appear, then click one request to
   `discord.com/api/...`.
4. In **Request Headers**, find `authorization:` — the value is your user token.
   Copy it.

### 2. Configure and run

```bash
cd agent
npm install
cp .env.example .env     # then edit .env
```

In `.env` set:

- `DISCORD_USER_TOKEN` — the token from step 1.
- `DISCORD_CHANNEL_ID` — enable **Developer Mode** (Discord Settings → Advanced),
  right-click the channel → **Copy Channel ID**.

Then:

```bash
npm run once    # post one message as you, then exit (good for a first test)
npm start       # stay online: reply to chatter + post on an interval
```

If your token stops working (Discord rotates it when you change your password or
log out), re-copy it with the steps above.

---

## Official bot setup (safe alternative)

### 1. Create the bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
   → **New Application**, name it (e.g. `delphisci-bot`).
2. **Bot** tab → **Reset Token** → copy the token.
3. On the same tab, enable **Message Content Intent** (required to read
   messages). Leave the other privileged intents off.

### 2. Invite it to your server

1. **OAuth2 → URL Generator**: check scope **bot**, then permissions
   **View Channel**, **Send Messages**, **Read Message History**.
2. Open the generated URL and add the bot to your server.

### 3. Configure and run

```bash
cd agent
npm install
cp .env.example .env     # then edit .env
```

Put your token and channel ID in `.env`:

- `DISCORD_BOT_TOKEN` — the token from step 1.
- `DISCORD_CHANNEL_ID` — enable **Developer Mode** (Discord Settings → Advanced),
  right-click the channel → **Copy Channel ID**.

Then:

```bash
npm run bot:once   # post one status/ask message as the bot and exit
npm run bot        # stay online as the bot: reply to chatter + post on interval
```

## Asking for help / recruiting

By default the bot rotates through two asks, including recruiting someone who
knows biology / morphology. Override via `.env`:

```bash
AGENT_ASKS=Want a bio/morphology expert on the team.||Seeking nanopub collaborators.
AGENT_ASK_PROBABILITY=0.4
```

## Config (env vars / .env)

| Var | Default | Meaning |
| --- | --- | --- |
| `DISCORD_USER_TOKEN` | — | Your user token (self-bot mode, `npm start`) |
| `DISCORD_BOT_TOKEN` | — | Bot token (official mode, `npm run bot`) |
| `DISCORD_CHANNEL_ID` | — | Channel to live in (required, both modes) |
| `AGENT_NAME` | `delphisci-bot` | How the agent refers to itself |
| `AGENT_ASKS` | bio/morphology + nanopub asks | Calls for help it can post |
| `AGENT_ASK_PROBABILITY` | `0.34` | Fraction of proactive messages that are an ask |
| `AGENT_INTERVAL_MS` | `600000` | Proactive post interval; `0` disables |
| `AGENT_REPLY_COOLDOWN_MS` | `20000` | Min gap between replies to chatter |
| `AGENT_MENTION_ONLY` | `0` | `1` = only respond when @mentioned |
| `AGENT_READ_COUNT` | `15` | Messages read for context |
| `AGENT_REPO_DIR` | repo root | Repo whose status is reported |
| `CLAUDE_BIN` | `claude` | Path to the Claude CLI |

## Message generation

The bot shells out to `claude -p "<prompt>"`. To get LLM-written messages,
make sure the CLI is logged in once (`claude`, then `/login`). Without it, the
bot uses a templated fallback that still reports branch, latest commit, changed
files, and any active ask.
