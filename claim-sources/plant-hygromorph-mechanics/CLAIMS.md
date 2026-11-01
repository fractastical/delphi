# Claims: plant hygromorph mechanics

Human-readable version of [`claims/key-claims.json`](claims/key-claims.json), with proof and test
status, followed by the candidates for the next batch. Status fields follow the repo rule
([AGENTS.md](../../../AGENTS.md), "Theorem is a proof status"): a claim is a theorem only when it is a
mathematical statement and its proof is established (Lean 4 or recorded in the literature); a data
test is a separate axis and never promotes a claim.

Lean module: [`../thompson-growth-form/lean/ThompsonLaws/Hygromorphs.lean`](../thompson-growth-form/lean/ThompsonLaws/Hygromorphs.lean),
report [`../thompson-growth-form/lean/reports/Hygromorphs.json`](../thompson-growth-form/lean/reports/Hygromorphs.json).
Tests: [`../../test-data/claim-tests/plant-hygromorph-mechanics/`](../../test-data/claim-tests/plant-hygromorph-mechanics/).

## Summary

| id | Law | Formal status | Lean | Data test |
|---|---|---|---|---|
| `hygromorph-bilayer-curvature` | \(\kappa = C(h,m,n)\,\Delta\varepsilon\) | proved (Timoshenko 1925) | 6 theorems, incl. derivation from equilibrium | `supports` (biological, confidence 0.4): prediction within 15% of measured bending for *P. torreyana* (Quan et al. 2021), ~2× under for *P. coulteri* (Reyssat & Mahadevan 2009); n = 2 scales, inputs combined across papers |
| `hygromorph-response-time` | \(\tau \sim h^2/D\) | proved (diffusion time scale) | 8 theorems, incl. heat-equation mode | none yet |
| `hygromorph-antisymmetric-twist` | \(\Delta\varepsilon_{12} = (\varepsilon_L-\varepsilon_T)\sin 2\phi,\ \Delta\varepsilon_{11}=0\) | proved (tensor algebra) | 5 theorems, incl. Mohr's circle | none yet |
| `flytrap-snap-geometry` | bistable iff \(\alpha = L^4\kappa^2/h^2 \gtrsim 0.8\) | partial (threshold numerical) | dimensional part only; not counted | none yet |
| `stimulus-response-systems-category` | simulation-preserving maps compose | proved (Marom et al. 2026, App. A.2) | 9 theorems, `CategoryTheory.Category` instance | not applicable (no organism content) |

## 1. `hygromorph-bilayer-curvature`: bilayer curvature from differential swelling

**Statement.** A thin two-layer strip whose layers swell by different amounts bends with a uniform
curvature proportional to the swelling-strain mismatch, with a geometric coefficient fixed by the
thickness ratio and modulus ratio of the layers. The pine cone scale is such a bilayer: its outer
sclerenchyma layer swells along the scale, its inner sclereid layer does not.

**Math.**
\[
\kappa = \frac{6(1+m)^2}{h\,[\,3(1+m)^2 + (1+mn)(m^2 + 1/(mn))\,]}\;\Delta\varepsilon,
\qquad m = \tfrac{h_1}{h_2},\; n = \tfrac{E_1}{E_2},\; h = h_1 + h_2 ;
\]
for \(m = n = 1\), \(\kappa = \tfrac{3}{2}\,\Delta\varepsilon / h\).

**Assumptions.** Linear elasticity; Euler–Bernoulli kinematics (slender strip, plane sections);
perfect bonding at the interface; uniform eigenstrain in each layer; small strains.

**Formal status.** Proved. Timoshenko (1925) for bimetal thermostats, thermal strain replaced by
hygroscopic strain; Reyssat & Mahadevan (2009) apply it to pine cone scales and paper–polymer
bilayers. Lean: `bilayerCurvature_ofEquilibrium` derives the formula from force balance
\(P_1 + P_2 = 0\), moment balance against \(\sum E_i h_i^3 \kappa / 12\) and strain compatibility at
the interface; `bilayerCurvature_linear`, `_zero`, `_symmetric`, `_sign`, `timoshenkoCoefficient_pos`.

**What is left to data.** Whether a real scale's layers are uniform, well bonded, linearly elastic
and slender enough, and whether the measured curvature change matches the prediction from measured
\(h_1, h_2, E_1, E_2, \Delta\varepsilon\). Pre-registered test (commit `310ca761`) against Reyssat &
Mahadevan (2009) and Quan et al. (2021, *Acta Biomater.* 128:370, CC BY): verdict `supports` by the
pre-registered rule (median \(|\log_{10}(\text{pred}/\text{meas})| = 0.165 \le 0.18\)), but on its
edge and at confidence 0.4: predicted 68° vs measured 79° for *P. torreyana*, predicted 72° vs
measured 132° for *P. coulteri*; the model underpredicts in both, sign correct in both; only two
scales, and no paper gives all five inputs for the same specimen. See the test's `result.json`.

**Sources.** [10.1098/rsif.2009.0184](https://doi.org/10.1098/rsif.2009.0184);
[10.1364/JOSA.11.000233](https://doi.org/10.1364/JOSA.11.000233);
[10.1038/37745](https://doi.org/10.1038/37745); [10.1016/j.actbio.2021.04.049](https://doi.org/10.1016/j.actbio.2021.04.049).

## 2. `hygromorph-response-time`: response time scales as thickness squared

**Statement.** The time a hygromorphic bilayer takes to respond to a humidity change is set by
diffusion of water through its thickness, so it grows as the square of the thickness divided by the
diffusion coefficient.

**Math.** \(\tau \sim h^2 / D\); the slowest mode of the 1-D diffusion equation on \(0 \le x \le h\)
with fixed boundary concentration is \(u = e^{-\pi^2 D t / h^2} \sin(\pi x / h)\).

**Assumptions.** Fickian diffusion with constant \(D\); quasi-static mechanics; one dominant
thickness.

**Formal status.** Proved as the diffusive time scale. Lean: `diffusiveTime_scale`
(\(\tau(kh) = k^2 \tau(h)\)), `diffusionMode_heat` (the mode satisfies \(u_t = D u_{xx}\)),
`diffusionMode_boundary`, `diffusionMode_decay`. Not proved in Lean: that this mode is the slowest.

**What is left to data.** Reyssat & Mahadevan (2009) measured \(\tau\) against \(h\) for bilayers and
scales and found the quadratic scaling. Non-Fickian sorption or swelling-dependent \(D\) would
change the exponent. No repo test yet.

## 3. `hygromorph-antisymmetric-twist`: antisymmetric fibre angles turn swelling into twist

**Statement.** When the two layers of a swelling bilayer have their stiff fibres at equal and
opposite angles to the strip axis, the layers' in-plane shear strains are equal and opposite, so the
through-thickness mismatch is a pure shear mismatch that drives helical twisting rather than
bending. This is how chiral seed pods and wheat awns open.

**Math.** \(\varepsilon_{12}^{(j)} = \tfrac12(\varepsilon_L - \varepsilon_T)\sin 2\phi_j\); with
\(\phi_{1,2} = \pm\phi\): \(\Delta\varepsilon_{12} = (\varepsilon_L - \varepsilon_T)\sin 2\phi\),
\(\Delta\varepsilon_{11} = 0\).

**Assumptions.** Each layer swells transversely isotropically about its fibre direction; the strain
transforms as a rank-2 tensor under rotation by the fibre angle; same material and \(|\phi|\) in
both layers.

**Formal status.** Proved (Armon et al. 2011; Marom et al. 2026 eq. 28). Lean:
`shearStrain_mismatch`, `axialStrain_mismatch`, and `strainInStripAxes_entries` showing the two
strains are the (1,1) and (1,2) entries of \(R\,\mathrm{diag}(\varepsilon_L,\varepsilon_T)\,R^\top\).
The finite-width shape (helicoid vs cylindrical helix) is nonlinear plate theory and not formalized.

**What is left to data.** Fibre angles and swelling strains in *Bauhinia* pods or wheat awns against
the measured pitch of the opened structure. No repo test yet.

**Sources.** [10.1126/science.1203874](https://doi.org/10.1126/science.1203874);
[10.1126/science.1140097](https://doi.org/10.1126/science.1140097).

## 4. `flytrap-snap-geometry`: the Venus flytrap snaps above a geometric threshold

**Statement.** A doubly curved leaf whose natural curvature changes slowly snaps between two stable
shapes only if a dimensionless combination of its size, thickness and curvature is large enough;
below the threshold it deforms smoothly. The snap time is set by elastic and poroelastic time scales,
not by cellular motor speed.

**Math.** \(\alpha = L^4 \kappa^2 / h^2 \gtrsim \alpha_c \approx 0.8\) for bistability;
\(\tau_{snap} \sim \mu L^2 / (kE)\) when \(\alpha \gg \alpha_c\).

**Formal status.** Partial. The threshold exists by shallow-shell analysis and numerics (Forterre et
al. 2005 measured \(\alpha\) from 0.3 to 1.9 across leaves) but has no closed form. Lean proves only
that \(\alpha\) is dimensionless and monotone (`snapParameter_dimensionless`, `_mono_size`,
`_anti_thickness`, `_threshold_mono`, `poroelasticTime_scale`); the report marks the claim
`not-formalized` because that is not the law, so it is **not** counted as a theorem.

**What is left to data.** Classify leaves by measured \(\alpha\) and by high-speed video (smooth vs
snap), and check closure time against \(L^2\). No repo test yet.

**Source.** [10.1038/nature03185](https://doi.org/10.1038/nature03185).

## 5. `stimulus-response-systems-category`: simulation-preserving maps form a category

**Statement.** Stimulus–response dynamical systems \((X, E, f)\), \(\dot x = f(x, e)\), with
morphisms \((\alpha, \alpha_E)\) satisfying \(d\alpha_x(f(x,e)) = g(\alpha(x), \alpha_E(e))\), form a
category: identities satisfy the condition and it is closed under composition. So a chain of locally
valid scale transitions in a material hierarchy (fibre → lamina → tissue → element → organ) is
globally valid.

**Formal status.** Proved (Marom, Tibbits, Zardini & Buehler 2026, Appendix A.2; closure is the
chain rule). Lean: `StimulusResponseHom.comp_simulation` (via `fderiv_comp`), `id_comp`, `comp_id`,
`comp_assoc`, a `CategoryTheory.Category` instance, and `mapsSolutions` (a morphism carries
solutions of \(\dot x = f(x, e(t))\) to solutions).

**What is left to data.** Nothing about organisms; this is a statement about the modelling language.
The paper's own validation (four printed actuators, predicted vs measured within one s.d.) is
`physical`, not `biological`, data. Its empirical content is carried by claims 1 and 3, which are
its element-scale laws.

**Source.** [10.1016/j.jmps.2026.106780](https://doi.org/10.1016/j.jmps.2026.106780),
[arXiv:2604.26367](https://arxiv.org/abs/2604.26367).

## Candidates for the next batch

From Marom & Buehler, *Frontiers of biological material intelligence* (MRS Bulletin 2025,
[10.1557/s43577-025-00987-8](https://doi.org/10.1557/s43577-025-00987-8), CC BY), which groups
biological material behaviour under three design principles, and from the hygromorph literature.
Each needs a quantitative statement, a formal status and a dataset before it becomes a claim.

| Candidate | Principle (Marom & Buehler) | Quantitative core | Overlap in the graph | Data |
|---|---|---|---|---|
| Wolff's law: trabecular orientation follows principal stress; remodelling tracks strain | II self-optimisation | strain-energy-density remodelling rule \(\dot\rho \propto (U/\rho - k)\) (Huiskes 1987; Weinkamer & Fratzl 2011) | `thompson1917-ch16-05`–`ch16-08`; `wolff-trabeculae` dataset queue | micro-CT fabric tensors vs FE stress |
| Pine cone bending coefficient | I sensing/response | Dawson, Vincent & Rocca 1997: bending coefficient from sclerenchyma/sclereid expansion ratio | claim 1 above | their Table 1 |
| Wheat awn humidity-cycle stroke | I | Elbaum et al. 2007: awn bending per RH cycle from cellulose fibril angle | claim 3 | Elbaum Fig. 3 |
| Stomatal aperture vs guard-cell turgor | I | aperture a linear function of turgor difference guard–epidermis (Franks & Farquhar) | none | gas-exchange datasets |
| Sea cucumber dermis stiffness switching | I | tensilin/softenin modulus ratio (Takehana 2014) | none | stress–strain tables |
| Growth increments as environmental records | III memory | ring width / isotope vs temperature regression (tree rings, *Arctica islandica*, coral) | shell chapter of Thompson; `organisms/` has bivalve taxa | ITRDB; sclerochronology archives |
| Nacre layer spacing vs growth conditions | III | aragonite platelet thickness ~ 0.5 µm, spacing vs temperature | Thompson shell claims | Meyers 2008 review |
| Scallop eye guanine mirror tuned to blue–green | II | reflectance peak vs layer thickness (quarter-wave stack) | none | Palmer 2017 |
| Sunflower heliotropism and phyllotaxis | temporal scales | circadian growth-rate asymmetry; Fibonacci divergence 137.5° | `phyllotaxis` queue; Thompson spiral claims | Vandenbrink 2014 |
| Material intelligence ≈ basal cognition | framing | none; a thesis, not a law | `claim-sources/levin-papers/` (310 claims on non-neural competency) | the Levin tests |

The last row is not a claim to extract but the reason to talk to the authors: their "intelligence is
the material" is Levin's basal-cognition thesis stated for materials, and neither cites the other.
