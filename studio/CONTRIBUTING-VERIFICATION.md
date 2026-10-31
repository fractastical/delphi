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

## 8. A green status is not a measurement. Ship the control whose answer you already know.

Four times in one day a check reported success while measuring nothing, and **in every case what
caught it was a control whose expected value was known in advance** — never a re-reading of the
code, and never a status code.

- **`grep -o` here is ugrep, and it reports only NON-OVERLAPPING matches.** A genome-wide k-mer
  scan returned "5 matched k-mers" for every label. 5 is exactly the maximum number of
  non-overlapping 24-mers in a 60 bp and a 94 bp exon. The **positive control** is what said this
  was wrong: exons 20 and 22 are *known present* at 37/37 and 71/71, so a method returning 5 was
  not measuring what it claimed. Without it, "5 k-mers found" ships as a number.
- **`exited with code 0` was `tail`'s status, not the scan's.** The scan had been killed at its
  900 s cap having covered 93.6% of the genome, printing no tallies. A pipeline's exit status is
  its last command's.
- **Every Addgene search page returns HTTP 200, including for gibberish.** Reading the status code
  would have "confirmed" strains that do not exist. Only a query that *had* to come back empty
  told the difference, and that single check demoted a problem.
- **A must-fail control that names a real thing is not a control.** `9ZZZ.cif` was chosen as a
  bogus PDB accession and returned HTTP 200 — because 9ZZZ is a real entry. Impossible accessions
  (`0000`, `ZZZZ`) do return 404. The endpoint was fine; the control was badly chosen, and it
  briefly "proved" the opposite of the truth.

Status-code-as-success and last-command-in-a-pipeline are the same failure wearing two hats.

**So: beside every search, scan or query, run one case whose answer you already know, in both
directions.** A positive control that must come back found, and a must-fail control that must
come back empty — and check that the must-fail case is genuinely impossible rather than merely
unfamiliar. A search that cannot come back empty has not been tested. A number with no control
beside it is not a measurement, however green the run looked.

## 9. Say whether you retrieved it or remembered it

A claim that makes the result *better* is the one to distrust most, and the one most likely to
have come from memory.

In the oca2 work, "Tinaja is not albino" was written into a preregistration as background
knowledge. What had actually been retrieved was a BioSample `ecotype` field reading
`"Tinaja cave"` — which establishes *cave* and says nothing about *pigment*. The claim went
unsourced for the whole run and would have upgraded a technical reproduction into a biological
specificity result on the strength of recall.

Challenged, it was sourced properly (Jeffery 2020, PMC7353729, full text) **and** one competing
explanation (another oca2 lesion in the Tinaja fish) was checked in our own three single-fish assemblies,
which does not rule it out at population level; the specificity reading was then withdrawn on independent
review (RESULT section 14.4). The fix was not
to delete the claim but to **mark the provenance failure in its own subsection** and ship the
observation at the confidence the evidence supports — post-hoc, n=1 per population, phenotypes
from a review about populations rather than from the individuals sequenced.

**Label every claim `retrieved` or `remembered` as you write it**, not when someone asks.

**And the asymmetry, which is the sharper form of this rule.** The author's own account, after the
fact: *"the Tinaja claim was load-bearing precisely because it improved the result, and I didn't
notice that while writing it."* That is the tell. A detail which **upgrades** a finding is the one
whose provenance needs checking before it goes in — not because such details are usually wrong,
but because nothing downstream will question them. A claim that weakens your result gets
scrutinised by you, immediately, for free. A claim that strengthens it does not, and the direction
of the effect is the trigger for the check.

So the operational rule is narrower than "source everything", which nobody does: **when you notice
that a detail makes the result better, stop and ask where you got it.**
