# Preregistrations

A preregistration committed **after** the result is not a preregistration. It is a description
of what happened, written in the future tense.

So each file here is committed to git **before its analysis returns**, and the commit timestamp
is the evidence. If you want to know whether a criterion was set in advance, read
`git log --follow` on the file and compare the commit time to the result's.

Nothing in this directory may be edited once its result is known. A criterion that turns out to
have been badly chosen is corrected by a **new** file that cites the old one and says what was
wrong with it, in the same way the refutation ledger keeps its retracted rows rather than
deleting them.

## A design flaw found by executing one of these, 2026-10-31

`2026-10-31-kcne1-binding-ddg.md` **pinned a structure** and **derived its acceptance threshold
from the full assay**. Those two commitments are **jointly unsatisfiable for any deposited
structure**, not merely for the one it named: every PDB entry resolves a subset of the protein, so
the variants actually scoreable are always a subset of the assay the threshold came from — and
that subset is not a random sample of it.

The run proved the point with numbers. Restricted to the 25 residues 9VEC models, the best
published model rises from **+0.288 to +0.434** and the median from **+0.110 to +0.214**, so
**22 of 95 models already clear the preregistered bar on the subset while none clears it on the
full assay** (Mann-Whitney p = 4.95e-12, 3.1x the variance). A ΔΔG scoring +0.35 would have
"passed" while losing to ProSST on the identical variants.

The coverage floor caught it, which is what a floor is for. But a floor is a backstop, and the
flaw was in the pairing.

**So: derive the threshold from the population you will actually score.** If a protocol restricts
the evaluable set — by structure coverage, by assay overlap, by any filter — recompute the
baseline on that restricted set *before* fixing the bar, and preregister the restricted number.
Writing down a threshold from a population you cannot reach is not a stricter test. It is a
different test, and usually an easier one.

*Found by the agent that executed the protocol rather than by its author.*
