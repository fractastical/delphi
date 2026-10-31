# Architecture issue: five-agent pipeline, orx and BioNeMo roles

- **Started:** 2026-10-30 23:20 UTC-4 (EDT)
- **Last activity:** 2026-10-30 23:25 UTC-4 (EDT)
- **User messages:** 1
- **Subagents:** 0
- **Transcript ID:** `1d4b5bec-3491-4b9c-b648-fb2717728413`

## Conversation

### 2026-10-30 23:20 — Turn 1 (User)

> evaluate this in an architecture issue

**Assistant:**

I need to figure out what "this" refers to. Let me look at the repo for existing architecture issues and recent context.

It's unclear what "this" refers to since there's no attached file or selection, so I should check the repo for any existing architecture issue documents or recent context that might clarify what needs evaluating.

No architecture issues found on GitHub. I should check the full issue list and recent transcripts to figure out what "this" refers to, and also check the remote.

Issue 16, the most recent one about using OpenResearch as the research-agent harness, was created roughly 2.5 hours ago. I notice issue 11 seems to be missing, possibly closed, and I'm wondering if this warrants evaluation in a separate architecture issue.

Since recent transcripts look like subagent batch runs, I'm trying to trace back to the parent chat that created issue 16, searching for mentions of "orx," "OpenResearch," or "architecture" in the query logs.

The most recent parent chat at 23:19 asked about using the openresearch harness, which led to issue 16. I should check the full tail of that conversation to figure out what "this" refers to in the last exchange.

"This" probably points to the bioelectric falsifiable-question note from the OpenResearch Delphi project that was just removed — so the user

I'm looking at the five-agent architecture proposal shared by a teammate, which covers extracting math models from literature, formulating theorems, collecting test datasets, publishing nanopub evidence, and applying the theorems—mostly built on OpenResearch harnesses with one step unassigned. I need to assess this structure for the GitHub architecture issue.

I want to ground this evaluation in actual repo facts—README goals, current extraction/assessment/publishing pipelines, the MCP server setup, and related issues on BioNeMo, orx, and alphaXiv—plus what I know about OpenResearch's coding-agent harness capabilities for literature search and experiment management to judge fit for the first three steps. I should check the README, BEST_PRACTICES doc, the orx skill file, issue 14, and the repo's pipeline structure before drafting the issue.


I'll review the teammate's proposed agent/harness breakdown against how the repo and available harnesses actually work, then file the findings as an architecture issue. Starting by gathering the relevant facts.

I want more detail on how extraction currently works—INSTRUCTIONS.md for extraction and assessment, the multi-agent setup via Cursor subagents, which models assessors.json references, the publish pipeline details, and orx's actual capabilities to see how well steps 1-3 fit. Let me run `orx skill` and check a few files, including the truth folder.

Since orx isn't on PATH here, I need to source the cargo env first, then try running `orx skill` directly to see what OpenResearch actually supports. I also want to peek at the math-bio-theorems work to see how those theorems were formalized—checking for LaTeX or Lean usage, and whether BEST_PRACTICES mentions Lean at all.

I think I have enough to write a solid evaluation, but let me double-check the best practices doc for the pipeline model and stub proofs warning, plus how nanopubs get signed with the ORCID key during publishing.

I now have enough to draft the evaluation issue, outlining Kavita's proposal: extracting math models from literature, formulating theorems for each, collecting test datasets, publishing evidence as nanopubs (no harness), and using the theorems for generation/simulation.

Overall, the five stages align with the pipeline we already run, and the harness-per-agent principle matches our best practices around separating assessor from builder, using different providers, and linting before publishing. I agree with the decomposition but disagree with some harness assignments, think assessment/audit (the dual-agent scoring step we've used for 538 claims) is missing as a stage, and think "harness" is being conflated with "tool" — harness should mean where an agent runs and what policies govern it, while tool is what it calls.

Looking at extraction specifically, OpenResearch seems like a weak fit since its model is built around experiment trees, fixed run commands, and frozen nodes running on compute, whereas extraction today is just document processing done by Cursor subagents reading chapters and producing verified JSON output with no run command or metrics involved.

However, OpenResearch's literature discovery and paper tools seem like a good fit as tools for extracting from papers rather than books. The real policies needed — verbatim quotes verified against source, no modern knowledge injection, no invented identifiers, one proposition per claim — are currently enforced by instructions and post-check scripts, so I'm thinking the harness should formalize that enforcement. My recommendation is to keep extraction as a batch-job harness using the literature tools as a source, and only commit it as a proper OpenResearch experiment once extraction quality becomes measurable, with a run command that chains the extraction and checking scripts and lets the prompt/model vary as committed config.

For theorem formulation, the obvious harness is one with a Lean proof checker in the loop — run `lake build` and record which theorems compile with zero sorries, treating each theorem/variant as a branch with pass/fail plus sorry count as the result. This fits OpenResearch's fixed-run-command model well, though I need to guard against stub proofs and make sure formal status gets recorded in the claim since a theorem compiling isn't the same as truth about organisms — without Lean in the loop, it's just more LLM text and OpenResearch doesn't add much. Now I'm turning to dataset collection as the third case to evaluate.

What's actually missing is the assessment/audit stage itself — dual agents from different providers, blind to each other's outputs and the builder's guesses, producing calibrated scores with consistent verdicts. That's steps 7-8 of the loop, and publishing as nanopubs needs the strictest harness of all since it's irreversible: signing key management, test registry first, lint gates, and the agent probably shouldn't hold the signing key at all — maybe it just produces unsigned TriG for a human to review and sign.

For simulation, BioNeMo is really a toolset for molecular-level claims (folding, binding, sequence) rather than a general harness, and our current claims operate at the organism/population level (Darwin, Thompson, Fisher, Turing) which it doesn't cover. OpenResearch looks like the better fit as the actual simulation harness, with a fixed run command.

Each stage's output should cite the previous one in the provenance chain, and I should map where team members plug in: Cursor/Claude Code for stages 1, 2's LLM part, and 3b; OpenResearch for Lean runs and stage 5; humans for the stage 4 gate. Now I'll draft the revised table and checklist, then create the repo issue with an "architecture" label (using gh with the renamed fractastical/delphi repo and delphisci remote) — though I can't easily attach the screenshot via gh.

I'll attribute the proposal source to the team WhatsApp chat (Kavita) modestly rather than quoting the screenshot directly, write the issue body to a temp file for gh issue create, cross-reference issues #16, #14, #10, and note there are no Lean files in the repo yet. I also want to tally up the claim counts: 291 + 247 + 18 + 3 = 559 total claims, with 494 dataset-resolvability assessments across the 247.

Since the Darwin claims were only assessed by 2 reviewers locally and the Thompson ones haven't been merged yet, only the 247 Darwin claims count in the overview. Truth scores live in docs/claims.json, so I'll stick to conservative, verified facts when drafting the issue.


I have the information I need—now I'll assess the proposal's five agent-to-harness mappings against the repo's existing functionality, orx's actual capabilities (experiment tree, fixed run command, lit search), and BioNeMo's actual scope (molecular NIMs), then file my findings.

I should swap the relative link for the full GitHub URL since relative links won't resolve in an issue, then proceed to create the label and the issue.

Filed as [issue #17](https://github.com/fractastical/delphi/issues/17), with a new `architecture` label. It quotes the five-agent proposal from the chat and evaluates each stage against what the repo does today, what `orx` actually is, and what BioNeMo actually is.

The verdict in short:

- **The five stages are right**, and so is the "each agent in a harness with policies" principle; it matches `BEST_PRACTICES.md` (`assessor != builder`, different providers, lint before publish).
- **The harness assignments are mostly backwards.** OpenResearch is an experiment tree with one fixed run command and frozen runs on compute. That fits stage 5 (simulation across organisms, where the $500 GPU credits get spent) and stage 2 once Lean 4's `lake build` is the run, but adds nothing to extraction, which is LLM document work with no run and no metric. Its lit-search commands (`orx discover`, `orx paper`) are useful tools for stages 1 and 3, separate from using it as the harness.
- **BioNeMo is a toolset, not a harness**, and it covers molecular-scale claims only. None of the 559 current claims (allometry, growth form, Fisher, Turing) can be simulated with it; it needs its own subset of claims (#14).
- **One stage is missing:** blind, multi-provider assessment. That's most of what the repo contains (494 resolvability assessments plus truth scores) and it needs the strictest read-isolation policy.
- **"NA" for publishing is right only as "no autonomous agent".** It's the irreversible, key-holding step, so it needs the tightest gate: agents emit unsigned TriG via PR; lint and test registry pass; a human runs production.

The issue ends with a revised stage/harness/tools/gate table and a decision checklist, including updating #16 so OpenResearch's task list covers only the stages it actually owns (2, 3a, 5).

_Tools used: Grep, Read ×5, Shell ×20, StrReplace, Write_
