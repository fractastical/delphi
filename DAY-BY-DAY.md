# What we did, day by day

Log behind the animations in the [README](README.md#what-we-did-day-by-day). Each stretch names the GIF that shows it. Figures in a row are the ones printed on that card, not a later recount: the live counts are the generated table in the README. Times are Boston local, the clock printed on the cards. The design thread's decisions, failures and corrections are in [`DEVELOPMENT-RECORD.md`](DEVELOPMENT-RECORD.md). The partner repository built on these claims in the same hours, [delphi-frontier](https://github.com/kganjam/delphi-frontier), has its `git log` lined up with ours at the [end of this file](#frontier) and in full in [`swarm/frontier/GIT-HISTORY.md`](swarm/frontier/GIT-HISTORY.md).

<a id="friday-oct-30"></a>

## Friday, Oct 30 — opening evening

[![Opening evening](assets/repo-history.gif)](assets/repo-history.gif)

`assets/repo-history.gif`. Title card: 25 commits, 18:40 to midnight. `git log` for that evening has 26 non-merge commits; the last, at 23:51, publishes the Wolfram claims to the test registry. Closing card, "as of midnight":

- 880 claims from three books: Darwin 247, Thompson 291, Wolfram 321, plus 21 mathematical-biology theorem claims with LaTeX.
- 1,076 dataset-resolvability assessments (GPT and Grok; Gemini in progress) and 2,781 nanopub files.
- Claim graph, query page, MCP server (`npx github:fractastical/delphi`), Discord agent.
- Darwin's 247 and 104 Thompson claims on production; the remaining Thompson claims and rubric v0.2.0 on the test registry.

| time | what |
|---|---|
| 18:40 | README for Science Claw Hack @ MIT |
| 18:45 | Best practices, adapted from the Project Delphi ontology |
| 18:53 | Goal stated: find the fundamental theorems of biology |
| 19:25 | 247 Darwin claims extracted as nanopub drafts |
| 20:41 | Interactive claim graph; Darwin's 247 claims promoted to production |
| 20:59 | Claim graph redesigned; blind truth scores added |
| 21:44 | Darwin's 247 claims also on the test registry |
| 21:50 | Query page: filter, sort, CSV/JSON, deep links |
| 22:05 | 291 Thompson claims extracted |
| 23:08 | LaTeX notation on 71 Thompson claims that state a relation |
| 23:12 | `delphisci` MCP server, runnable via `npx` |
| 23:13 | `AGENTS.md` |
| 23:35 | 291 Thompson claims and their GPT/Grok assessments on the test registry |
| 23:46 | 321 Wolfram claims extracted, quoted and page-cited |
| 23:51 | 321 Wolfram claims on the test registry |

<a id="saturday-morning"></a>

## Saturday, Oct 31, 00:30–01:40 — organism inventory

[![Organisms overnight](assets/organisms-overnight.gif)](assets/organisms-overnight.gif)

`assets/organisms-overnight.gif`. Sixteen cloud agents, one per chapter slice of Darwin and Thompson, launched at 00:30 and merged by 01:40. Closing card:

- 782 distinct animal taxa, 3,340 located mentions, 1,372 dataset records.
- 735 GBIF keys, 649 NCBI taxids, 760 Wikidata items, 401 WoRMS ids; 88 taxa named by both authors.
- 764 GBIF occurrence counts, 239 NCBI genome assemblies, 237 PBDB and 82 OBIS counts.
- Every slice passes `organisms/validate.mjs` with 0 errors. Merged view now lives under [`test-data/organisms/`](test-data/organisms/README.md).

The merge commit is 01:40 (`Organisms: merge Thompson ch11 … all 16 slices complete`).

<a id="saturday-midday"></a>

## Saturday, Oct 31, morning — claim tests, then the ladder

[![Claims, tests, confidence, theorems](assets/claims-status.gif)](assets/claims-status.gif)

`assets/claims-status.gif`, the scoreboard as of early afternoon (the next animation starts from this card at 13:09). Between the organism merge and that card, claim-test agents pre-registered and ran Wolfram, math-bio, Darwin and Thompson tests. Verified Boston times from `git log`:

| time | what |
|---|---|
| 01:55 | Eight tests of proved math-bio laws pre-registered against public data |
| 02:13 | Four Darwin/Thompson tests pre-registered (ICS ages, LR04+EDC, NHANES, CCDB) |
| through 03:32 | Wolfram tests pre-registered, then run (rule 30, rule 110 gliders, elementary CA reversibility, and others) |
| 09:57 | README gains the illustrated summaries, including this morning's stills: [`assets/repo-snapshot.png`](assets/repo-snapshot.png) and the Nebius cell-geometry still [`assets/nebius-snapshot.png`](assets/nebius-snapshot.png) |
| 10:04 | Merged organism view grows to 22 slices, 938 taxa, 1,679 datasets; 129 claim-test results merged from 13 agent branches |
| 10:32 | Hub, swarm, holdout, Lean and organism threads land together |
| 10:44 | Class Aves confirmed as the held-out clade and re-frozen |
| 10:49 | SHA-256 attestation of every pre-registered result, draft record and frozen exam |
| 10:59 | A9 faithfulness package (issue #40): rubric, blinded prompts, runner |
| 11:03 | OpenResearch grounding for 6 headline tests; the runs are logged verbatim |

What the card itself shows:

- 880 claims extracted sentence by sentence, each a nanopublication. Darwin 247 (41 tested), Thompson 291 (31 tested), Wolfram 321 (59 tested).
- Blind truth score, mean P(true) from two assessors (GPT-5.6 Sol, Grok 4.7), scored before any test: Darwin median 0.77 (22% above 0.9, 22% below 0.5); Thompson median 0.50 (5% above 0.9, 50% below 0.5).
- 132 claims tested: 78 support, 25 mixed, 20 refute, 9 inconclusive. The 15:50 comparison card counts 131 at 13:09; both numbers are left as printed.
- 16 claims proved as theorems, all from the mathematical-biology set (the card's legend: 16 proved, 1 partial, 2 refuted). Book claims had not reached theorem status; Lean scaffolds were in progress.
- Ladder on the closing frame: 880 extracted, 859 scored for testability, 132 tested, 78 supported, 20 refuted, 16 proved. Bar lengths on that frame are logarithmic.

<a id="saturday-afternoon"></a>

## Saturday, Oct 31, 13:09–15:50

[![Since 13:09](assets/since-1309.gif)](assets/since-1309.gif)

[![Where it stands at 15:50](assets/delphi-summary.gif)](assets/delphi-summary.gif)

`assets/since-1309.gif` is the change. `assets/delphi-summary.gif` is the standing card at 15:50 (one frame).

| on the animation | what |
|---|---|
| Levin arrives | 16 papers, 310 claims, 2014–2025: bioelectric patterning, regeneration, xenobots, TAME. First tests: two refutations of a wide overlap between morphogenesis genes and learning/memory genes (0.70, 0.65), one support that higher cellular competency accelerates evolutionary search in a 1D embryo model (0.90). Thirteen more pre-registered, awaiting data. Levin's 310 are unsigned nanopubs, waiting for review. |
| Published | Thompson's 291 and Wolfram's 321, with assessments, signed and pushed to production. Live nanopubs 372 → 880 (Darwin 247, math-bio 21, Thompson 291, Wolfram 321). The production publish commit is 14:07. |
| Theorems | 16 → 63. The 47 Thompson claims machine-checked in Lean 4 (no `sorry`, standard axioms only) now count beside the 16 proved in the literature (Fisher, Turing, Kimura, Hamilton, Maynard Smith). |
| Two axes | The claim table counts tests against data separately from proof. A data verdict does not make a claim a theorem. At 15:50: Darwin 41 tested, Thompson 31 tested of which 47 are theorems. |

Before → now, as the closing frame prints it (13:09 against 15:50):

| | 13:09 | 15:50 |
|---|---:|---:|
| claims | 880 | 1,190 |
| live as nanopubs | 372 | 880 |
| theorems | 16 | 63 |
| tested against data | 131 | 133 |
| tests pre-registered, awaiting data | 0 | 13 |
| thinkers | 8 | 9 |

The 15:50 standing card agrees: 1,190 claims from 9 thinkers (1859–2025), 880 live, 63 theorems (47 Lean-checked, 16 literature), 133 tested (78 supports, 25 mixed, 21 refutes, 9 inconclusive), 938 animal taxa and 1,679 dataset records. Its footer: a proof is not evidence that organisms satisfy it, and a data test is not a proof.

<a id="overnight"></a>

## Saturday night into Sunday morning — Oct 31, 16:08 → Nov 1, 09:54

[![Overnight](assets/overnight-nov1.gif)](assets/overnight-nov1.gif)

`assets/overnight-nov1.gif`. Title card: 421 commits from three authors; claims 1,190 → 1,763 as Aristotle's 566 arrive; tested against data 133 → 174; theorems 63 → 91; self-assessment 58 → 72.8 / 100 after the four-arm comparison joined the evidence; four forecasters price 27 open problems.

The hour card attributes the 421 by author date since 16:08: Joel Dietz 104 (claims, tests, publishing), Amit Shenoy 313 (the design thread: Lean checks, the 3D blueprint, graph views), Ashley 4 (claim grounding). The 09:00 bar is the night's uncommitted work landing. Hours the card annotates:

| hour | what the card says |
|---|---|
| 16:00 | Design thread: Lean checks, 3D blueprint, graph views |
| 17:00 | Claim-test swarm: 20 pre-registered, 17 run |
| 00:00 | Aristotle's 566 claims; claim graph rebuilt |
| 01:00 | 1,496 nanopubs to the test registry |
| 09:00 | Merge; pine-cone bilayer test, formalization tags, Hardy–Weinberg and Price drafts |

The rest of the animation, in the order it plays:

1. **21 tests logged**, each pre-registered before any data was fetched. The frame lists them with verdict colour from 17:12 (rule 30 from a single black cell, supports) through 23:43 (cylinders or spheres in full surface contact, refutes), across Wolfram, Levin, Darwin and Thompson.
2. **Tested against data, 133 → 174.** At 16:10 the split is 78 supports, 25 mixed, 21 refutes, 9 inconclusive. A data verdict does not make a claim a theorem.
3. **Faithfulness gate, 33 tests.** Role A9: does the analysis measure what the claim asserts? GPT-5.6 Sol judged first; Grok 4.7 gave a blind second opinion on every not-representative call. 22 faithful or narrower, 6 contested, 5 agreed not representative. A not-representative verdict is reported beside the data verdict and is not used to edit it. Same split as the README's generated table (33 of 174; 5 not representative, 6 contested).
4. **Theorems, 63 → 91.** Of the Lean-checked ones, 47 were already counted at 16:10 and 26 were added overnight (73). New modules named on the card: HollowTube, MurrayCubic, LimbBoneSimilarity; TwelvePentagons and HamiltonScope reworked. No `sorry`, standard axioms only. The generated README table splits the 91 as 73 Lean-checked and 18 proved in the literature.
5. **Design thread.** 313 commits. By topic on the card: Lean checks 70, claim and problem graph 30, 3D blueprint and viewers 27, gene pathways 17, prior art 15, open problems 15, figures 15, dashboard 15, physics 13. 152 Lean theorems compile, 0 `sorry`, 0 non-standard axioms; 57 of 57 statement mutants rejected. The pre-registered winged-zebrafish test failed: 1 of 10 axes scorable. Narrative, including that failure, is [`DEVELOPMENT-RECORD.md`](DEVELOPMENT-RECORD.md).
6. **Signed and published to the test registry**, with the operator's ORCID key. Production still holds the 880 Darwin, Thompson, Wolfram and math-biology claims. Overnight on the test registry: 1,496 Aristotle and Levin claim nanopubs with assessments; 11 cell-geometry evidence items (8 corrected, then 3 that supersede their predecessors); 3 self-assessment round-2 nanopubs, one per assessor. Nanopub files in the repo: 5,787 → 8,890.
7. **Self-assessment, 58 → 72.8** of 100. Science Claw judging rubric. Three blind assessors (GPT-5.6 Sol, Gemini 4 Argon, Grok 4.7) re-rated after the four-arm agent comparison joined the evidence pack. Round 1 is archived beside round 2. Largest change is collective capability, 3.3 → 8 (weight 25%). The other criteria, out of 10: problem significance 8.3 → 8, scientific impact 6.7 → 7, decentralized agency 4.7 → 6, execution and validation 7 → 7.3. The comparison itself is [`test-data/agent-comparison/SUMMARY.md`](test-data/agent-comparison/SUMMARY.md); the swarm thread had finished earlier on Saturday, and this card is the re-rate once that evidence was in the pack.
8. **27 open problems, priced blind** by Claude Opus 5.5, Gemini 4 Argon, GPT-5.6 Sol and Grok 4.7. Dots are the median chance a problem is settled within 30 days.
9. **First problem run: the species-area exponent.** Pre-registered before any richness value was seen, then run on 1,124 GIFT islands. Pooled z = 0.307 (95% CI 0.295 to 0.319). Regional exponents range from 0.14 to 0.49, so one universal z fails. 22.6% of plausible sampling-only nulls land in 0.15 to 0.35; the null fails its own criterion. Preston's canonical lognormal, 0.264, reproduced.
10. **Tooling**, several of them local prototypes: a federation prototype (signed ed25519 statements that a Lean proof or data test reproduced); MCP tools `delphi_claim_tests` and `delphi_morpholib`; claim grounding to INDRA (Gilda) and OLS; a pattern atlas and a four-slide deck. Sunday morning on the same card: the pine-cone bilayer-curvature test completed (supports, n=2, confidence 0.4); a formalization tag on every math-bio claim; unsigned drafts for Hardy–Weinberg, the Price equation and the hygromorph claims.

Before → now, 16:10 on Oct 31 against the morning of Nov 1:

| | 16:10 | morning of Nov 1 |
|---|---:|---:|
| claims | 1,190 | 1,763 |
| theorems | 63 | 91 |
| tested against data | 133 | 174 |
| tested on organisms | 66 | 90 |
| nanopub files in the repo | 5,787 | 8,890 |
| open problems | 20 | 27 |
| self-assessment, of 100 | 58 | 72.8 |

The README's generated table (2026-11-01 15:21 UTC) still matches the morning column on claims, theorems and tests. One commit after the animation, at 10:49, corrects the README: the 880 production nanopubs were published on the hackathon's first night, not before it.

<a id="frontier"></a>

## The partner repository, in the same hours

[delphi-frontier](https://github.com/kganjam/delphi-frontier) (MorphoSwarm Frontier) was built during the same event on this repo's claims and MCP server; its adapter shows up in our MCP log as the `frontier-adapters` client, 30 sessions on Oct 31 ([`COLLABORATIONS.md`](COLLABORATIONS.md)). Their curated build record is crawled in [`swarm/frontier/BUILT.md`](swarm/frontier/BUILT.md). This section is the uncurated one: their `git log`, next to ours, on the same clock. The tables are generated by `node swarm/frontier/git-history.mjs` from [`swarm/frontier/git-history.json`](swarm/frontier/git-history.json), which holds every commit; the per-stretch reading, with their commit subjects quoted and linked, is [`swarm/frontier/GIT-HISTORY.md`](swarm/frontier/GIT-HISTORY.md).

Their repository opens at 10:49 Boston on Saturday Oct 31 (`Initial commit`, then `Seed Delphi Frontier with the verified artifacts and the verification rules`), sixteen hours after ours; nothing of theirs overlaps the Friday evening or the organism inventory. From 14:00 Saturday the two columns cross: ours is busiest before noon, theirs from 15:00 on, with its largest hour at 18:00 Saturday evening when ours had slowed to a few commits, and a second peak at 01:00 Sunday as the night's results landed on both sides. The adapter sessions that read our claims (18:10–18:51 UTC, 14:10–14:51 Boston) fall in the hour their `frontier_adapters` and bulk-import commits appear. Commits are code activity: their own audit says every reviewer there shares one git identity, and a count of commits says nothing about participants, results or which side was reading the other at a given hour.

<!-- frontier-git:start -->
<!-- Generated by node swarm/frontier/git-history.mjs from swarm/frontier/git-history.json (retrieved 2026-11-01T16:03:58.324Z). Edit the script, not this block. -->
Commits per hour, author date, America/New_York. Delphi is this repository since 2026-10-30 18:00; Frontier is the default branch of [kganjam/delphi-frontier](https://github.com/kganjam/delphi-frontier) at `11b9e74`. Commits are code activity, not agents or results.

| hour | Delphi | Frontier |
|---|---:|---:|
| 10-30 18:00 | 3 | 0 |
| 10-30 19:00 | 1 | 0 |
| 10-30 20:00 | 2 | 0 |
| 10-30 21:00 | 4 | 0 |
| 10-30 22:00 | 2 | 0 |
| 10-30 23:00 | 14 | 0 |
| 10-31 00:00 | 210 | 0 |
| 10-31 01:00 | 165 | 0 |
| 10-31 02:00 | 20 | 0 |
| 10-31 03:00 | 5 | 0 |
| 10-31 09:00 | 3 | 0 |
| 10-31 10:00 | 116 | 2 |
| 10-31 11:00 | 49 | 0 |
| 10-31 12:00 | 90 | 6 |
| 10-31 13:00 | 79 | 17 |
| 10-31 14:00 | 65 | 69 |
| 10-31 15:00 | 12 | 125 |
| 10-31 16:00 | 26 | 104 |
| 10-31 17:00 | 63 | 80 |
| 10-31 18:00 | 23 | 168 |
| 10-31 19:00 | 10 | 130 |
| 10-31 20:00 | 3 | 125 |
| 10-31 21:00 | 0 | 92 |
| 10-31 22:00 | 6 | 84 |
| 10-31 23:00 | 16 | 79 |
| 11-01 00:00 | 35 | 66 |
| 11-01 01:00 | 21 | 155 |
| 11-01 02:00 | 1 | 41 |
| 11-01 08:00 | 1 | 2 |
| 11-01 09:00 | 10 | 4 |
| 11-01 10:00 | 1 | 1 |
| 11-01 11:00 | 0 | 1 |
| **total** | **1,056** | **1,351** |

| stretch | Delphi | Frontier | Delphi by commit date | Frontier by commit date |
|---|---:|---:|---:|---:|
| [Friday Oct 30, opening evening](#friday-oct-30) | 26 | 0 | 26 | 0 |
| [Saturday Oct 31, 00:00–01:40, organism inventory](#saturday-morning) | 363 | 0 | 363 | 0 |
| [Saturday Oct 31, 01:40–13:09, claim tests, then the ladder](#saturday-midday) | 295 | 11 | 112 | 11 |
| [Saturday Oct 31, 13:09–16:08](#saturday-afternoon) | 159 | 222 | 48 | 222 |
| [Saturday night into Sunday morning, Oct 31 16:08 → Nov 1 09:54](#overnight) | 211 | 1,115 | 505 | 1,115 |
| Sunday Nov 1, after 09:54 | 2 | 3 | 2 | 3 |

The two date columns differ where work was rebased before it reached the default branch: 416 of Delphi's 1,056 commits and 13 of Frontier's 1,351 carry an author date that is not their commit date. Saturday Oct 31, 01:40–13:09, claim tests, then the ladder: Delphi 295 by author date, 112 by commit date; Frontier 11 and 11. Saturday Oct 31, 13:09–16:08: Delphi 159 by author date, 48 by commit date; Frontier 222 and 222. Saturday night into Sunday morning, Oct 31 16:08 → Nov 1 09:54: Delphi 211 by author date, 505 by commit date; Frontier 1,115 and 1,115. Author date is when the work was done; commit date is when it landed. The overnight card's own count (421 at 09:54) was taken at that moment from a different head and is left as printed.
<!-- frontier-git:end -->
