# let's do an udiot of our current repo organizaiotn es as it goes to contest rule

- **Started:** 2026-11-01 12:01 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-11-01 12:08 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `87f3872c-8c93-40bb-8de5-f25b298db177`

## Conversation

### 2026-11-01 12:01 — Turn 1 (User)

> let's do an udiot of our current repo organizaiotn es as it goes to contest rules

**Assistant:**

I'll audit the repo's organization against the contest rules. First I'll find those rules and the current layout so the comparison is against the actual documents.

The first pass shows this is tied to the ScienceClaw hack. I'll pull the published contest rules and compare them to how the repo is actually laid out.

The judging rubric is in the repo already. I'll read that against the live site and the top-level layout so the audit is about what a judge would actually see.

The rubric is clear; the repo has several front doors. I'll map the top-level layout onto the five judging criteria and the collaboration bonus.

The contest does not prescribe a folder layout. The gap is whether a judge can score the five rubric rows from how the repo is organized. I'll put that map in a canvas you can open beside the chat.

The published ScienceClaw rules score five weighted rows. They do not specify a folder layout, a license, or a ban on work started before the event. The repo already holds evidence for every row. A judge still cannot score it from the way the tree is organized.

The full map is in [Contest repo audit](/Users/jdietz/.cursor/projects/Users-jdietz-Documents-GitHub-dev-delphisci/canvases/contest-repo-audit.canvas.tsx), a live view you can open beside the chat. It is a canvas because the findings are a table of rubric rows against paths, and that is easier to scan than a write-up.

What fails first:

- **No judge map.** `README.md` never names the rubric. The blind score (mean **72.8 / 100**, commit `08fd5b3c` at 05:10 UTC) lives at `scripts/release/self-assessment/SUMMARY.md` and is not linked from the README. That pack is already behind the numbers table regenerated at 15:21 UTC.
- **Two problem lists, zero shared ids.** `problems/problems.json` has **27** attackable problems (7 A, 13 B, 7 C). `open-problems/problems.json` has **215** source-list items. `AGENTS.md` and the assessors still say 20.
- **The first screen quotes three theorem counts.** The generated table says **91** (73 Lean, 18 literature). The same README describes the Lean page as **53**. The blind pack scored **87**.
- **The 25% collective row is one paragraph.** The comparison is `test-data/agent-comparison/SUMMARY.md` (multi-agent arms beat a single agent by at least 4 of 20 verified dataset URLs). The null — Aristotle Book VI, no swarm advantage — is under `scripts/release/agent-comparison/`. `swarm/` is the control sketch and the Frontier crawl, not that experiment.
- **17 of 40 root directories are unnamed in the README**, including `omics/` (3,905 tracked files, the fourth-largest tree). `problems/README.md` still says nothing there is solved, while `problems/runs/` already has three runs and `species-area-exponent` has a `RESULTS.md`.

What is solid: the four-arm comparison is pre-registered and reports its nulls, Lean reports and claim-test verdicts are real, and the MCP server and forum are running systems. Sponsor use is one file per sponsor.

Before the 14:30 slides, the useful change is one root page: five rubric rows, one path and one current number each, the 27-problem list named as the one in scope, and the three runs pointed at from that page. Moving the 31,883 tracked files would not help a judge.

_Tools used: GetDynamicTools ×2, Glob ×5, Grep ×9, Read ×17, Shell ×5, WebSearch, Write_
