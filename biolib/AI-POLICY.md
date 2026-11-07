# AI policy

Most of the Lean in Biolib was written by AI agents working from human-chosen claims, and the project says so.
The policy follows from that, and from the delphi rule that the assessor is never the builder.

1. **AI-written proofs are welcome.** Lean checks the proof; what needs review is the *statement*: does it say
   what the docstring says, and are the hypotheses the source's. Say in the pull request which model wrote
   what, so the reviewer knows what to look hardest at.
2. **Acceptance into `Biolib/` is a human decision**, made by someone who did not generate the module and is
   not using the model that did. AI review is welcome as input and is recorded as such.
3. **No fabricated sources.** Every paper, dataset or measurement named in a docstring must have been fetched
   by whoever cites it. An unverifiable citation is removed, not fixed.
4. **A `sorry`-free build is the floor, not the bar.** A statement can be true, proved, and about nothing; the
   non-vacuity witness and the mutation test exist because generated proofs of vacuous statements are the
   failure mode we have actually seen.
5. **Agents read this file.** `AGENTS.md`-style instructions for agents working in this repository are the
   README's rules and this file; there is nothing an agent may do here that a person may not.
