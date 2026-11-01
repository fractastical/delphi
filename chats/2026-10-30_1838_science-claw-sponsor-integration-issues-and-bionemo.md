# Science Claw sponsor integration issues and BioNeMo

- **Started:** 2026-10-30 18:38 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **Last activity:** 2026-10-30 19:45 EDT (UTC-4) through 2026-11-01 02:00, then EST (UTC-5)
- **User messages:** 5
- **Subagents:** 0
- **Transcript ID:** `22da6dfb-dc5d-445d-93e6-8169cc277bdd`

## Conversation

### 2026-10-30 18:38 — Turn 1 (User)

> make an issue for each science claw sponsor to see how to integrate their technology

**Assistant:**

I'll look in the repo for the Science Claw sponsor list first.

I'm not sure what "science claw sponsors" refers to, so let me search the repo for context.

The repo doesn't list sponsors, so I'll look up the Science Claw Hack @ MIT event.

The sponsor info isn't in the repo, so I'll need to search the web for details on Science Claw Hack @ MIT's sponsors.

Let me check the official site's sponsor section directly to get the full list.

I should fetch the site directly to get the precise sponsor list, since logos may just be images.

I need to distinguish sponsors from the "With People From" group—Harvard, MIT, UMich, Hardmode, Sundai, LAMM—so I should check how that sponsor section is structured.

I'm counting up the sponsors and partners listed—NVIDIA, Anthropic, Formlabs, Nebius, Edison Scientific, Stifel, Google Cloud, OpenAI, Romix Biosciences, alphaXiv, MIT SoE, Lila Sciences—noting that Stifel and MIT SoE don't really have tech products to integrate into something.

I'll create issues for every sponsor since the user said "each," but flag Stifel and MIT SoE honestly as likely not applicable rather than skipping them entirely. Let me check the site's challenge section for any sponsor-specific challenges to make the issues more informed.


Found 12 sponsors across three tiers: NVIDIA (Platform), Claude/Formlabs/Nebius/Edison/Stifel/Google Cloud (Builders), and OpenAI/Romix/alphaXiv/MIT School of Engineering/Lila (Supporters). Now I'll check the sponsor challenges and existing repo labels to flesh out each issue.

Since there are no existing issues, I'll create a "sponsor-integration" label and draft issue bodies grounded in each sponsor's actual tech—starting with NVIDIA's BioNeMo, ALCHEMI, and NIM microservices, thinking through an integration where agents validate claims and publish results as nanopubs with provenance, then moving to ideas for Anthropic's Claude API.

alphaXiv, MIT School of Engineering, and Lila Sciences are less clear — I should flag them for verification rather than assume specifics about their APIs. I'll keep a consistent template for each entry (context, offerings to verify, integration ideas) and write the bodies to temp files before creating them via gh in a loop script.


No existing issues or labels found. I'll create a `sponsor-integration` label and add one issue per sponsor, each outlining relevant tech, integration ideas tied to delphisci's nanopub and Delphi ontology work, and a checklist.

_Tools used: GetDynamicTools, Grep ×2, Shell ×5, WebSearch, Write ×12_

_Turn ended: error (new_message_submitted)_

### 2026-10-30 18:42 — Turn 2 (User)

> include nvidia alchmi

**Assistant:**

The issue-creation command got interrupted, so I'll check which issues were actually created.

Let me check what was created — the NVIDIA issue already includes ALCHEMI, so I should verify the current state before deciding if a separate issue is needed.

I'm noticing items 11 and 12 are missing, so I should fill those in, and I want to add a dedicated ALCHEMI issue separate from the NVIDIA BioNeMo one, while Formlabs already seems covered under #3.


Issues #1–#10 are created, with MIT School of Engineering and Lila Sciences still missing and Formlabs already covered (#3). Next I'll research NVIDIA ALCHEMI before creating its issue.

I need to create a dedicated ALCHEMI issue referencing #1 and #3, add the missing MIT and Lila issues, and update Formlabs #3 to reference the ALCHEMI loop before drafting the ALCHEMI body text.


I'll create a dedicated ALCHEMI issue covering its Batched Geometry Relaxation NIM, link it to Formlabs as a simulate-then-print pairing, note the connection on the Formlabs issue, and add the two remaining missing issues.

Now I'll cross-link the Formlabs and NVIDIA issues to the new ALCHEMI issue.

NVIDIA ALCHEMI now has its own issue, [#13](https://github.com/fractastical/delphisci/issues/13), linked to the Formlabs issue [#3](https://github.com/fractastical/delphisci/issues/3). Every Science Claw sponsor has an issue, all tagged `sponsor-integration`. I took the sponsor list from the official site, scienceclawhack.ai.

**ALCHEMI and Formlabs:** ALCHEMI is a GPU service that relaxes atomic structures with machine-learned force-field models. The issue lists its models, request format and the steps to get it running. The main idea is an agent that checks materials claims with ALCHEMI and publishes each result as a nanopub, with the model and settings recorded. The second idea is a simulate-then-print demo with Formlabs: screen candidates in ALCHEMI, print the chosen one with Formlabs' print-preparation API, and publish both results as linked nanopubs. I commented on #3 describing that pairing, and on [#1](https://github.com/fractastical/delphisci/issues/1) noting it now covers BioNeMo and general NVIDIA access.

**All issues:**
- [#1 NVIDIA (BioNeMo and general access)](https://github.com/fractastical/delphisci/issues/1)
- [#2 Anthropic (Claude, plus an MCP tool server for nanopubs)](https://github.com/fractastical/delphisci/issues/2)
- [#3 Formlabs](https://github.com/fractastical/delphisci/issues/3)
- [#4 Nebius](https://github.com/fractastical/delphisci/issues/4)
- [#5 Edison Scientific](https://github.com/fractastical/delphisci/issues/5)
- [#6 Stifel](https://github.com/fractastical/delphisci/issues/6)
- [#7 Google Cloud](https://github.com/fractastical/delphisci/issues/7)
- [#8 OpenAI](https://github.com/fractastical/delphisci/issues/8)
- [#9 Romix Biosciences](https://github.com/fractastical/delphisci/issues/9)
- [#10 alphaXiv](https://github.com/fractastical/delphisci/issues/10)
- [#11 MIT School of Engineering](https://github.com/fractastical/delphisci/issues/11)
- [#12 Lila Sciences](https://github.com/fractastical/delphisci/issues/12)
- [#13 NVIDIA ALCHEMI](https://github.com/fractastical/delphisci/issues/13)

Some issues need follow-up before they're useful:
- **Stifel and MIT School of Engineering (#6, #11):** these are a bank and the host, with no technology to integrate. The issues say so and can probably be closed.
- **Romix (#9):** I couldn't find what their technology is. The issue is a placeholder to ask them at the event.
- **Edison, Lila and alphaXiv (#5, #12, #10):** it's unclear what API access they'll give teams. Those issues start with a task to confirm that on site.

I should wrap up with a concise summary of my findings.

_Tools used: Shell ×3, WebSearch, Write_

### 2026-10-30 18:45 — Turn 3 (User)

> ok close the issues that don't need integration

**Assistant:**

I'll close issues #6 and #11 as not planned, while leaving Romix and the others open since their status is still unclear.

I closed the two sponsor issues that have nothing to integrate: Stifel Venture Banking ([#6](https://github.com/fractastical/delphisci/issues/6)) and MIT School of Engineering ([#11](https://github.com/fractastical/delphisci/issues/11)). Both are marked "not planned" with a short comment saying the sponsor has no technology to integrate.

The other 11 issues are still open. I left Romix ([#9](https://github.com/fractastical/delphisci/issues/9)) open because we don't yet know what technology they offer. Close it too if they turn out to have nothing to integrate.

_Tools used: Shell_

### 2026-10-30 18:57 — Turn 4 (User)

> make issue jsut for bionemo

**Assistant:**

I'll quickly check BioNeMo's current offerings so the issue is accurate, then create it.

I should quickly look into BioNeMo to make sure I get the details right before creating the issue and updating the comment on #1.

I created a BioNeMo issue: [#14](https://github.com/fractastical/delphisci/issues/14).

**What it covers:** the BioNeMo models NVIDIA currently offers, grouped by task:
- **Structure prediction:** OpenFold3, Boltz-2, AlphaFold2, ESMFold.
- **Protein design:** RFdiffusion and ProteinMPNN.
- **Embeddings, genomics and small molecules:** ESM2, Evo 2, and DiffDock and GenMol.

ESM2 and ESMFold can be called for free on NVIDIA's hosted site. Most of the rest need a GPU to run yourself.

**Integration ideas:**
- An agent checks a biology claim by running a model, then publishes the result as a nanopub. The nanopub records the model, its inputs and its confidence scores.
- A protein-design chain: RFdiffusion generates a backbone, ProteinMPNN designs a sequence, and Boltz-2 checks the result. Each step becomes a linked nanopub.
- Several agents each run a different model, and the nanopubs record where the models agree or disagree. That's the kind of multi-agent value the judges are looking for.

The task list starts with getting an NVIDIA API key and running ESMFold or Boltz-2 on one sequence, then prototypes the claim-to-nanopub loop.

I also renamed [#1](https://github.com/fractastical/delphisci/issues/1) to "NVIDIA (general access, NIM, DGX Spark)". I left a comment on it saying BioNeMo is now in #14 and ALCHEMI in [#13](https://github.com/fractastical/delphisci/issues/13). The body of #1 still describes BioNeMo and ALCHEMI, so it now repeats #13 and #14. Close #1 if you don't need a general NVIDIA access issue.

_Tools used: Shell, WebSearch, Write_

### 2026-10-30 19:44 — Turn 5 (User)

> forbionemo go through all of the repos and see if any could be useful for our purpose: https://github.com/orgs/NVIDIA-BioNeMo/repositories?type=all

**Assistant:**

I'll list every repo in the NVIDIA-BioNeMo organization and check each one against our use case: agents that verify biology claims and publish them as nanopubs using the Delphi ontology.

I'll use the GitHub CLI to list the repositories.

I'm narrowing down the key repos to check—bionemo-agent-toolkit, agent-for-lifesciences, BioNeMo-Inference-Runtime, and Structure-Prediction-Pipeline—and plan to pull their READMEs for more detail.


Found 27 repos in the org, with four looking directly agent-related: `bionemo-agent-toolkit`, `agent-for-lifesciences`, `BioNeMo-Inference-Runtime`, and `BioNeMo-Structure-Prediction-Pipeline`. I'll check their READMEs, along with `bionemo-recipes` and `nvMolKit`, to confirm relevance.

The toolkit is the strongest match. Next I'll check Aevom (`agent-for-lifesciences`) for the parts we'd care about: how it records state and provenance, its tool list, and whether it supports MCP.

I'm looking for more details on Aevom, this life sciences agent, including its tool list and features around provenance and state tracking.

My search didn't find the right match, but I noticed the repo has math-bio-theorems and darwin-origin projects involving nanopub building — the darwin-origin project assesses biology claims, which ties in nicely. I'll use rg on the file via shell to dig deeper.


That search hit our own repo instead of the README, but it surfaced useful context—existing nanopub-building scripts and Darwin claim assessments I'll factor into the recommendations. Now I'll re-run the search targeting the Aevom README directly.

Aevom's dynamic MCP server support means our nanopub MCP server could plug right in. I also want to check the darwin-origin biology content and see what top-level directories delphisci has.


Aevom supports loading external MCP servers at runtime, so our nanopub MCP server could plug right in. Now I'll check what biology content delphisci already has to align recommendations with our actual claims.

I should quickly check delphisci's agent directory and its darwin-origin claims to see if there's a connection, like whether Evo2 or CodonFM relate to Darwin's claims about variation.


I'll check the `agent` folder and sample some Darwin claims to figure out which BioNeMo models could actually test them, given our biology content spans Darwin's *Origin* claims and math-biology theorems like Turing patterns.

For Darwin's claims about variation and heredity, genomic models seem most relevant — I could test whether slight variations are mostly neutral or deleterious using Evo 2's variant effect scoring, or look at codon usage patterns across thousands of species with CodonFM to probe common descent. I should be honest that these are imperfect proxies, and structural models are less useful here than genomic ones.

Let me check the agent's README to understand the framework — bot.js suggests this might be a Discord bot.

Since the agent runs through the claude CLI, bionemo-agent-toolkit skills can install directly with the claude-code agent flag — this looks like a solid fit. I'll post these findings as a comment on #14.


Since our Discord agent calls the `claude` CLI, BioNeMo's agent skills can plug in directly via their `--agent claude-code` install option with no new code needed. I'll post the full review as a comment on the BioNeMo issue.

Three of the 27 NVIDIA-BioNeMo repos are directly useful, about seven more might help depending on which claims we test, and the rest aren't relevant. I posted the full review as a [comment on #14](https://github.com/fractastical/delphisci/issues/14#issuecomment-6535913056).

**Use these:**
1. **[bionemo-agent-toolkit](https://github.com/NVIDIA-BioNeMo/bionemo-agent-toolkit)** is the best fit. It's a set of ready-made agent skills for every hosted BioNeMo model, plus multi-step workflows such as align-then-fold. Our Discord agent already uses the `claude` CLI, so one install command adds the skills with no new code. We'd only add a final step that turns each result into a nanopub. It needs an NVIDIA API key but no GPU.
2. **[agent-for-lifesciences](https://github.com/NVIDIA-BioNeMo/agent-for-lifesciences)** (called Aevom) is NVIDIA's full reference agent app for molecular science. It can load external MCP tool servers while running, so the nanopub MCP server proposed in [#2](https://github.com/fractastical/delphisci/issues/2) would plug straight in. It runs on a Mac without a GPU, but the first build takes 20–30 minutes and it's research-grade software, so keep it local.
3. **[BioNeMo-Structure-Prediction-Pipeline](https://github.com/NVIDIA-BioNeMo/BioNeMo-Structure-Prediction-Pipeline)**: running it needs a GPU cluster, so that's out this weekend. What's useful is its output and its design:
   - It produced about 1.8 million protein-complex structures that are free to cite in the AlphaFold Database.
   - Each run is sealed with a verified record of its inputs and outputs, which is a good template for our nanopub provenance fields.

**Maybe useful, depending on which claims we pick:**
- **CodonFM and JEPA-DNA** are genome models that could serve as rough proxies for testing some of the Darwin claims about variation.
- **BioNeMo-Inference-Runtime** is only worth it if we get a GPU machine.
- **nvMolKit, KERMT, DualBind and RNAPro** only matter for chemistry or RNA claims.

**Not useful:** the other 16 are model-training code or generators that don't help check claims.

Our current biology content is the Darwin *Origin* claims and Turing pattern theorems. Those are about evolution and pattern formation, not molecules, so BioNeMo can only test indirect evidence for them. The comment recommends picking two or three claims with a clear molecular angle rather than running BioNeMo across the whole claim set.

I'm wrapping up my overall summary now.

_Tools used: Grep, Read ×5, Shell ×7, Write_
