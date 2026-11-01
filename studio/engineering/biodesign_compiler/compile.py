"""SPEC-014 prototype: pinned assembly manifests -> a report with separate axes (never one success badge).

Reuses engineering/coupling.py (typed ports, validate_coupling, default_registry/default_couplings) for the interface and
coupling axes; it adds only pinning, cross-component hash checks, domain/numerical readings of existing artifacts, a
layer diff and a result cache keyed by input hashes. It runs no biological model and implies no whole genome.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engineering import coupling as cp

ASSEMBLY_SCHEMA = "frontier.biodesign.assembly/1"
REPORT_SCHEMA = "frontier.biodesign.report/1"
AXES = ("structural_refs", "units_context", "model_domain", "numerical", "empirical", "implementation")
LAYERS = ("genetic_blueprint", "cell_program", "tissue_model", "geometry", "aero", "behavior")
# which layers each stage reads; a changed pin invalidates exactly the stages that read it
STAGE_LAYERS = {
    "structural_refs": LAYERS,
    "units_context": ("tissue_model", "geometry", "aero"),
    "model_domain": ("aero",),
    "numerical": ("aero",),
    "empirical": ("genetic_blueprint", "tissue_model", "behavior"),
    "implementation": ("genetic_blueprint", "cell_program"),
}
VARIANTS = {"v3a": "fish3d-v3a-fan", "v3b": "fish3d-v3b-glide-pose", "v3c": "fish3d-v3c-daane-length"}
SHARED = {
    "genetic_blueprint": "artifacts/genetic-blueprints/blueprints.json",
    "cell_program": "artifacts/fish-regulatory-map/map.json",
    "tissue_model": "artifacts/bioelectric-tissue/model_interface.json",
    "behavior": "artifacts/behavior/manifest.json",
}


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pin(root: Path, rel: str) -> dict:
    b = (root / rel).read_bytes()
    return {"path": rel, "sha256": sha(b), "bytes": len(b)}


def build_assembly(root: Path, vid: str, siblings: list[str]) -> dict:
    d = VARIANTS[vid]
    comps = {k: pin(root, v) for k, v in SHARED.items()}
    comps["geometry"] = pin(root, f"artifacts/fish3d/{d}/candidate.json")
    comps["aero"] = pin(root, f"artifacts/cfd3d/vlm/{d}/vlm.json")
    comps["geometry_panels"] = pin(root, f"artifacts/fish3d/{d}/panels.json")
    comps["geometry_components"] = pin(root, f"artifacts/fish3d/{d}/components.json")
    a = {"schema": ASSEMBLY_SCHEMA, "id": f"fish3d-{vid}", "parent": None, "siblings": siblings,
         "components": comps,
         "shared_pins": sorted(SHARED),
         "shared_pins_note": "genetic_blueprint, cell_program, tissue_model and behavior are the same pinned files in every variant: no per-variant version of them exists",
         "unresolved_interfaces": ["expression->growth", "growth->EI (flexural rigidity)", "genetic_blueprint->cell_program binding validation"],
         "scope": "biological design pins only; print derivatives and display poses are not part of the assembly; no whole-genome design is implied"}
    a["assembly_sha256"] = sha(json.dumps({k: v for k, v in a.items() if k != "assembly_sha256"}, sort_keys=True).encode())
    return a


def _load(root, p):
    return json.loads((root / p["path"]).read_text())


def stage_structural(root: Path, a: dict) -> dict:
    bad, ok = [], []
    for k, p in a["components"].items():
        f = root / p["path"]
        if not f.exists():
            bad.append({"layer": k, "reason": f"missing file {p['path']}"})
        elif sha(f.read_bytes()) != p["sha256"]:
            bad.append({"layer": k, "reason": f"sha256 changed: pinned {p['sha256'][:12]}, found {sha(f.read_bytes())[:12]}", "path": p["path"]})
        else:
            ok.append(k)
    if not bad:
        v = _load(root, a["components"]["aero"])
        for fld, layer in (("candidate_sha256", "geometry"), ("panels_sha256", "geometry_panels"), ("components_sha256", "geometry_components")):
            if v[fld] != a["components"][layer]["sha256"]:
                bad.append({"layer": "aero", "reason": f"aero {fld} {v[fld][:12]} does not match the pinned {layer} {a['components'][layer]['sha256'][:12]}"})
    return {"status": "fail" if bad else "pass", "pinned_ok": ok, "failures": bad}


def stage_units_context(root: Path, reg: cp.Registry, couplings: list[cp.Coupling]) -> dict:
    out = []
    for c in couplings:
        v = cp.validate_coupling(reg, c)
        out.append({"coupling": c.id, "label": v.label.split(":")[0], "failed_checks": {k: x for k, x in v.checks.items() if str(x).startswith(("fail", "refused", "missing"))}})
    counts = {}
    for o in out:
        counts[o["label"]] = counts.get(o["label"], 0) + 1
    return {"status": "mixed", "counts": counts, "refused": [o for o in out if o["label"] == "refused"],
            "note": "the registry models are the flying-fish constraint/glide/fin-beam/Notch models, not these fish3d variants; geometry and aero artifacts are not typed ports there, so no variant-specific unit result exists"}


def stage_domain(root: Path, a: dict) -> dict:
    v = _load(root, a["components"]["aero"])
    st = v["status"]
    return {"status": "fail" if st.startswith("NOT CONVERGED") else "unassessed", "reading": st,
            "model": "horseshoe VLM, zero-thickness isolated paired fins, no body; rays/membrane/thickness not resolved"}


def stage_numerical(root: Path, a: dict) -> dict:
    v = _load(root, a["components"]["aero"])
    r = v["refinement"]
    res = {"CL_rel_change_48x16_to_72x24": r["CL_rel_change"], "pectoral_dCp_rms_change": r["pectoral_L"]["quad_dCp_rms_change_over_rms"],
           "frozen_threshold": None}
    if v["status"].startswith("NOT CONVERGED"):
        res["status"] = "fail (retained)"
        res["reason"] = v["status"]
    else:
        res["status"] = "measured, no frozen threshold: not called converged"
    return res


def stage_empirical(root: Path) -> dict:
    m = json.loads((root / "engineering/COUPLING_MANIFEST.json").read_text())
    return {"status": "unresolved", "calibrations_registered": m["calibrations_registered"],
            "reading": "no calibration is registered; behavior manifest: " + _load(root, {"path": SHARED["behavior"]})["biological_accuracy"]}


def stage_implementation(root: Path) -> dict:
    b = json.loads((root / SHARED["genetic_blueprint"]).read_text())
    kin = {d["id"]: d["expression_kinetics"]["status"] for d in b["designs"]}
    bind = {d["id"]: d["cell_program_binding"]["validation_status"] for d in b["designs"]}
    return {"status": "unresolved", "expression_kinetics": kin, "cell_program_binding_validation": bind,
            "reading": "proposals only; LEN coordinates and sequence null; no genome implied"}


def unresolved_bridges(reg, root: Path) -> list[dict]:
    c05 = next(c for c in cp.default_couplings() if c.id == "c05_notch_to_fin_stiffness")
    v = cp.validate_coupling(reg, c05)
    return [
        {"bridge": "expression->growth", "status": "unresolved", "reason": "no expression-to-growth model or mapping is registered; blueprint expression_kinetics are UNKNOWN"},
        {"bridge": "growth->EI", "status": "unresolved", "reason": "no growth-to-flexural-rigidity mapping; the nearest registered coupling is refused", "coupling_id": c05.id, "coupling_label": v.label.split(":")[0]},
        {"bridge": "blueprint->cell_program", "status": "unresolved", "reason": "cell_program_binding validation_status is unknown in every design"},
    ]


def compile_assembly(root: Path, a: dict, reg=None, couplings=None, cache=None) -> dict:
    reg = reg or cp.default_registry()
    couplings = couplings or cp.default_couplings()
    fns = {
        "structural_refs": lambda: stage_structural(root, a),
        "units_context": lambda: stage_units_context(root, reg, couplings),
        "model_domain": lambda: stage_domain(root, a),
        "numerical": lambda: stage_numerical(root, a),
        "empirical": lambda: stage_empirical(root),
        "implementation": lambda: stage_implementation(root),
    }
    axes, reused = {}, []
    for s in AXES:
        key = json.dumps({k: a["components"][k]["sha256"] for k in STAGE_LAYERS[s]}, sort_keys=True)
        if cache is not None and s in cache and cache[s]["key"] == key:
            axes[s] = cache[s]["result"]
            reused.append(s)
            continue
        axes[s] = fns[s]()
        if cache is not None:
            cache[s] = {"key": key, "result": axes[s]}
    return {"assembly": a["id"], "assembly_sha256": a["assembly_sha256"], "axes": axes, "reused_from_cache": reused,
            "unresolved_bridges": unresolved_bridges(reg, root),
            "no_single_badge": "axes are reported separately; an unresolved bridge is not a violated constraint and neither is hidden by a render"}


def impact(old: dict, new: dict) -> dict:
    changed = [k for k in sorted(set(old["components"]) | set(new["components"])) if old["components"].get(k, {}).get("sha256") != new["components"].get(k, {}).get("sha256")]
    inv = [s for s in AXES if set(STAGE_LAYERS[s]) & set(changed)]
    return {"changed_layers": changed, "invalidated_stages": inv, "kept_stages": [s for s in AXES if s not in inv]}


def flat(o, p=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield from flat(v, f"{p}.{k}" if p else k)
    elif isinstance(o, list) and len(o) <= 8:
        for i, v in enumerate(o):
            yield from flat(v, f"{p}[{i}]")
    else:
        yield p, o


def knob_diff(root: Path, a: dict, b: dict, limit=40) -> list[dict]:
    x, y = dict(flat(_load(root, a["components"]["geometry"]))), dict(flat(_load(root, b["components"]["geometry"])))
    d = [{"path": k, a["id"]: x.get(k), b["id"]: y.get(k)} for k in sorted(set(x) | set(y)) if x.get(k) != y.get(k)]
    return d[:limit] + ([{"truncated": len(d) - limit}] if len(d) > limit else [])


def compare(root: Path, asms: list[dict]) -> dict:
    rows = []
    for a in asms:
        v = _load(root, a["components"]["aero"])
        rows.append({"assembly": a["id"], "CL_paired_fins_alpha4_S_lattice": v["cases"]["4"]["CL_paired_fins_on_S_lattice"],
                     "refinement_CL_rel_change": v["refinement"]["CL_rel_change"], "aero_status": v["status"][:60],
                     "usable_for_comparison": not v["status"].startswith("NOT CONVERGED")})
    return {"matched_conditions": "alpha 4 deg, rho=1 |V|=1, horseshoe VLM, 48x16 lattice, isolated paired fins", "rows": rows,
            "note": "no feasibility score is given; an unconverged variant's CL is listed but flagged unusable"}


def layer_diff(root: Path, asms: list[dict]) -> list[dict]:
    out = []
    for i in range(len(asms)):
        for j in range(i + 1, len(asms)):
            d = impact(asms[i], asms[j])
            d.update({"a": asms[i]["id"], "b": asms[j]["id"], "geometry_knob_changes": knob_diff(root, asms[i], asms[j])})
            out.append(d)
    return out


def broken_controls(root: Path, a: dict, reg, couplings) -> dict:
    import copy
    bad = copy.deepcopy(a)
    bad["components"]["geometry"]["sha256"] = "0" * 64
    hash_res = stage_structural(root, bad)
    c13 = next(c for c in cp.default_couplings() if c.id.startswith("c13"))
    wrong = cp.Coupling(c13.id + "_wrong_unit", c13.from_ref, c13.to_ref, mapping_kind="assumed", assumption_ids=c13.assumption_ids,
                        factor=c13.factor, factor_dim=cp.dim(m=2), time_relation=c13.time_relation, uncertainty_kind=c13.uncertainty_kind, note="control: factor dimension m^2 instead of m")
    v = cp.validate_coupling(reg, wrong)
    return {"broken_hash": {"expected": "fail", "got": hash_res["status"], "reason": hash_res["failures"]},
            "broken_unit": {"expected": "refused", "got": v.label.split(":")[0], "reason": v.reasons + [f"{k}: {x}" for k, x in v.checks.items() if str(x).startswith("fail")], "label": v.label}}


def run(root: Path, cache=None) -> dict:
    ids = list(VARIANTS)
    asms = [build_assembly(root, v, [x for x in ids if x != v]) for v in ids]
    reg, cps = cp.default_registry(), cp.default_couplings()
    return {"assemblies": asms, "compiled": [compile_assembly(root, a, reg, cps, None if cache is None else cache.setdefault(a["id"], {})) for a in asms],
            "comparison": compare(root, asms), "layer_revision_diff": layer_diff(root, asms),
            "controls": broken_controls(root, asms[0], reg, cps)}
