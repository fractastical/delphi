"""Project integrated receipts into scoped regional/scalar assurance annotations.

Checklist: pin every source; check recorded code identity; preserve failed controls;
separate numerical/formal from empirical; refuse dimensional shortcuts; do not
multiply shared evidence; leave unmeasured interfaces and probabilities unknown.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIMENSIONS = ["formal_properties", "numerical_fidelity", "empirical_validation", "parameter_coverage", "cross_scale_transfer", "ensemble_robustness"]
REGIONS = {"body": "Body and whole-fish balance", "pectoral-left": "Left pectoral fin", "pectoral-right": "Right pectoral fin",
           "pelvic-left": "Left pelvic fin", "pelvic-right": "Right pelvic fin", "caudal": "Caudal fin"}
SCALES = ["molecular", "macromolecular", "subcellular", "cellular", "tissue", "organ", "neural", "organism", "developmental", "collective", "ecological", "evolutionary"]
MODEL_SCALES = {"flying_fish_constraints": "organism", "glide_pointmass": "organism", "finbeam_euler_bernoulli": "organ", "fin_load_bridge": "organ",
                "hh1952_gap_chain": "cellular", "motor_clutch_ecm": "cellular", "rdfield_nonlinear_sweep": "tissue", "collier1996_two_cell": "cellular"}


def digest_bytes(data):
    return sha256(data).hexdigest()


class Sources:
    def __init__(self, root):
        self.root, self.index = Path(root).resolve(), {}

    def read(self, path):
        data = self.file(path)
        return json.loads(data)

    def file(self, path):
        target = (self.root / path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("source outside project")
        data = target.read_bytes()
        self.index[path] = {"path": path, "sha256": digest_bytes(data), "byte_size": len(data)}
        return data

    def pin(self, path, selector=""):
        if path not in self.index:
            self.file(path)
        return {**self.index[path], "selector": selector}

    def identities(self, base, expected):
        checked, mismatches = [], []
        for name, wanted in expected.items():
            path = (self.root / base / name).resolve()
            if not path.is_relative_to(self.root):
                raise ValueError("code path outside project")
            relative = str(path.relative_to(self.root))
            actual = digest_bytes(path.read_bytes()) if path.is_file() else None
            checked.append({"path": relative, "recorded_sha256": wanted, "actual_sha256": actual, "matches": actual == wanted})
            if actual != wanted:
                mismatches.append(relative)
        return {"status": "matches" if not mismatches else "mismatch", "checked": checked, "mismatches": mismatches,
                "scope": "source byte identity only; recorded runs were read, not rerun by this projection"}


def dimension_check(source, target):
    """Direct assignment only: unit conversion/geometry factors require an explicit map."""
    if source is None or target is None:
        return {"status": "unknown", "reason": "physical dimensions not declared"}
    units = set(source) | set(target)
    if any(source.get(unit, 0) != target.get(unit, 0) for unit in units):
        return {"status": "refused", "reason": "dimension mismatch; an unprovided calibrated mapping cannot be replaced with direct assignment"}
    return {"status": "consistent_dimensions_only", "reason": "matching dimensions alone establish no biological transfer"}


def conclusion(status, summary, evidence, *, scope="Declared model/receipt scope only", **extra):
    if not evidence:
        raise ValueError("every conclusion needs a source or bounded-search scope pin")
    return {"status": status, "summary": summary, "scope": scope, "evidence": evidence, **extra}


def unknown_vector(evidence, reason):
    return {axis: conclusion("unknown", reason, evidence) for axis in DIMENSIONS}


def _models(s):
    project = "projects/flying-fish.draft.json"
    models = {}
    for model, scale in MODEL_SCALES.items():
        vector = unknown_vector([s.pin(project, "/draft/payload/limitations")], "No scoped result for this assurance dimension in the indexed inputs")
        vector["empirical_validation"] = conclusion("unknown", "Held-out accuracy and calibration for target fish are unknown", [s.pin(project, "/draft/payload/limitations")], target="Exocoetidae", calibration="unknown", error_distribution=None)
        vector["cross_scale_transfer"] = conclusion("unsupported", "No calibrated biological cross-scale transfer established", [s.pin("engineering/COUPLING_MANIFEST.json", "/calibrations_registered")])
        models[model] = {"id": model, "kind": "model", "label": model.replace("_", " "), "scale": scale,
                         "studio_anchor": "flying-fish:" + scale, "model_ids": [model], "region_ids": [], "vector": vector}
    formal = "engineering/formal/RECEIPT.json"
    receipt = s.read(formal)
    lean = receipt["lean_checks"]
    identity = s.identities("engineering/formal", lean["provenance"]["files"])
    status = "checked_scoped" if lean["all_ok"] and identity["status"] == "matches" else "stale_or_failed_receipt"
    models["flying_fish_constraints"]["vector"]["formal_properties"] = conclusion(status,
        "Recorded Lean run checks parameterized similarity laws and a conflict certificate; altered laws/certificate were rejected",
        [s.pin(formal, "/lean_checks"), s.pin(formal, "/solver_result/provenance")],
        assumptions=["positive area/density/lift coefficient", "geometric mass~length^3 and area~length^2", "unchanged gravity/rho/CL", "level-flight lift proxy"],
        anti_triviality={"status": "recorded_mutants_rejected", "parameters_in_theorem": ["m", "g", "rho", "S", "C", "k"],
                        "each_block_rejected": lean["negative"]["each_block_rejected"], "axioms": lean["positive"]["axioms_used"],
                        "scope": "Source theorem and recorded mutation/axiom receipts inspected; no independent anti-triviality certification or fresh Lean run"}, source_identity=identity)
    models["flying_fish_constraints"]["vector"]["parameter_coverage"] = conclusion("source_envelope", "Mass/wing-loading envelope is sourced; air density and lift coefficients are declared assumptions", [s.pin(formal, "/solver_result/provenance")])
    bio = "artifacts/bioelectric/controls_baseline.json"
    bm = "artifacts/bioelectric/manifest.json"
    controls, manifest = s.read(bio), s.read(bm)
    identity = s.identities("engineering/bioelectric", manifest["code_sha256"])
    models["hh1952_gap_chain"]["vector"]["numerical_fidelity"] = conclusion("checked_scoped" if controls["passed"] and identity["status"] == "matches" else "stale_or_failed_receipt",
        "Analytic membrane/gate, conservation, HH time-step and passive-cable grid controls recorded", [s.pin(bio, "/checks"), s.pin("artifacts/bioelectric/mutation_receipt.json")],
        checks=controls["checks"], source_identity=identity, scope="Default HH scenario; smooth passive cable is a separate operator control, not all atlas settings")
    atlas = s.read("artifacts/bioelectric/atlas.json")
    models["hh1952_gap_chain"]["vector"]["parameter_coverage"] = conclusion("sampled_assumption_envelope", "49 explicit gap-by-sodium scenarios, not biological parameter uncertainty", [s.pin("artifacts/bioelectric/atlas.json")],
        sampled_points=len(atlas["rows"]), axes=[atlas["x"], atlas["y"]], uniform_convergence_checked=False,
        robustness_fraction=None, reason="No preregistered biological-success predicate for this exploratory atlas")
    mech = "artifacts/mechanobio/controls.json"
    mm = "artifacts/mechanobio/simulation-manifest.json"
    controls, manifest = s.read(mech), s.read(mm)
    identity = s.identities(".", manifest["code_files"])
    core_mismatches = [p for p in identity["mismatches"] if p.endswith(("model.py", "controls.py"))]
    models["motor_clutch_ecm"]["vector"]["numerical_fidelity"] = conclusion("checked_scoped" if controls["passed"] and not core_mismatches else "stale_or_failed_receipt",
        "Analytic/independent mechanics, force balance and ensemble-mean timestep screen recorded; auxiliary source mismatches are retained", [s.pin(mech), s.pin(mm, "/code_files")],
        checks=controls, source_identity=identity, scope="Default parameter ensemble; no uniform all-settings stochastic convergence or held-out biological accuracy")
    protocol = s.read("artifacts/mechanobio/protocol.json")
    sweep = s.read("artifacts/mechanobio/sweep.json")
    models["motor_clutch_ecm"]["vector"]["parameter_coverage"] = conclusion("sampled_assumption_envelope", "Stiffness×viscosity grid with paired baseline/constant-rupture seeds; repeated runs are dependent", [s.pin("artifacts/mechanobio/protocol.json"), s.pin("artifacts/mechanobio/sweep.json")],
        parameter_cells=len(sweep["rows"]), seeds=protocol["seed_list"], simulation_runs=sweep["n_simulations"], robustness_fraction=None)
    fin = "engineering/fin_mechanics/artifacts/result.json"
    result = s.read(fin)
    identity = s.identities("engineering/fin_mechanics", result["code_files_sha256"])
    models["finbeam_euler_bernoulli"]["vector"]["numerical_fidelity"] = conclusion("checked_scoped" if identity["status"] == "matches" else "stale_or_failed_receipt",
        "Analytic/FEM comparison and uniform/tapered grid convergence recorded; invalid small-deflection settings remain visible", [s.pin(fin, "/controls"), s.pin(fin, "/convergence"), s.pin(fin, "/validity")],
        controls=result["controls"], convergence=result["convergence"], source_identity=identity)
    models["finbeam_euler_bernoulli"]["vector"]["parameter_coverage"] = conclusion("sampled_assumption_envelope", "61 assumed EI values with declared validity limits; no measured target-ray stiffness", [s.pin(fin, "/EI_assumed_range"), s.pin(fin, "/sweep")],
        sampled_points=len(result["sweep"]["rows"]), declared_valid_count=sum(r["uniform"]["valid"] for r in result["sweep"]["rows"]),
        robustness_fraction=None, reason="Descriptive model-validity count, not a prospectively declared robustness estimate")
    gc = "engineering/simulation/results/controls.json"
    gs = "engineering/simulation/results_controlled/summary.json"
    controls, summary = s.read(gc), s.read(gs)
    models["glide_pointmass"]["vector"]["numerical_fidelity"] = conclusion("scoped_with_failures" if summary["n_unconverged"] else "recorded_scoped_controls",
        "Recorded ballistic/energy/equilibrium controls pass; corrected common-launch batch retains unconverged rows", [s.pin(gc), s.pin(gs)],
        controls=controls, unconverged_rows=summary["n_unconverged"], total_rows=summary["n_rows"],
        source_identity={"status": "not_established_for_full_batch", "scope": "No complete run/source hash manifest linked to this summary was asserted by this projector"})
    models["glide_pointmass"]["vector"]["parameter_coverage"] = conclusion("sampled_assumption_envelope", "Common-launch candidate/polar scenarios use assumed aerodynamic coefficients", [s.pin(gs)],
        candidate_count=len(summary["designs"]), rows=summary["n_rows"], reported_robust_wins=summary["n_robust_wins"],
        reported_scenario_flips=summary["n_flip"], robustness_fraction=None,
        reason="Original win rule is preserved descriptively; prospective ordering was not independently established here")
    rd = "engineering/simulation/rd/receipt.json"
    result = s.read(rd)
    models["rdfield_nonlinear_sweep"]["vector"]["numerical_fidelity"] = conclusion("replay_only", "Two saved nonlinear-field reruns reproduce selected frozen rows; not a uniform convergence or fish calibration check", [s.pin(rd)], cells=result["cells"])
    models["collier1996_two_cell"]["vector"]["numerical_fidelity"] = conclusion("source_report_only", "Coupling manifest reports a two-cell SBML replay; no additional numerical controls were rerun here", [s.pin("engineering/model_interfaces/collier1996_two_cell.json")])
    return models


def _matrix(s, model_ids):
    manifest_path = "engineering/COUPLING_MANIFEST.json"
    manifest = s.read(manifest_path)
    cells = {(a, b): {"from": a, "to": b, "status": "same_model" if a == b else "unknown",
                           "unit_check": "not_a_transfer" if a == b else "unknown", "quantitative_error": None,
                           "assumptions": [], "missing_calibrations": [], "relations": [],
                           "evidence": [s.pin(manifest_path, "/couplings")]} for a in model_ids for b in model_ids}
    for index, row in enumerate(manifest["couplings"]):
        edge, verdict = row["coupling"], row["verdict"]
        a, b = edge["from"].split(".")[0], edge["to"].split(".")[0]
        if (a, b) not in cells:
            continue
        cell = cells[a, b]
        cell["relations"].append({"id": edge["id"], "from_port": edge["from"], "to_port": edge["to"],
                                  "status": verdict["status"], "dimension_check": verdict["checks"].get("dimension"),
                                  "mapping_kind": edge["mapping_kind"], "reasons": verdict.get("reasons", [])})
        statuses = {relation["status"] for relation in cell["relations"]}
        cell["status"] = "refused" if "refused" in statuses else "assumption_scenario" if "scenario" in statuses else "typed_interface_only"
        cell["unit_check"] = "see_port_relations"
        cell["assumptions"] = sorted(set(cell["assumptions"] + verdict.get("assumption_ids", [])))
        cell["missing_calibrations"] += verdict.get("missing_calibrations", [])
        cell["evidence"].append(s.pin(manifest_path, f"/couplings/{index}"))
    electrical = s.read("engineering/bioelectric/model_interface.json")
    fin = s.read("engineering/model_interfaces/finbeam_euler_bernoulli.json")
    voltage = next(port for port in electrical["ports"] if port["name"] == "voltage")
    stiffness = next(port for port in fin["ports"] if port["name"] == "flexural_rigidity")
    cell = cells["hh1952_gap_chain", "finbeam_euler_bernoulli"]
    cell.update(status="refused", unit_check=dimension_check(voltage["dim"], stiffness["dim"]),
                missing_calibrations=["Voltage-to-development-to-geometry-to-material transfer is absent; voltage is not EI"],
                evidence=[s.pin("engineering/bioelectric/model_interface.json", "/ports"), s.pin("engineering/model_interfaces/finbeam_euler_bernoulli.json", "/ports")])
    return {"axes": model_ids, "entries": list(cells.values()), "interpretation": "PAE-inspired interface view; no spatial-error numbers, no zero diagonal error, no calibrated joint uncertainty",
            "dimension_rule": "Direct mismatched-dimensional assignment refused; a sourced factor/map must be explicit; matching units do not establish biology"}


def _group_vector(models, selected, evidence):
    vector = unknown_vector(evidence, "No applicable checked target-fish model is indexed for this region/scale")
    for axis in DIMENSIONS:
        entries = [{"model": key, "status": models[key]["vector"][axis]["status"]} for key in selected]
        if axis == "empirical_validation":
            vector[axis] = conclusion("unknown", "Regional held-out biological error and calibration are unknown", evidence, error_distribution=None)
        elif selected:
            pins = [pin for key in selected for pin in models[key]["vector"][axis]["evidence"]]
            unique = { (p["sha256"], p["selector"]): p for p in pins }
            vector[axis] = conclusion("partial_scoped" if any(x["status"] not in {"unknown", "unsupported"} for x in entries) else "unknown",
                "Inspect individual model scopes; this projection does not average assurance dimensions or treat membership as validation",
                list(unique.values()), model_statuses=entries)
    return vector


def build(root=ROOT, *, include_ensembles=True):
    sources = Sources(root)
    project_path = "projects/flying-fish.draft.json"
    project = sources.read(project_path)["draft"]["payload"]
    models = _models(sources)
    nodes = list(models.values())
    for scale in SCALES:
        selected = [key for key, value in MODEL_SCALES.items() if value == scale]
        nodes.append({"id": "flying-fish:" + scale, "kind": "scale", "label": scale, "studio_anchor": "flying-fish:" + scale,
                      "model_ids": selected, "region_ids": [], "vector": _group_vector(models, selected, [sources.pin(project_path, "/draft/payload/scale_coverage")])})
    for region, label in REGIONS.items():
        selected = ["flying_fish_constraints", "glide_pointmass"] if region == "body" else ["fin_load_bridge", "finbeam_euler_bernoulli"] if region.startswith("pectoral") else []
        nodes.append({"id": region, "kind": "region", "label": label, "region_ids": [region], "studio_anchor": "flying-fish:organism" if region == "body" else "flying-fish:organ",
                      "model_ids": selected, "spatial_status": "named_UI_annotation_not_measured_segmentation", "default_display_state": "unknown",
                      "vector": _group_vector(models, selected, [sources.pin(project_path, "/draft/payload/limitations")])})
    matrix = _matrix(sources, list(models))
    from .equations import registry
    equations, equation_gaps = registry(sources)
    for node in nodes:
        node["equation_ids"] = [eq["id"] for eq in equations if eq["model_id"] in node["model_ids"]]
        node["dependency_chain"] = {"models": node["model_ids"],
                                    "transfers": [{"from": e["from"], "to": e["to"], "status": e["status"]}
                                                  for e in matrix["entries"] if e["from"] != e["to"] and e["to"] in node["model_ids"]],
                                    "gaps": [gap["id"] for gap in equation_gaps],
                                    "interpretation": "Source/model equation stack plus explicit missing bridges, not a connected biological mechanism"}
    core = sources.read("engineering/formal/RECEIPT.json")["solver_result"]
    controlled = sources.read("engineering/simulation/results_controlled/summary.json")
    groups = [
        {"id": "source-fish1990", "members": ["flying_fish_constraints", "glide_pointmass", "finbeam_euler_bernoulli"], "evidence": [sources.pin(project_path, "/draft/payload/members/1")]},
        {"id": "assumed-aerodynamic-coefficients", "members": ["flying_fish_constraints", "glide_pointmass", "finbeam_euler_bernoulli"], "evidence": [sources.pin("engineering/formal/RECEIPT.json", "/solver_result/provenance/level_lift_proxy/parameters")]},
        {"id": "shared-HH-model-and-reservoirs", "members": ["hh1952_gap_chain"], "evidence": [sources.pin("artifacts/bioelectric/sources.json")]},
        {"id": "shared-motor-clutch-model-and-paired-seeds", "members": ["motor_clutch_ecm"], "evidence": [sources.pin("artifacts/mechanobio/protocol.json")]},
    ]
    essential = [
        {"id": "cell-tissue-fin", "status": "unsupported", "blocks": ["developmental biological design"], "need": "Target-species cell/tissue measurements and a causal developmental-to-fin map", "evidence": [sources.pin(project_path, "/draft/payload/open_questions")]},
        {"id": "fin-deformation-aerodynamic-polar", "status": "unsupported", "blocks": ["loaded-fin flight prediction"], "need": "Calibrated geometry/deformation-to-lift/drag and held-out trajectories", "evidence": [sources.pin("engineering/COUPLING_MANIFEST.json", "/couplings/7")]},
        {"id": "fin-stiffness-calibration", "status": "unknown", "blocks": ["material-validity decision"], "need": "Target-fin effective stiffness and boundary-condition data", "evidence": [sources.pin("engineering/fin_mechanics/artifacts/result.json", "/not_established")]},
    ]
    next_actions = [{"id": "resolve-" + gap["id"], "priority_class": "unsupported_essential_bridge", "targets": [gap["id"]],
                     "action": gap["need"], "expected_information_gain": None, "expected_utility": None,
                     "reason": "Can remove an explicit essential blocker; ranking among these needs measured cost/outcome models", "evidence": gap["evidence"]} for gap in essential]
    next_actions.append({"id": "refine-unconverged-glide", "priority_class": "known_numerical_failure", "action": "Inspect and refine the recorded unconverged common-launch scenario before comparing it", "expected_information_gain": None, "expected_utility": None,
                         "evidence": [sources.pin("engineering/simulation/results_controlled/summary.json", "/n_unconverged")]})
    ensembles = []
    for candidate in ("baseline", "shorter-ray", "stiffer-ray"):
        path = "artifacts/assurance-experiments/ensemble-" + candidate + ".json"
        if include_ensembles and (sources.root / path).is_file():
            from .ensembles import verify
            ensembles.append(verify(sources, path))
    if ensembles:
        pins = [pin for ensemble in ensembles for pin in ensemble["evidence"]]
        for item in nodes:
            if item["id"] in {"pectoral-left", "pectoral-right", "flying-fish:organ", "finbeam_euler_bernoulli"}:
                item["vector"]["ensemble_robustness"] = conclusion("declared_simulation_fraction", "Prospective candidate predicates recomputed from pinned paired load-shape trials; not biology", pins,
                    candidates=ensembles, scope="Declared assumed input distribution and static linear-ray envelope only")
        groups.append({"id": "paired-fin-assurance-trials", "members": [e["candidate"]["id"] for e in ensembles], "evidence": pins,
                       "note": "Candidates share latent draws; both load cases and meshes within each draw are dependent, one denominator trial"})
    return {"schema": "frontier.design-assurance/1", "project_id": "flying-fish", "status": "unsupported_essential_bridges",
            "biological_success_probability": None, "probability_calibrated": False, "dimensions": DIMENSIONS,
            "nodes": nodes, "transfer_matrix": matrix,
            "equation_registry": equations, "equation_gaps": equation_gaps,
            "ensembles": ensembles,
            "dependence_graph": {"groups": groups, "nodes": sorted(set(models) | {member for group in groups for member in group["members"]}), "edges": [{"from": member, "to": group["id"], "kind": "uses_shared_input"} for group in groups for member in group["members"]],
                                 "aggregation": "No product/sum of confidence; shared source/model inputs form dependence groups; repeated frames/seeds are not biological confirmations"},
            "project": {"unsupported_essential_bridges": essential, "weakest_essential_bridge_status": "unsupported",
                        "counterexamples": [{"kind": "formal_constraint_conflict", "status": core["status"], "constraints": core["conflict"], "scope": core["scope"], "evidence": [sources.pin("engineering/formal/RECEIPT.json", "/solver_result")]},
                                            {"kind": "no_robust_candidate_winner", "reported_robust_wins": controlled["n_robust_wins"], "candidates": len(controlled["designs"]), "scenario_flips": controlled["n_flip"], "unconverged_rows": controlled["n_unconverged"], "evidence": [sources.pin("engineering/simulation/results_controlled/summary.json")]}],
                        "next_actions": next_actions, "action_policy": "Blocker/dependency priority only; no invented expected-information or utility numbers"},
            "claim_refs": [{"ref": member["ref"], "subsystem": member["subsystem"], "status": "snapshot_pin_not_live_store_acceptance"} for member in project["members"]],
            "display_legend": {"default_dimension": "empirical_validation", "unknown": {"color": "#88929d", "label": "Accuracy/calibration unknown"},
                               "checked_scoped": {"color": "#48a8ca", "label": "Recorded scoped computational check"},
                               "partial_scoped": {"color": "#d7a651", "label": "Partial model evidence; inspect scope"},
                               "refused": {"color": "#cf7166", "label": "Transfer refused"},
                               "warning": "Colors are categorical evidence states, not calibrated probabilities or spatial-error scores"},
            "notices": ["Regional labels are UI anchors, not measured anatomical segmentation or uniform local accuracy.",
                        "Recorded receipts were read and code hashes recomputed; simulations/Lean were not rerun by this projection.",
                        "No biological success probability or aggregate confidence score is produced.",
                        "No ensemble robustness fraction is issued without a pinned prospectively declared predicate and replayable run metrics."],
            "evidence_index": sorted(sources.index.values(), key=lambda item: item["path"])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("artifacts/assurance"))
    parser.add_argument("--root", type=Path, default=ROOT, help="Local integrated input checkout; no network fetching")
    args = parser.parse_args()
    result = build(args.root)
    args.output.mkdir(parents=True, exist_ok=True)
    data = json.dumps(result, indent=2, sort_keys=True, allow_nan=False).encode() + b"\n"
    (args.output / "map.json").write_bytes(data)
    from .render import regional_svg
    svg = regional_svg(result).encode()
    (args.output / "regions.svg").write_bytes(svg)
    manifest = {"schema": "frontier.assurance.receipt/1", "action": "evidence_projection", "output": {"path": "map.json", "sha256": digest_bytes(data), "byte_size": len(data)},
                "code_sha256": {p.name: digest_bytes(p.read_bytes()) for p in sorted(Path(__file__).parent.glob("*.py"))},
                "sources": result["evidence_index"], "checks_executed": "source byte hashes and recorded receipt status read; no new simulation/Lean execution"}
    manifest["renderAction"] = {"kind": "render_categorical_schematic", "input_sha256": digest_bytes(data),
                              "output": {"path": "regions.svg", "sha256": digest_bytes(svg)},
                              "scope": "UI region schematic with colors derived from vector statuses; no anatomical measurement or simulated state field"}
    (args.output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"status": "built", "nodes": len(result["nodes"]), "sources": len(result["evidence_index"]), "sha256": digest_bytes(data)}))


if __name__ == "__main__":
    main()
