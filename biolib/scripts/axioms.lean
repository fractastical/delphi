import Biolib
import BiolibAlpha

/-!
Axiom audit for every theorem in Biolib and BiolibAlpha. Run after `lake build`:

    lake env lean scripts/axioms.lean

It fails (exit code 1) if any theorem depends on an axiom other than Lean's three standard ones
(`propext`, `Classical.choice`, `Quot.sound`), which also catches `sorryAx`.
-/

open Lean Elab Command in
run_cmd do
  let env ← getEnv
  let roots : List Name := [`Biolib, `BiolibAlpha, `Delphi, `ThompsonLaws, `DarwinLaws]
  let mut bad : Array (Name × Array Name) := #[]
  let mut n : Nat := 0
  for (c, info) in env.constants.toList do
    unless roots.contains c.getRoot do continue
    unless info.isTheorem do continue
    n := n + 1
    let axs ← Lean.collectAxioms c
    let extra := axs.filter fun a =>
      !(a == ``propext || a == ``Classical.choice || a == ``Quot.sound)
    if extra.size > 0 then bad := bad.push (c, extra)
  if bad.size > 0 then
    throwError "theorems checked: {n}; with non-standard axioms: {bad.size}\n{bad}"
  logInfo m!"theorems checked: {n}; all depend only on propext, Classical.choice, Quot.sound"
