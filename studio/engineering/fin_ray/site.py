"""Read-only gallery adapter; site owner supplies tracked reads and media copying.

Usage in build_site.engineering_cards:
    build_card(ins.read, lambda name, sha: _vid(
        ins, out, "fin-ray-bilaminar", "artifacts/fin-ray", name, sha))

No simulator import, filesystem scan, model run or network access occurs here.
"""

from hashlib import sha256
import itertools
import json

DIRECTORY = "artifacts/fin-ray"


def build_card(read, publish_media):
    """Return one native gallery card from digest-checked committed artifacts."""
    manifest = json.loads(read(f"{DIRECTORY}/artifact-manifest.json"))
    pins = {x["path"]: x for x in manifest["files"]}
    if len(pins) != len(manifest["files"]):
        raise ValueError("Duplicate fin-ray artifact pin")

    def pinned(name):
        # Only fixed paths below are read; manifest entries never initiate reads.
        item = pins[name]
        raw = read(f"{DIRECTORY}/{name}")
        if sha256(raw).hexdigest() != item["sha256"] or len(raw) != item["bytes"]:
            raise ValueError(f"Fin-ray digest/size mismatch: {name}")
        return raw

    protocol = json.loads(pinned("protocol.json"))
    receipt = json.loads(pinned("run-v2/receipt.json"))
    results = json.loads(pinned("run-v2/results.json"))
    controls = json.loads(pinned("run-v2/controls.json"))
    pinned("RESULTS.md")
    pinned("ray-response.png")
    if receipt["protocol_sha256"] != pins["protocol.json"]["sha256"]:
        raise ValueError("Run protocol differs from displayed protocol")
    native = {x["path"]: x for x in receipt["files"]}
    for name in ["results.json", "controls.json"]:
        if native[name]["sha256"] != pins[f"run-v2/{name}"]["sha256"]:
            raise ValueError("Run receipt differs from displayed result")
    expected = set(itertools.product(*(
        protocol["cases"][key] for key in ["B", "G", "d", "phi0", "p"]
    )))
    cases = results["cases"]
    identities = [tuple(x["parameters"][key] for key in ["B", "G", "d", "phi0", "p"]) for x in cases]
    if len(identities) != len(set(identities)) or set(identities) != expected:
        raise ValueError("Displayed case identities differ from declared experiment")
    if protocol["cases"]["count"] != len(expected) or receipt["cases_returned"] != len(cases):
        raise ValueError("Fin-ray count/identity mismatch")
    numerical = sum(x["numerical_controls_passed"] for x in cases)
    if receipt["numerical_controls_passed"] != numerical:
        raise ValueError("Fin-ray numerical count mismatch")
    source = protocol["source"]
    state, poster = publish_media("ray-response.png", pins["ray-response.png"]["sha256"])
    return {
        "id": "fin-ray-bilaminar",
        "title": "Single-ray basal sliding and curvature: published-equation reproduction",
        "scales": ["organ", "tissue"],
        "evidence_kind": "SimulationResult; computed static same-equation comparison",
        "model": {
            "name": "Two-hemitrich planar ray, Alben et al. (2007), Eq3.14 / Eq5.2",
            "context": f"{numerical}/{len(expected)} same-equation numerical comparisons passed. Prescribed base sliding changes single-ray curvature under a fixed load moment. Source species is bluegill sunfish; no measured flying-fish material or whole-fin validation.",
        },
        "time": {"units": "Static normalized ray arclength, not physical time", "note": "Figure shows actual BVP solution states; no temporal motion inferred."},
        "video": {"file": None, "sha256": None, "note": "Static response plot, not a video."},
        "video_state": "none", "video_href": None,
        "poster_href": poster if state == "present_verified" else None,
        "poster_is_figure": True, "poster_state": state,
        "poster": {"file": "ray-response.png", "sha256": pins["ray-response.png"]["sha256"]},
        "numerical_checks": [
            {"name": "Same-equation BVP versus Eq5.2", "result": f"{numerical}/{len(expected)} declared comparisons; maximum normalized curvature error {max(x['curvature_max_absolute_error_vs_Eq5_2'] for x in cases):.3g}"},
            {"name": "Analytic and sign-comparison controls", "result": f"{sum(controls['checks'].values())}/{len(controls['checks'])} recorded comparisons passed; not independent biological evidence"},
            {"name": "Printed Figure8 source discrepancy", "result": "UNRESOLVED: listed parameters and Eq5.2 give constant curvature; the figure/text describes an S-shaped reversal. No sign or parameter fit was made."},
        ],
        "equations": [
            {"label": "Uniform single-ray equilibrium (dimensionless)", "tex": r"-2B\phi''+G\phi-pd(1-s)=0,\quad\phi(0)=\phi_0,\ \phi(1)=0", "source": "Alben et al. Eq3.14 and Eq5.2; fixed base sliding, fused tip"},
            {"label": "Basal sliding to curvature", "tex": r"\kappa=-\phi'/d,\quad\theta=(\phi_0-\phi)/d", "source": "Eq3.9 and Eq3.18, constant gap"},
            {"label": "Derived unloaded sliding stiffness (not fin EI)", "tex": r"K_{\phi}=2Ba\coth(a)/d^2,\quad a=\sqrt{G/(2B)}", "source": "Our energy differentiation of Eq3.12 for p=0; dimensional scale B0/L^3, N/m"},
        ],
        "sources": [
            {"label": "Primary source: bluegill ray model", "locator": source["doi"] + "; Eq3.9–3.18, Sec3.3, Eq5.2/Fig8; PDF SHA256 " + source["sha256"]},
            {"label": "Frozen protocol and actual numerical output", "locator": f"{DIRECTORY}/protocol.json SHA256 {pins['protocol.json']['sha256']}; run-v2/receipt.json"},
        ],
        "parameter_unknowns": [
            "All numerical inputs are nondimensional. G=200 is not 200 Pa; dimensional G is shear modulus times intraray area.",
            "Flying-fish ray length L, bending-rigidity scale B0, area and taper remain unknown; SI outputs are null.",
            "Basal sliding stiffness is not aggregate whole-fin EI or an ecology hinge spring.",
        ],
        "open_questions": protocol["coupling_ports"]["unknown"],
        "limitations": [
            "Same-equation numerical fidelity is not biological validation or a reproduction of the inconsistent printed Figure8 curve.",
            "Single static planar segmented ray with fused tip and prescribed base sliding; no muscle force/work, neural control, membrane, torsion or fluid feedback model.",
            f"{sum(x['curvature_gap_caution_at_engineering_reference_0_1'] for x in cases)}/{len(cases)} cases reach a descriptive curvature-gap caution; no source-established sharp physical-validity PASS.",
            "Empirical validation unknown; biological_success_probability null.",
        ],
        "couplings": [], "coupling_ports": protocol["coupling_ports"],
        "manifest": f"{DIRECTORY}/index.json", "report": f"{DIRECTORY}/RESULTS.md", "native": True,
        "artifacts": [{"path": f"{DIRECTORY}/{name}", "sha256": pins[name]["sha256"], "bytes": pins[name]["bytes"]} for name in ["protocol.json", "run-v2/receipt.json", "RESULTS.md", "ray-response.png"]],
    }
