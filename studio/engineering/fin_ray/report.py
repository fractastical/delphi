"""Plot saved static ray states and retain unresolved source/transfer questions."""

import argparse
from pathlib import Path

import numpy as np

from .model import ART, digest, dump


def run(root):
    import json
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    receipt = json.loads((root / "receipt.json").read_text())
    cases = json.loads((root / "results.json").read_text())["cases"]
    for item in receipt["files"]:
        if digest(root / item["path"]) != item["sha256"]:
            raise ValueError("Numerical output digest changed")
    fig, axes = plt.subplots(2, 3, figsize=(12.8, 7.2), layout="constrained")
    source_case = None
    for case in cases:
        p = case["parameters"]
        col = [20., 200., 2000.].index(p["G"])
        color = f"C{[0., .005, .01, .015].index(p['phi0'])}"
        style = "-" if p["p"] == 0 else "--"
        with np.load(root / case["states"]["path"], allow_pickle=False) as data:
            axes[0, col].plot(data["x"], data["y"], style, color=color, label=f"phi0={p['phi0']}, p={p['p']:g}")
            axes[1, col].plot(data["s"], data["kappa"], style, color=color)
        if p == dict(B=1., G=200., d=.01, phi0=.01, p=200.):
            source_case = case
    for col, g in enumerate([20, 200, 2000]):
        axes[0, col].set(title=f"G={g} (dimensionless)", xlabel="x / L", ylabel="y / L")
        axes[0, col].set_aspect("equal", adjustable="datalim")
        axes[0, col].grid(alpha=.2)
        axes[1, col].set(xlabel="Ray arclength s / L", ylabel="Curvature x L")
        axes[1, col].axhline(0, color="gray", linewidth=.7)
    axes[0, 1].legend(fontsize=6, ncols=2, loc="upper left")
    fig.suptitle("Single-ray equation reproduction | solid: unloaded; dashed: prescribed uniform load\nBase sliding changes curvature; not measured flying-fish material or whole-fin EI", fontsize=12)
    path = ART / "ray-response.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    controls = json.loads((root / "controls.json").read_text())
    maximum_phi_error = max(x["phi_max_absolute_error_vs_Eq5_2"] for x in cases)
    maximum_curvature_error = max(x["curvature_max_absolute_error_vs_Eq5_2"] for x in cases)
    cautions = sum(x["curvature_gap_caution_at_engineering_reference_0_1"] for x in cases)
    stiffness = [
        {"G": x["parameters"]["G"], "K_sliding_normalized": x["unloaded_generalized_sliding_stiffness_L3_over_B0"], "relative_energy_check_error": x["stiffness_relative_error"]}
        for x in cases if x["parameters"]["p"] == 0 and x["parameters"]["phi0"] == .01
    ]
    stiffness_table = "\n".join(
        f"| {x['G']:g} | {x['K_sliding_normalized']:.8g} | {x['relative_energy_check_error']:.3g} |"
        for x in stiffness
    )
    dump(ART / "render-provenance.json", {
        "schema": "frontier.fin-ray.render/1", "code_sha256": digest(Path(__file__)),
        "receipt_sha256": digest(root / "receipt.json"),
        "input_states": [x["states"] for x in cases],
        "output": {"path": path.name, "sha256": digest(path), "bytes": path.stat().st_size},
        "scope": "Plot of24actual static BVP solution states, not temporal motion or observed rays. No fitted Fig8 trace.",
    })
    text = f"""# Single-ray actuation and curvature: bounded equation reproduction

**{len(cases)}/24 declared static cases returned; {sum(x['numerical_controls_passed'] for x in cases)}/24 meet the frozen numerical checks.** The eight analytic/mutation controls passed: {controls['passed']}. This is numerical agreement with a printed model, not measured material calibration or biological validation.

The model is [Alben, Madden and Lauder (2007), DOI10.1098/rsif.2006.0181](https://doi.org/10.1098/rsif.2006.0181), a planar single-ray model with two inextensible hemitrichia, a thin incompressible linear-shear layer and fused tips. The paper tested bluegill sunfish, not flying fish. This calculation uses the uniform-parameter specialization of Eq3.14 with fixed base sliding and uniform load moment, compares with Eq5.2, obtains curvature from Eq3.9 and reconstructs centerline coordinates through Eq3.17–18. It implements no muscle, servo, nervous system or developmental program.

All parameters and outputs are **dimensionless**, as in Section 3.3. B is one hemitrich's bending rigidity divided by unknown B0; G is shear modulus times intraray area, scaled by B0/L². **G=200 is not 200 Pa.** p is force per ray arclength scaled by B0/L³, not pressure in Pa. Ray length L, B0 and cross-sectional area for the flying-fish geometry remain unknown. No SI stiffness is inferred.

## Source discrepancy preserved

The printed Sec5.3/Fig8b values B=1,G=200,d=.01,phi0=.01,p=200 give p*d/G=phi0 exactly. The hyperbolic term in Eq5.2 cancels, so phi=.01(1-s), curvature=1 and the unit-length ray is a circular arc: tip=(sin1,1-cos1). The numerical tip is {source_case['tip_xy_over_L']}; circle error {controls['circle_tip_error']:.3g}. The printed Figure8b/text instead describes an S-shaped reversal for those same parameters (and its caption points to Eq5.1 for uniform load). **That figure reproduction is unresolved.** We did not change a sign, tune parameters or fit a trace to remove the disagreement.

## Numerical scope and derived interface

Maximum phi error against Eq5.2: {maximum_phi_error:.3g}; maximum curvature error: {maximum_curvature_error:.3g}. Two BVP tolerances1e-8/1e-10 are retained per case; these are error comparisons against the analytic solution, not a measured convergence rate. Wrong curvature and load signs fail the frozen reference controls. This reproduces the same mathematical model through a separate numerical boundary-value solve, not an independently measured or independently derived biological model.

For the unloaded case only, differentiating the paper's internal energy (Eq3.12) gives generalized sliding stiffness K=2*B*a*coth(a)/d², a=sqrt(G/(2B)). Its dimensional scale is B0/L³, giving N/m. It measures the cost of relative basal sliding, **not aggregate fin bending EI**. Numerical energy checks at phi0=.01:

| Dimensionless G | Dimensionless sliding K | Relative energy-check error |
| --- | --- | --- |
{stiffness_table}

Loads p≠0 have no inferred actuator force or work budget here.

{cautions}/24 cases reach the descriptive curvature-gap reference max|kappa*d|≥.1; the maximum is {max(x['max_abs_curvature_times_gap'] for x in cases):.4g}. The source assumes a thin layer and curvature of order1/L. Highly localized curvature can violate that ordering. The .1 reference is an engineering caution, not a source-established sharp validity boundary or a physical PASS. All states and cautions remain visible.

The useful coupling port is prescribed per-ray base_slide/L → curvature*L(s), centerline/L(s), with a separate unloaded basal stiffness. Connecting it to a whole fin requires ray identities/spacing/taper, material measurements, interray membrane mechanics, finite torsion and force/energy-limited actuation. Mapping that fin to aerodynamic pressure requires an actual load-transfer model. There is no substitution of these values into the earlier aggregate-EI aeroelastic assay or MuJoCo hingeK.

Run code/protocol/environment/source/output hashes are in {root.name}/receipt.json and protocol.json. Actual local wall time {receipt['wall_seconds']:.3f}s; one CPU/thread,2GiB/128tasks/300s scope. Dollar cost unknown. The first attempt stopped before parameter cases on a NumPy-bool JSON serialization error; run/failure.json remains unchanged and the corrected serialization was tested before run-v2.

Next questions: which flying-fish rays correspond to the geometry, and what are L,B0,d(s),G(s)? Does the printed uniform-load figure require corrected parameters/signs? What actuator force/work and membrane model connect base sliding to a full fin? Empirical validation remains unknown.
"""
    (ART / "RESULTS.md").write_text(text)
    dump(ART / "index.json", {
        "schema": "frontier.fin-ray.index/1", "status": "computed equation reproduction; source figure disagreement unresolved",
        "scale": "single-ray material/organ interface", "species_source": "Lepomis macrochirus",
        "transfer_species": "flying fish: unknown", "biological_success_probability": None,
        "report": "artifacts/fin-ray/RESULTS.md", "poster": "artifacts/fin-ray/ray-response.png",
        "protocol": "artifacts/fin-ray/protocol.json", "receipt": f"artifacts/fin-ray/{root.name}/receipt.json",
        "source": receipt["source_model"], "declared_cases": 24, "computed_cases": len(cases),
        "source_figure_reproduction": "unresolved", "empirical_validation": "unknown",
    })
    files = [p for p in ART.rglob("*") if p.is_file() and p.name != "artifact-manifest.json"]
    dump(ART / "artifact-manifest.json", {"files": [
        {"path": str(p.relative_to(ART)), "sha256": digest(p), "bytes": p.stat().st_size}
        for p in sorted(files)
    ]})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ART / "run-v2")
    args = parser.parse_args()
    run(args.root)
