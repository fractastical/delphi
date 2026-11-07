# Contributing to Biolib

Small pull requests, one result or one module at a time, so review is fast. Open an issue first if you are
unsure where a result belongs.

## Where a result goes

Pick the subject folder by the biology, not by the source: a scaling law from *On Growth and Form* goes in
`Allometry/`, not `Thompson/`. Name the source in the module docstring. If no folder fits, propose one in the
pull request; `MolecularBiology/`, `Development/` and `Neuroscience/` are expected and empty.

New work starts in `BiolibAlpha/<Subject>/` unless it already meets every rule in the README. Promotion to
`Biolib/` is a separate pull request that moves the file and records who accepted it and why.

## Before you open the pull request

```
lake build
lake env lean scripts/axioms.lean
```

Both must pass. Then check, in your module:

- a module docstring (`/-! ... -/`) naming the claim or paper, the reading proved, and what is **not** proved;
- every definition has a docstring with units;
- every empirical input is a field of a hypothesis structure, with its source in the field's docstring;
- a `Nonempty` witness for each hypothesis structure;
- a mutation: a commented-out or `example`-guarded variant showing what fails when a hypothesis is dropped
  or a relation flipped.

## What reviewers check

1. Is it biology, and is it stated as biologists state it, with the conventions and units they use?
2. Does the Lean statement say what the docstring says it says? A proof of a weaker reading with a stronger
   docstring is the most common defect and is rejected.
3. Are the hypotheses the minimal ones, and are they the ones the source actually assumes?
4. Would a reader know what observation would make this law's hypotheses false?

## Formalizing an informal result

Pick an entry in `Biolib/Meta/Informal.lean`. Write the module, then remove the entry from the list (the
`all_length` theorem will tell you to) and add the import. The sync script regenerates `Informal.lean` from
the delphi registry, so also tell us the id so the registry is updated; otherwise your entry reappears.

## Mirror status

Until Biolib is the source of truth, modules copied by `scripts/sync-from-delphi.py` carry a provenance
block and are overwritten on each sync. Changes to those files go to their origin (the path in the block).
New modules written directly here are not touched by the sync.
