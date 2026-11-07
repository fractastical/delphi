# Biolib

**An open-source Lean 4 library of results from biology, organized by biology.** What
[Physlib](https://github.com/leanprover-community/physlib) is for physics: one package, one toolchain,
reviewed content in `Biolib/`, a lighter-review `BiolibAlpha/`, informal results waiting to be formalized,
and a biology docstring on every module. Built on [Mathlib](https://github.com/leanprover-community/mathlib4).

Current contents, counts and the module table are in [`STATUS.md`](STATUS.md), which is generated; nothing
in this README is a number.

```
lake build                          # Biolib and BiolibAlpha
lake env lean scripts/axioms.lean   # fails if any theorem uses more than propext, Classical.choice, Quot.sound
```

## What is in it

```
Biolib/
  Allometry/            size, shape and the scaling of parts with body size
  Biomechanics/         structures, materials and locomotion under physical law
  Morphogenesis/        how cells, tissues and shells take their form
  PopulationGenetics/   allele frequencies, fixation, selection and inheritance
  Physiology/           metabolism, transport and the perturbations an organism survives
  Ecology/              populations, competition, succession and biogeography
  Meta/                 anatomy graphs, constraint forms, and Informal.lean
BiolibAlpha/            same subjects; candidate, proposed and contested material, certificates, audits
```

Every theorem is a theorem about a **model**: a structure of named hypotheses, each carrying the observation
or assumption it stands for, and a conclusion that follows from them. There is no `axiom` anywhere, so
`#print axioms` on any theorem names only Lean's three standard ones; an empirical ingredient enters as a
hypothesis the caller must supply, never as a fact about the world. A proof here shows the conclusion follows
from the hypotheses. Whether organisms satisfy the hypotheses is settled by data, not by Lean, and that is why
a result can be proved and still be *contested* (see `BiolibAlpha/Physiology/DepthCapContested.lean`, where a
measured fish at 8,336 m refutes a law's hypothesis and the module proves `False` from the observation).

### Biolib vs BiolibAlpha

The split follows the law registry in the delphi working tree, the way Physlib's follows review standard:

- **`Biolib/`**: modules whose registry laws are `accepted`, or whose theorems are Lean-checked claims in the
  delphi claim graph (a claim report records the module, the declaration and the reading proved).
- **`BiolibAlpha/`**: `candidate`, `proposed` and `contested` laws; pipeline certificates (kernel-checked
  eliminations of specific designs); audits and witnesses. We do not promise to keep Alpha compiling when its
  dependencies move; we record when it breaks.

A `retired` law is kept, compiled, and marked retired in its module docstring. Laws are retired, never
deleted.

### Informal results

`Biolib/Meta/Informal.lean` lists results that belong here and are not formalized: registry laws with no Lean
module, and claims the delphi graph records as proved in the literature without a Lean proof. Each entry has an
English statement, its source, and the formalization tags from the claim graph (`one`, `several`, `identity`,
`contingent`), so someone who knows Lean can formalize it without first knowing the biology. Formalize one,
then replace the entry with an import of your module.

## Where the modules come from, and where to edit them

Biolib is currently a **mirror**. The modules are developed in the
[delphi working tree](https://github.com/fractastical/delphi_private), beside the claim sources, data tests
and law registry that produce them, and copied here by `scripts/sync-from-delphi.py`, which rewrites the
imports, prepends a provenance docstring, and writes [`PROVENANCE.json`](PROVENANCE.json) (origin path, origin
commit, content hash, registry laws and Lean-checked claims per module) and [`STATUS.md`](STATUS.md). Namespaces
inside the modules (`Delphi.*`, `ThompsonLaws.*`, `DarwinLaws.*`) are the origin's and will be renamed to
`Biolib.*` once the modules move here for good.

Until then: to change a module, change it at its origin and re-run the sync. To **add** a result, open a pull
request here with a new module under the right subject; it is reviewed against the rules below and, if
accepted, registered as a law in the delphi registry so the two stay in step.

Modules at the origin that do not compile on the pinned toolchain are listed under *Not carried* in
`STATUS.md` with the reason, and are not here.

## Rules for a contribution

These are the delphi registry's acceptance criteria (`lean/registry/propose.mjs`), which Biolib adopts whole:

1. The result is **sourced**: a module docstring names the claim or paper it formalizes and the reading it
   proves (a historical sentence usually admits several).
2. Every empirical ingredient is a **named hypothesis** on a structure, not an `axiom`.
3. `#print axioms` shows only `propext`, `Classical.choice`, `Quot.sound`. No `sorry`.
4. **Non-vacuity**: a witness shows the hypotheses can be satisfied together.
5. A **mutation test**: a deliberately broken variant that fails to compile or changes the conclusion. A proof
   nobody tried to break is not evidence.
6. **Scope** is stated: taxa, life stages and ranges the hypotheses are meant for.
7. Biology docstring on the module and on each definition, with units for every quantity.
8. Acceptance into `Biolib/` is a **human** decision recorded in the review; AI-written proofs are welcome in
   `BiolibAlpha/` and are promoted the same way as any other.

See [`CONTRIBUTING.md`](CONTRIBUTING.md) and [`AI-POLICY.md`](AI-POLICY.md).

## Related

- [Physlib](https://github.com/leanprover-community/physlib) and the
  [perspective paper](https://doi.org/10.1002/advs.202517294) behind it, whose model this follows.
- [LeanGenetics](https://github.com/ATOMSLab/LeanGenetics) (Jones & Josephson, UMBC): the central dogma in
  Lean 4, with proofs that transcription is injective and the genetic code is not. It overlaps
  `Biolib/PopulationGenetics/Genotype.lean`; we would like it in `Biolib/MolecularBiology/`.
- The delphi project: [delphibio.org](https://delphibio.org), the claim graph and law registry these modules
  are proved against.

## License

Not yet chosen; the decision, with Apache-2.0 proposed, is
[fractastical/delphi#15](https://github.com/fractastical/delphi/issues/15). Until a license file is added these files are
all-rights-reserved by default and contributions cannot be accepted.
