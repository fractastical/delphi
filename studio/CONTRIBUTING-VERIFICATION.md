# How a result gets into this repo

Written from one day of trying, and failing, to produce a novel claim. Fifteen attempts, fifteen
refutations — see [`ledger/`](ledger/README.md). These rules are what survived.

## 1. Compiling is not evidence

A theorem that compiles with a clean axiom audit can still say nothing.

- Ours shipped `finite_domain_stable`, which assumed `¬(det < 0)` and concluded `0 ≤ det`. That is
  `not_lt`. It compiled. The axiom audit was clean. An independent reviewer caught it.
- Our experiment checker accepted a frozen `False` once helper text added a second `False`
  assumption — elaborated type `False → False`, clean audit again.

**Every target ships a paired mutant that must FAIL to compile.** A result scores only if its
mutant was rejected. Without that you are measuring an agent's ability to weaken the target.

## 2. Hash the file, not the string

We circulated `6d61ae56…` as a freeze hash. It was the sha256 of an in-memory JSON string, not of
the committed bytes. Quote the on-disk sha256 **and** `git hash-object` beside it.

## 3. Read the citation before you cite it

Three errors in one file's lineage: a wrong source, then two replacements relayed from a reviewer
without being read — whose abstracts did not support the claim either. **If you have not read it,
mark it unread or leave it out.**

## 4. Ask the question your ground truth decides

We asked models *"does a pattern form"*, a nonlinear question, and scored it against **linear**
mode admissibility. Subcritical patterns form where linear theory says stable. The question did
not test the proposition. Re-run with the question matched, the result was 24/24 for both models —
a clean null instead of a false finding.

## 5. Prior-art check before the claim, not after

Of fifteen candidate headlines, **four** died to prior art we had not looked for, including one
repository committed to **five hours** before we claimed the gap. Budget the search first; it is
cheaper than the retraction.

## 6. Separate columns, always

**Proved** (what the model entails), **simulated** (what the discretisation produced), **observed**
(what was measured). A Lean theorem certifies the first and says nothing about an organism. We ran
no experiment, and every artifact here says so.

## 7. Report the null

Three measured nulls today. Each is in the ledger with its witness. A null reported is a result;
a null buried is the thing that makes the next person repeat it.
