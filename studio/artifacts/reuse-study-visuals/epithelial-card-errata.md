# Reading notes for docs/epithelial-repair-card.md (09, 66f2b95), from independent review

The card shipped here is owner 09's `66f2b95`, byte-for-byte. 09 has already corrected, in the card itself, every point the independent review raised on `edc1e10`: the gate tally, the 625-filled versus 1875-residual label, the 1.414 bracket wording, the observed 65 initial cells against the nominal 625-node target, the passive floor as a context-specific observation, and G1b. They are listed so a reader of an older copy can see what changed:

1. **Gate tally.** Strictly 7 pass (G1, G2, G3, G5, G7, G9, G11), 3 fail (G4, G10, G12), G6 descriptive, G1b incomplete, G8 unevaluable. "Nine of thirteen" counted G6 as a pass and is wrong.
2. **G1b.** The frozen rule is every written frame. Only 756 of 1476 frames (51.2%) can be compared, with 0 disagreements on those; the other 720 are not evidence of agreement. It is INCOMPLETE. The earlier reported pass (at `9429a21` and `edc1e10`) is kept as history, not as a verdict, and the rule was not narrowed to shared times to call a pass.
3. **Floor arithmetic.** 625 nodes are filled and 1875 remain as the residual gap of the 2500-node hole (25.0% ideal). The measured passive closure, 22.04% (arm F1-no-drive-NEGATIVE), is an observation in that one context, not a universal amount to subtract.
4. **1.414.** The geometric mean of the observed bracket (1, 2) at k=4: one conditional out-of-sample bracket check, not an observed point threshold and not a verified scaling law.
5. **Cell counts.** The unwounded arm starts with 65 cells, a mean of 40000/65 = 615.4 nodes; 625 is the nominal target and scale anchor.

Points for how the site shows it:

6. **Horizon.** CLOSED and ARRESTED are operational labels at a finite 1000 model-unit horizon; permanence of arrest is not shown. Time is model units and Monte-Carlo sweeps, never minutes.
7. **Gap size.** The k=4 and k=7 bracket intervals overlap, so their differing midpoints alone do not refute a constant Phi. k=1 never arrests, G8 is unevaluable and G12 failed: counter-evidence, with no criterion rescued.
8. **No validation.** No output was compared with data from any cell line or species; where the model agrees with a paper, two models agree.
