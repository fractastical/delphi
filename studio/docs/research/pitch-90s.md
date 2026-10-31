# 90-second pitch — grounded, no swarm-gain assertion

**Rule:** every figure below is either verified here, or **attributed to its owner and marked
unverified**. Nothing claims a collective or swarm gain. Timing is ~155 words per 60 s.

---

## The script

> Science has a recording problem. A result that survives is written down. A result that dies
> usually isn't, and the criterion that would have killed it is written *after* the verdict, by
> whoever won.
>
> **Delphi Frontier is a store where the decision rule is attached to the question before the
> answer exists.** A Problem carries what would settle it, what would refute it, and when to
> stop. An Action can't be leased against a problem that doesn't state those. A result lands
> against a criterion that was fixed first.
>
> We ran it twice today. One test **closed positive** — a deletion absent from all 1.36 billion
> bases of a cave-fish assembly, reproducing a 2021 paper from a different fish and a different
> data type. The second **stopped itself** at a coverage floor, and that one was worth more:
> restricted to what the structure actually resolved, **22 of 95 published models already cleared
> the bar we'd written**. A pass would have been a false positive. The floor caught it.
>
> The honest numbers: **267 problems, 13 actionable, one closed loop.** Not one novelty claim of
> ours survived the day — they're all in a refutation ledger with their witnesses.
>
> On coordination we make no claim, and we can tell you why precisely. The organisers
> benchmarked it themselves and published a **regime map**: coordination improves discrimination
> only where evidence is genuinely distributed. Where one channel dominates, it improves
> *interpretation, provenance and auditability* instead. On their own four tasks it won once,
> tied at 0.955 against 0.951, was matched by a single channel alone, and on the fourth came in
> **7.2% worse** than a scripted baseline.
>
> Our closed loop was one agent running one exact scan. By their taxonomy that is a
> dominant-channel setting — so what coordination buys us is the audit trail, not the answer.
> That is what we built, and it is all we claim.

**~210 words ≈ 85 s**, leaving ~5 s of slack.

## What is shown on screen, and what it rests on

| beat | artifact | status |
|---|---|---|
| the store | `frontier/` on **main `3272d3e`**, 18 test functions | **verified here** |
| criterion-before-result | preregistration committed with no result section; criterion and inconclusive band byte-identical to the one reported against | **verified; self-attested, see caveat** |
| positive loop | exon 21 absent from 1,361,196,561 bp; flanking exons present once each | **verified**, reproduction not discovery |
| the stop | coverage 20.27% vs a 75% floor; 22 of 95 models clear +0.288 on the resolved subset | **verified** |
| forms | **3 printed forms** (6 STL: precursor short-fin, two-wing glider, four-wing glider, each + stand) | **verified on the demo branch** |
| simulations | **4 videos**: `delta_notch_replay`, `fin_mechanics`, `glide_fixed_launch`, `rd_fields` | **verified present on the demo branch; not viewed by me** |
| live corpus | **901 claims / 257 questions** | **ATTRIBUTED to codex-03, NOT verified here** — not in git; I find 21/90/310 in branch JSON. **Do not say it until its owner confirms the query that produced it.** |

## Caveats the script must survive

- **Self-attested, not witnessed.** Git order is not independent proof; we control the clock. Say
  "the criterion was fixed first and the committed file contains no result", not "git proves it".
- **The positive loop is a reproduction**, not a discovery. Pachón was never tested; n=1 per
  population; assemblies haploid, so no zygosity call.
- **No swarm or collective gain is asserted anywhere.**
- **Three claims are theirs, not ours**: dead-ends-as-typed-artifacts, a formal novelty
  definition, and the framing of verifying that provenance commutes. Cite, don't claim.
- **Main vs branch**: the store, specs and Lean are on main (18 tests). Search, beliefs, compute,
  engineering, deployment, the forms and the videos are on task branches (demo branch: 182
  tests). Name the branch or don't name the capability.

## The regime map, verbatim — use these words, they are theirs

> "a regime map identifying where coordination matters: **distributed-evidence settings**, where
> coordination improves discrimination over single-channel baselines; **dominant-channel
> settings**, where coordination mainly improves interpretation, provenance, and auditability;
> and **representational-mapping settings**, where coordination changes the object of inference
> rather than improving prediction." — arXiv:2605.22300

**Coordination made things worse in three measured places**, which is why an unconditional claim
is unsafe: retrieval@3 **0.2708 against a scripted baseline's 0.2917** (their own framing: "7.2%
worse on retrieval@3 and 120.0% better on same-class nearest-neighbour coherence"); SwarmWorld's
Discovery-AUC paired effects where **two of nine are negative and one starred** (asterisks mark
intervals excluding zero); and full culture **behind for 800 ticks** on best-artifact
performance, **never** ahead on validated invention count across 3,200.
