# Instructions for rubric assessors

You are scoring a hackathon project snapshot against the Science Claw Hackathon judging rubric.
You are one of several independent assessors from different model providers. You work blind:
you have not seen the builders' own view of the project or any other assessor's output, and
you must not look for them.

## What you may read

Only the evidence pack at `scripts/release/self-assessment/evidence/` and the rubric at
`scripts/release/self-assessment/rubric.json`. The pack contains:

- `MANIFEST.json`: the pinned commit, capture time and SHA-256 of every file.
- `repo/`: verbatim copies of the project's README, agent notes, best-practice guide,
  collaboration log, service READMEs, the claim-test summary, assessment instructions and rubric
  used for claims, the Lean instructions and the latest executable-claim run.
- `captured/`: command outputs: the MCP overview, tests summary and candidates, MorphoEval
  live check, organisms, forum feed and requests, GitHub issues and PRs, git log, shortlog and
  stats, nanopub manifests (test vs production counts), Lean report counts, the tracked-file
  tree and the list of subagent sessions.

Do not read anything else in the repository, do not browse the web, and do not run the
project's code. If you need something that is not in the pack, say so in `missing_evidence`
and score on what is there. Reading the repository outside the pack would contaminate the
blind comparison between assessors.

## What you are judging

The rubric is the one the hackathon's judges will use (weights in `rubric.json`). Judge the
snapshot as a judge would: "Science is the benchmark. Success is not simply whether an agent
completed a task, but whether the system produced a scientifically meaningful result supported
by evidence, validation, or measurable progress", and "whether organizing capabilities as a
decentralized collective adds something beyond a single agent, isolated agents, or a
conventional workflow."

Be specific and be hard. Claims the team makes about itself count only when the pack shows the
thing (a file, a count, a test result, an external record). Distinguish what exists from what
is planned (issues, pre-registrations, offers with no reply). Where a criterion asks for a
comparison (collective capability), say explicitly whether you found one.

## Output

Write exactly one JSON file to `scripts/release/self-assessment/raw/<your-assessor-id>.json`
with this shape, and nothing else:

```json
{
  "assessor": "<your-assessor-id>",
  "rubric": "scienceclaw-rubric/0.1.0",
  "evidence_pack_sha256": "<contents of evidence/PACK_SHA256>",
  "commit": "<MANIFEST.json commit>",
  "scores": {
    "problem-significance": 0-10,
    "scientific-impact": 0-10,
    "decentralized-agency": 0-10,
    "collective-capability": 0-10,
    "execution-validation": 0-10
  },
  "bonus": 0-10,
  "justifications": {
    "<criterion-id>": "one paragraph; cite pack paths, counts, issue numbers, IRIs",
    "collaboration-bonus": "..."
  },
  "gaps": {
    "<criterion-id>": ["concrete change that would raise this score", "..."],
    "collaboration-bonus": ["..."]
  },
  "comparison_found": { "found": true|false, "where": "pack path or null", "note": "what the comparison measured, or what is missing" },
  "top_three_fixes": ["ranked: the cheapest changes that raise the weighted total most", "...", "..."],
  "highest_value_improvement": {
    "title": "one line",
    "what": "the single concrete change the team should make, specific enough to start on now",
    "why_this_one": "why it beats every other candidate on expected gain in the weighted total, given the weights",
    "expected_score_deltas": { "<criterion-id>": "+N, integers on the 0-10 scale, only criteria that move" },
    "expected_total_gain": "sum of weight x delta x 10, points on the 0-100 total",
    "bonus_delta": "0 if the bonus does not move",
    "effort": "honest hours of team work",
    "evidence_that_would_prove_it": "the file or table a judge could check"
  },
  "missing_evidence": ["things you wanted and the pack did not have"],
  "confidence": 0-1,
  "summary": "two or three sentences a judge could read aloud"
}
```

Integers for scores and bonus. `highest_value_improvement` is exactly one change, the one with
the largest expected gain in the weighted total per hour of effort that is realistically achievable
before the deadline; make its deltas consistent with the anchors. Confidence is your confidence in your own scoring given the
evidence, in [0,1]; it is not a probability that the project wins anything. Do not compute the
weighted total; the pipeline does.
