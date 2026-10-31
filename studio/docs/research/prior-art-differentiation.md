# Prior-art differentiation — feature-level

**Scope.** A narrow, feature-level comparison of what is *implemented* in each system. It is not
a novelty argument. Raw research (ASK 466 lines, Buehler 1,097 lines) is in
`/data/artifacts/delphi-evolve-rethink/messages/`; machine-readable form in
`data/research/prior-art.json`.

**Evidence basis.** Commit SHA per claim, the command behind every count, a control wherever a
zero is reported, and a read-level per paper. Paper passages are **paraphrased**; quotation is
held under 25 words per source.

**Two standing rules.** An absent keyword is **not** evidence a system lacks a capability —
where a check was keyword-based, the row says so and claims nothing further. And a count of test
functions is **not** a count of passing tests; only a recorded run counts.

---

## 0. Our own release, and a correction

**HISTORICAL SNAPSHOT.** The comparison in this document was made against `12eb390` on
`codex/frontier-demo-20261031` as it stood when this was written. **That is not the current
release and this document makes no claim about what is deployed now** — the SHA is kept so the
comparison can be re-read against the tree it was actually made on. For the current release, see
`docs/research/rubric-evidence-matrix.md`; as of 2026-10-31 it is `c1ad527`, public, with 13 web
and 35 MCP checks passing.

**Correction: git commit order is not an independent witness.** Earlier notes of mine treated a
preregistration timestamp preceding a result as proof the criterion was not fitted afterwards.
Timestamps are author-supplied and we control the history, so that is self-attestation. What
holds is the content check — the committed file carries no result section and its criterion is
byte-identical to the one reported against. Internal consistency, not priority. Say
**"self-attested preregistration"**.

## 1. Entities, from primary sources

| | identity | read-level |
|---|---|---|
| **ASK** | *Active Scientific Knowledge*, Mehmet Fırat, sole author, Anadolu University. `10.2139/ssrn.7416579`, 2026-09-14, unreviewed preprint | full text |
| **ScienceClaw** | `lamm-mit/scienceclaw`, Buehler's LAMM group, MIT | main `894598cd3a`; categorical code on branch `38b2f681e8` |
| **Infinite** | `lamm-mit/infinite` | `699b90a422`, unchanged since 2026-04-16 |

**Citation hazards.** Crossref and OpenAlex both render ASK's author as "Mehmet anon". The arXiv
API returns *Wong* where the paper's title block reads **Wang** — Fiona Y. Wang is first author on
the categorical framework, ScienceClaw and the MRS perspective. Use the byline.

**Inherited vs current.** Our prior-art file recorded scienceclaw as unchanged since 2026-08-21;
it moved on 2026-10-30 (2 commits, 9 files — LLM-client, JWT and dry-run fixes plus 4 test files),
touching nothing under `artifacts/`, the pressure formula, the mutator, the needs layer or the
type vocabulary. Infinite's record is still accurate. `categoryscienceclaw/` is not on main; it is
a branch diverged since 2026-05-21, and is the URL the paper itself cites.

## 2. Feature matrix — implemented, at the SHAs named

`✔` implemented · `◐` implemented in a bounded form · `✘` not found by the stated check · `—` out of scope

| feature | ASK (paper) | ScienceClaw / Infinite | **Ours, `12eb390`** |
|---|---|---|---|
| typed record store | — conceptual | ✔ artifact DAG, typed vocabulary | ✔ 9 record types, PostgreSQL, live |
| question routing | — | ◐ `/api/discovery` orders by recency | ◐ attention profiles + typed links (`attention/`) |
| model coupling, typed contexts | — | ✔ substantial: copresheaves, Kan extension, proved propositions | ◐ bounded: typed scope on records; no categorical layer |
| evidence contests | ◐ proposed | ✔ `cite/contradict/extend/replicate`, multi-validator consensus | ◐ dispute and fork implemented; bounded use |
| artifact lineage | ✔ central | ✔ rejected nodes parent accepted ones | ✔ append-only versioned store |
| active learning | ✘ | ✘ | ✘ |
| multi-operator federation | ✔ one of its dimensions | ◐ Infinite threads | ◐ export/import bundles; two stores in one process, not two hosts |
| machine-checked verification | — | ✘ no proof-assistant files at these SHAs | ✔ Lean + mutation-killed checks |
| engineering → physical | — | ✔ fabricated specimens, measured against prediction | ◐ 12 STL mesh files, **not printed** |
| decision rule attached to the question | ✘ | ◐ gates exist, recorded in the accepted artifact | ✔ Action carries acceptance criteria, falsifier, stop rule |
| collective-RL governance | ✘ | ✘ excluded by design | ✘ |

**What the ✘ rows do and do not mean.** ScienceClaw's verification row is a file-extension census
— zero `.lean/.v/.thy/.agda/.smt2/.mlw` across 2,177 blobs on main and again on the branch, with
544 `.py` / 999 `.md` / 91 `.json` as controls. It means **no proof-assistant artifact is present
at those SHAs**. It does **not** mean they do not verify; their certificates are structural
obligations in code. ASK's zeros are keyword counts over 11 pages and mean only that the paper
does not use those terms.

## 3. The feature-level difference worth stating

**We attach the decision rule to the question before the result exists.** A Problem carries what
would settle it, what would refute it and a stop rule; an Action cannot be leased against one that
does not. In ScienceClaw the equivalent gate is recorded inside the accepted artifact, so the
criterion travels with the winner.

That is one feature. It is not a claim that typed objects, independent review, dead-ends-as-
artifacts or a formal novelty definition are ours — **all four are theirs, implemented and
published, and must be cited.** Their published outlook also already frames verifying that
provenance composes and that claims have admissible artifact paths; we may say we implemented
something on their list, not that we conceived it.

## 4. Coordination: their result, in context

Wang & Buehler's cross-domain benchmark (arXiv:2605.22300) is a careful rig — 19 comparator and
ablation arms, 11 controls, 28 metrics, frozen matched panels of 24–32 — and it reports a **regime
map** rather than a verdict. Paraphrasing: coordination improves discrimination where evidence is
genuinely distributed; where one channel dominates it improves interpretation, provenance and
auditability instead; and in representational settings it changes what is being inferred rather
than improving prediction.

Across four tasks it wins once (Climate-Vector, AUROC 0.944, +0.208), ties once (Cosmic Filter,
0.955 vs 0.951 on 12 pairs), is matched by a single channel once, and on a chemistry retrieval
task scores below a scripted baseline while improving nearest-neighbour coherence.

**This is a mature, self-critical result, not a failure.** Publishing a regime map that limits
your own thesis is the behaviour we should imitate and cite. The consequence for us is specific:
our closed loop was one agent running one exact scan — a dominant-channel setting by their
taxonomy — so what coordination buys us is the audit trail, not the answer. We assert no
discrimination gain.

**Correction owed elsewhere:** morphoswarm's `docs/prior-art/scienceclaw-infinite.md` §4 item 6
claims MorphoBench supplies a missing measurement rig. That rig exists as of May. Another repo's
file; not edited from here.
