# Single-ray actuation and curvature: bounded equation reproduction

**24/24 declared static cases returned; 24/24 meet the frozen numerical checks.** The eight analytic/mutation controls passed: True. This is numerical agreement with a printed model, not measured material calibration or biological validation.

The model is [Alben, Madden and Lauder (2007), DOI10.1098/rsif.2006.0181](https://doi.org/10.1098/rsif.2006.0181), a planar single-ray model with two inextensible hemitrichia, a thin incompressible linear-shear layer and fused tips. The paper tested bluegill sunfish, not flying fish. This calculation uses the uniform-parameter specialization of Eq3.14 with fixed base sliding and uniform load moment, compares with Eq5.2, obtains curvature from Eq3.9 and reconstructs centerline coordinates through Eq3.17–18. It implements no muscle, servo, nervous system or developmental program.

All parameters and outputs are **dimensionless**, as in Section 3.3. B is one hemitrich's bending rigidity divided by unknown B0; G is shear modulus times intraray area, scaled by B0/L². **G=200 is not 200 Pa.** p is force per ray arclength scaled by B0/L³, not pressure in Pa. Ray length L, B0 and cross-sectional area for the flying-fish geometry remain unknown. No SI stiffness is inferred.

## Source discrepancy preserved

The printed Sec5.3/Fig8b values B=1,G=200,d=.01,phi0=.01,p=200 give p*d/G=phi0 exactly. The hyperbolic term in Eq5.2 cancels, so phi=.01(1-s), curvature=1 and the unit-length ray is a circular arc: tip=(sin1,1-cos1). The numerical tip is [0.8414709848079007, 0.4596976941318631]; circle error 4.22e-15. The printed Figure8b/text instead describes an S-shaped reversal for those same parameters (and its caption points to Eq5.1 for uniform load). **That figure reproduction is unresolved.** We did not change a sign, tune parameters or fit a trace to remove the disagreement.

## Numerical scope and derived interface

Maximum phi error against Eq5.2: 3.21e-14; maximum curvature error: 3.44e-11. Two BVP tolerances1e-8/1e-10 are retained per case; these are error comparisons against the analytic solution, not a measured convergence rate. Wrong curvature and load signs fail the frozen reference controls. This reproduces the same mathematical model through a separate numerical boundary-value solve, not an independently measured or independently derived biological model.

For the unloaded case only, differentiating the paper's internal energy (Eq3.12) gives generalized sliding stiffness K=2*B*a*coth(a)/d², a=sqrt(G/(2B)). Its dimensional scale is B0/L³, giving N/m. It measures the cost of relative basal sliding, **not aggregate fin bending EI**. Numerical energy checks at phi0=.01:

| Dimensionless G | Dimensionless sliding K | Relative energy-check error |
| --- | --- | --- |
| 20 | 63472.602 | 7.23e-13 |
| 200 | 200000 | 1.08e-13 |
| 2000 | 632455.53 | 1.05e-14 |

Loads p≠0 have no inferred actuator force or work budget here.

12/24 cases reach the descriptive curvature-gap reference max|kappa*d|≥.1; the maximum is 0.4743. The source assumes a thin layer and curvature of order1/L. Highly localized curvature can violate that ordering. The .1 reference is an engineering caution, not a source-established sharp validity boundary or a physical PASS. All states and cautions remain visible.

The useful coupling port is prescribed per-ray base_slide/L → curvature*L(s), centerline/L(s), with a separate unloaded basal stiffness. Connecting it to a whole fin requires ray identities/spacing/taper, material measurements, interray membrane mechanics, finite torsion and force/energy-limited actuation. Mapping that fin to aerodynamic pressure requires an actual load-transfer model. There is no substitution of these values into the earlier aggregate-EI aeroelastic assay or MuJoCo hingeK.

Run code/protocol/environment/source/output hashes are in run-v2/receipt.json and protocol.json. Actual local wall time 0.885s; one CPU/thread,2GiB/128tasks/300s scope. Dollar cost unknown. The first attempt stopped before parameter cases on a NumPy-bool JSON serialization error; run/failure.json remains unchanged and the corrected serialization was tested before run-v2.

Next questions: which flying-fish rays correspond to the geometry, and what are L,B0,d(s),G(s)? Does the printed uniform-load figure require corrected parameters/signs? What actuator force/work and membrane model connect base sliding to a full fin? Empirical validation remains unknown.
