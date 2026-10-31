# Prior-art differentiation

**What this is:** the compact matrix. The raw research sits in
`/data/artifacts/delphi-evolve-rethink/messages/` (ASK 466 lines, Buehler 1,097 lines) and is a
working artifact, not a deliverable. Machine-readable form: `data/research/prior-art.json`.

**Evidence basis.** Every row carries a current commit SHA, the command that produced a count
(with a control wherever a zero is reported), and a read-level for every paper. **No broad
novelty claim, no baseline claim inferred from a snippet, and no swarm or collective gain
assertion appears anywhere in this document.**

---

## 0. A correction that changes how we may describe our own work

**Git commit order is not an independent witness.** I repeatedly wrote that a preregistration at
`10:29:30` preceding a result at `10:52:30` proves the criterion was not fitted afterwards. **It
does not.** Commit timestamps are author-supplied and we control both the clock and the history.
That is a *self-attestation*.

What survives is the **content** check, which is the real evidence: the committed preregistration
contains no result section, and its acceptance criterion and inconclusive band are byte-identical
to the ones reported against (`sha256 affabcd2…`). That demonstrates **internal consistency, not
priority**.

An independent witness would be a third-party timestamp — OpenTimestamps, a public registry, a
signed receipt from a service we do not control. **We have none.** Until we do, the phrase is
**"self-attested preregistration"**.

---

## 1. The three entities, identified from primary sources

| | what it is | status |
|---|---|---|
| **ASK** | *Active Scientific Knowledge*, **Mehmet Fırat, sole author**, Anadolu University. DOI `10.2139/ssrn.7416579`, deposited 2026-09-14 | **unreviewed preprint, 0 citations**, read at **full-text** |
| **ScienceClaw** | `lamm-mit/scienceclaw` — Buehler's LAMM group at MIT, who judge this hackathon | main `894598cd3a` (2026-10-30); categorical code only on branch `38b2f681e8` |
| **Infinite** | `lamm-mit/infinite` — publication and discourse layer | `699b90a422` (2026-04-16), **unchanged** |

**Citation hazard:** Crossref *and* OpenAlex record ASK's author as "Mehmet anon". And the arXiv
API returns **"Fiona Y. Wong"** where the paper's own title block says **Wang** — she is first
author on the categorical framework, ScienceClaw and the MRS perspective. Cite the byline, never
the metadata.

## 2. Inherited record versus current

| | inherited | current | consequence |
|---|---|---|---|
| scienceclaw | `ab9aba1302`, "no new commits" | **`894598cd3a`, 2026-10-30** | **inherited record is now FALSE** |
| infinite | `699b90a422` | `699b90a422` | inherited record still accurate |

The scienceclaw move is 2 commits / 9 files — LLM-client, JWT and dry-run fixes plus 4 test files
— touching **nothing** under `artifacts/`, the pressure formula, the mutator, the needs layer or
the type vocabulary. Code findings therefore survive, **stated as a diff rather than assumed**.
`categoryscienceclaw/` does not exist on main at all (contents API "Not Found" at `894598cd3a`;
20 entries at `38b2f681e8` as the control); it is a branch **diverged** since 2026-05-21, and is
the URL arXiv:2606.01444 itself cites.

One inherited criticism **went stale yesterday**: "only one test file exercises project-specific
core behaviour" — 503 lines of project-specific tests landed 2026-10-30 and have not been read.

## 3. Feature matrix — implemented versus claimed

`✔` implemented and verified · `◐` present but weaker than it reads · `✘` absent, measured with a
control · `—` not addressed

| dimension | ASK (paper) | ScienceClaw / Infinite | Ours |
|---|---|---|---|
| question routing | — | `/api/discovery` ranks by `desc(createdAt)`, **pure recency** | ✘ not implemented |
| model coupling, typed contexts | ✘ conceptual only | ✔ real: copresheaves, categories of elements, left Kan extension, 8 proved propositions (2606.01444) | ✘ |
| evidence contests | ◐ proposed, no mechanism | ✔ `cite/contradict/extend/replicate`, multi-validator consensus | ◐ dispute/fork implemented, unexercised |
| artifact lineage | ✔ central to the model | ✔ **rejected nodes parent accepted ones**, with `rejected_reason` | ✔ append-only versioned store (main) |
| active learning | ✘ | ✘ | ✘ |
| multi-operator federation | ✔ one of its six dimensions | ◐ Infinite threads | ✘ **bundle test runs two stores in one process** |
| verification (machine-checked) | — | ✘ **zero** `.lean/.v/.thy/.agda/.smt2/.mlw`; their certificates are structural and two are weak | ✔ Lean on main; mutation-killed tests |
| engineering vs discovery | — | ✔ 2604.26367 **fabricates specimens**, 4 cases, 0.1–6.6% error | ◐ 3 print forms, 4 videos — **demo branch only** |
| **epistemic objects for plans / experiments / actions** | ✘ closed list of seven; no plan, no experiment | ◐ `Need`, `HypothesisIteration`, SwarmWorld bounded plan — **but gates live in the accepted artifact** | ✔ Action carries acceptance criteria, falsifier, stop rule |
| **collective-RL governance** | ✘ all ten terms zero | ✘ **ruled out deliberately** | ✘ not implemented |

**Controls behind the zeros.** ASK: `reinforcement/reward/feedback/policy/bandit/active learning/
optimiz*/prioriti*/allocat*/incentive` all 0 across 11 pages; `conformance/conform/compliant/
specification/acceptance` all 0. ScienceClaw: zero proof-assistant files against **544 `.py` /
999 `.md` / 91 `.json`** on main (2,177 blobs) and again on the branch; `acceptance_criteri` 0
files, `stop_rule` 0, `preregist` 0, `falsifi` only inside LLM prompt strings.

## 4. What we may and may not say

**MAY — the one defensible sentence:**
> **They have the objects; we add the decision rule to the object, before the result exists.**

Their gates are real but live in code and in the **accepted** artifact's payload — the HEA
`gate_rule` is recorded *inside the winning model*, so the criterion is written **after the
verdict, by the winner**. Ours is a typed `Action` carrying acceptance criteria, a falsifier and
a stop rule, written before. *(With §0's caveat: self-attested, not independently witnessed.)*

**MAY — machine-checked verification**, stated narrowly: *no `.lean/.v/.thy/.agda/.smt2/.mlw` in
these three repositories at these SHAs* — **not** "they do not do verification".

**MAY NOT — any collective or swarm gain claim.** See §5.

**MAY NOT — typed research objects, independent review, or dead-ends-as-artifacts as ours.**
Already implemented and published: a node with `status: "rejected"` and a `rejected_reason`,
**parenting the accepted model**.

**MAY NOT — a formal non-subjective novelty definition as ours.** 2606.01444 defines discovery as
residual content outside the image of the Kan comparison map, explicitly to avoid "subjective
novelty".

**MAY NOT — "we thought of verifying provenance".** Their §3 outlook already lists as future work
that the system *"could verify that provenance diagrams commute, that every public claim has an
admissible artifact path, that retractions and supersessions preserve old evidence."* We may say
we implemented something they listed as future work. **We must cite them.**

**MAY NOT — ASK conformance.** ASK defines none, has no implementation, and the six-dimensions-as-
acceptance-criteria reading is **entirely our construction**. SPEC-087 already says so.

**A trap to expect:** *"Publication under ASK can be understood as a proposal to change a shared
knowledge state"* — the paper's only use of "proposal". It means a **diff to the knowledge
graph**, not an action proposal. It does not say what it looks like it says.

**Records over voting.** Our ordering is by typed record content. We implement no vote, and
Infinite's reputation gates *who may post*, not what gets attempted.

## 5. Collective capability — the judges measured it and mostly refuted it

**arXiv:2605.22300** (F. Y. Wang & Buehler): coordinated vs single-agent on the same tasks,
comparator matched on inputs, 19 arms, 11 controls, 28 metrics, frozen panels of 24–32.

| task | coordinated | single-agent | verdict |
|---|---|---|---|
| Climate-Vector | AUROC 0.944 | +0.208 worse | **wins** |
| Cosmic Filter | 0.955 | 0.951 | **tie** |
| Computational Kuhn | 0.9688 | 0.969 | **no gain** |
| Sound of Molecules | retrieval@3 0.2708 | loses to chemistry baseline | **non-predictive** |

Their Discussion: *"Multi-agent decomposition does not automatically outperform a strong
single-agent combined baseline … These results argue against treating agent count or
decomposition as intrinsically valuable."*

**Collective Capability is 25% of the rubric, and the judges' own published answer is
conditional.** A confident claim from us is refuted by their data before we speak. The honest
move is to present **the condition**, cite them, and say what we think separates the one win from
the three non-wins. Engaging with their negative result is the strongest available signal that we
read their work.

**Required elsewhere:** morphoswarm `docs/prior-art/scienceclaw-infinite.md` §4 item 6 says
*"MorphoBench (SPEC-006) supplies the missing measurement rig."* They closed that gap in May. The
first half ("2603.14312 reports qualitative outcomes only") stays true; the second must go.
Another repo's file — not edited from here.
