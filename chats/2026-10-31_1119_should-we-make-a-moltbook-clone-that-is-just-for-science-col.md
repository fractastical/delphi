# should we make a moltbook clone that is just for science collabs?

- **Started:** 2026-10-31 11:19 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-31 11:19 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `47ac694b-398f-4c47-a2da-75b1545f3404`

## Conversation

### 2026-10-31 11:19 — Turn 1 (User)

> should we make a moltbook clone that is just for science collabs?

**Assistant:**

Worth a quick look at what's already in the repo before answering.

Actually, I recall the repo already has a `forum/` directory described as a Moltbook-style board for agents to post their work. Let me check forum/README.md to give a properly informed answer.

You already have one: `forum/` is exactly this. It's untracked (not yet committed) but complete: ~1,400 lines, zero-dependency Node + SQLite, with the Moltbook shape (register → API key, labs/submolts, posts, threaded comments, votes, karma, `/home`, heartbeat file) plus the science-specific parts: `artifact`/`request`/`result` post kinds, required URL on artifacts, claim ids on posts so `GET /api/v1/claims/:id/posts` groups a claim with its tests, an offer/accept collaborator flow, skills on profiles, a seed script that posts this repo's artifacts, a CLI, and a Fly.io Dockerfile/`fly.toml`. The README is at `forum/README.md`.

So the real question is not "should we build it" but "should we commit it and put it somewhere," and whether it's worth running at all. My honest assessment:

Arguments for keeping it:
- The science-specific bits are genuinely different from Moltbook. Tying posts to claim ids means results accumulate against a claim rather than scrolling away, which is the thing delphisci's nanopubs want and a generic feed can't do.
- The request → offer → accept flow gives agents a concrete way to find each other for tasks like "resolve these 40 Darwin taxa to GBIF," which is the collaboration pattern this repo already uses.
- Zero deps and a single SQLite file means it costs almost nothing to host.

Risks:
- Moltbook's lesson is that a board with only one operator's agents posting is a diary, not a forum. The seed posts as `delphisci`; without external agents reading `/skill.md` and registering, there's no network effect. You'd need to actively invite a few other agent operators (Moltbook-adjacent people, INDRA folks, the math-bio Lean crowd) at launch.
- Moderation. There is no human verification step by design ("the operator controls who gets the URL"), so if the URL leaks you get spam fast. Rate limits exist but no ban/moderation endpoints that I can see in the README.
- It duplicates Moltbook's social surface. An alternative is to skip the social layer and only keep the pieces Moltbook lacks: a claims → results index and a request board, and post links to those *on* Moltbook (`agent/moltbook.mjs` already drafts posts there). That gets the audience for free and avoids running a second community.

My recommendation: commit `forum/` since it's done, but deploy it as a narrow "claims + collab board" and cross-post to Moltbook from `agent/moltbook.mjs` rather than trying to be a Moltbook competitor. Add a minimal moderation path (operator key to delete posts/ban an agent) before making the URL public. If you want, I can wire the moltbook cross-posting, add the moderation endpoints, or just commit the forum as-is.

_Tools used: Read, Shell_
