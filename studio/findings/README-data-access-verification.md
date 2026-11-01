# Verifying data access demoted 2 of 15 actionable problems

`c4e0960` recorded **15 of 17** sourced problems as actionable. **That number is superseded: it
is 13.** The 17 are unchanged; what changed is that somebody checked whether the data each
problem needs actually exists.

| | before | after |
|---|---|---|
| actionable | 15 | **13** |
| recorded | 2 | **4** |

Data-access verdicts across the 17: **8 confirmed, 5 referenced-only, 2 not-found, 2 n/a** (the
two already `recorded` for other reasons). Proposal file sha256
`23d0160512ccb86b1aebf5b1cb70e80105e9157399f09f69f17981da84dc7e18`.

An "actionable" problem whose data does not exist is not actionable. It is well written.

## The two demotions, and why they are the interesting records

**SB-02** (promoter leakiness) — `not-found`. GEO's five MPRA hits are yeast TSS selection, mouse
chromatin accessibility and three human enhancer studies. *E. coli* appears in two taxon fields as
the **cloning host**, not the measurement organism. No bacterial promoter-RBS library with
uninduced expression, which is the measurement the question turns on.

**SB-03** (kill-switch escape) — `not-found`. Addgene returns zero result markers for the named
strains. The check also sharpened the problem: the field's published "escape rate" is *"the ratio
of the number of viable microbes when the kill switch is triggered relative to the number when it
is not triggered"* — a survival ratio, **not** the per-generation mutation rate the problem asked
about. Same name, different quantity. SB-03 is now better posed than when it was written, and is
`recorded` on data access rather than on novelty.

## Both demotions came from must-fail controls, not from reading

This is the part worth keeping. **Every Addgene search page returns HTTP 200, including for
gibberish.** Reading the status code would have "confirmed" SB-03's strains. Only a control query
that had to come back empty separated a real hit list from an empty one, and that single check
produced the demotion.

The same reviewer caught an error of its own with the same instrument. Its first Europe PMC pass
put `\"` inside single quotes, the shell passed literal backslash-quotes, Europe PMC dropped the
quoting, and every phrase search silently degraded to a loose term search. Counts inflated 10-50x
(17→103, 3→222, 41→2008) — and **the inflated counts looked better**. What caught it was reading
titles: a chemical-kinetics query returning zirconia dental restorations is not a query that ran.

Four earlier zero-result searches were re-run correctly and **none of the zeros survived**
(434 / 442 / 214 / 311 on Europe PMC). So those zeros described the query strings, not the
literature — which is this repository's recurring lesson arriving through a third instrument.

## What is still NOT verified, so the 8 confirmed are not over-read

Confirmation means the named resource resolves and serves data of the right kind. It does **not**
mean the resource contains the specific fields each acceptance criterion needs. CH-01's replicate
count and ED-02's pair count are exactly that gap, and both remain those problems' own next
actions. CH-02's novelty status was deliberately **not** upgraded: Europe PMC covers *Combustion
and Flame* about as poorly as PubMed does, so that negative is still scoped to indexes which do
not cover the field.

Two problems dropped in the first pass for want of a source (cell-free to in vivo transfer,
consortium stability) do have literature that was simply not reached. They stay out, but the
first report must not be read as evidence those questions are unstudied.
