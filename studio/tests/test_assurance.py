"""Assurance derives from actual pinned receipts; no synthetic confidence scores."""
from hashlib import sha256
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from engineering.assurance.build import DIMENSIONS, REGIONS, ROOT, SCALES, Sources, build, dimension_check
from engineering.assurance import ensembles
from engineering.assurance.render import regional_svg


@pytest.fixture(scope="module")
def result():
    return build()


def node(result, identifier):
    return next(item for item in result["nodes"] if item["id"] == identifier)


def clone_sources(result, tmp_path):
    paths = {item["path"] for item in result["evidence_index"]}
    for item in result["nodes"]:
        for value in item["vector"].values():
            paths.update(row["path"] for row in value.get("source_identity", {}).get("checked", []))
    for name in paths:
        source, target = ROOT / name, tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    return tmp_path


def test_every_region_and_scale_keeps_biological_accuracy_unknown(result):
    assert result["biological_success_probability"] is None and result["probability_calibrated"] is False
    assert {item["id"] for item in result["nodes"] if item["kind"] == "region"} == set(REGIONS)
    assert {item["id"] for item in result["nodes"] if item["kind"] == "scale"} == {"flying-fish:" + scale for scale in SCALES}
    for item in result["nodes"]:
        assert set(item["vector"]) == set(DIMENSIONS)
        assert item["vector"]["empirical_validation"]["status"] == "unknown"
        if item["id"] not in {"pectoral-left", "pectoral-right", "flying-fish:organ", "finbeam_euler_bernoulli"} or not result["ensembles"]:
            assert item["vector"]["ensemble_robustness"]["status"] == "unknown"
    assert node(result, "caudal")["vector"]["numerical_fidelity"]["status"] == "unknown"


def test_all_conclusion_pins_resolve_exact_bytes_and_json_selectors(result):
    count = 0
    def visit(value):
        nonlocal count
        if isinstance(value, dict):
            if {"path", "sha256", "selector"} <= value.keys():
                content = (ROOT / value["path"]).read_bytes()
                assert sha256(content).hexdigest() == value["sha256"]
                if value["selector"].startswith("/"):
                    current = json.loads(content)
                    for token in value["selector"].split("/")[1:]:
                        current = current[int(token)] if isinstance(current, list) else current[token]
                count += 1
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)
    visit(result)
    assert count > 100


def test_formal_scope_mutation_axioms_and_current_identity_are_distinct(result):
    formal = node(result, "flying_fish_constraints")["vector"]["formal_properties"]
    assert formal["status"] == "checked_scoped" and formal["assumptions"]
    assert formal["source_identity"]["status"] == "matches"
    assert all(formal["anti_triviality"]["each_block_rejected"].values())
    assert "m" in formal["anti_triviality"]["parameters_in_theorem"]
    assert formal["anti_triviality"]["axioms"]
    assert "no independent" in formal["anti_triviality"]["scope"]


def test_real_numerical_failures_and_auxiliary_source_mismatch_are_preserved(result):
    glide = node(result, "glide_pointmass")["vector"]
    assert glide["numerical_fidelity"]["unconverged_rows"] == 1
    assert glide["numerical_fidelity"]["status"] == "scoped_with_failures"
    assert glide["parameter_coverage"]["reported_robust_wins"] == 0
    assert glide["parameter_coverage"]["reported_scenario_flips"] > 0
    mech = node(result, "motor_clutch_ecm")["vector"]["numerical_fidelity"]
    assert mech["source_identity"]["mismatches"] == ["engineering/mechanobio/render.py"]
    assert mech["status"] == "checked_scoped"  # Actual model/control code still matches.


def test_changed_source_code_cannot_keep_checked_hh_status(result, tmp_path):
    root = clone_sources(result, tmp_path)
    with (root / "engineering/bioelectric/model.py").open("a") as stream:
        stream.write("\n# source mutation test\n")
    changed = build(root, include_ensembles=False)
    value = node(changed, "hh1952_gap_chain")["vector"]["numerical_fidelity"]
    assert value["status"] == "stale_or_failed_receipt"
    assert "engineering/bioelectric/model.py" in value["source_identity"]["mismatches"]


def test_failed_recorded_control_cannot_be_projected_as_passed(result, tmp_path):
    root = clone_sources(result, tmp_path)
    path = root / "artifacts/bioelectric/controls_baseline.json"
    controls = json.loads(path.read_text())
    controls["passed"] = False
    path.write_text(json.dumps(controls))
    value = node(build(root, include_ensembles=False), "hh1952_gap_chain")["vector"]["numerical_fidelity"]
    assert value["status"] == "stale_or_failed_receipt"


def test_transfer_matrix_has_unknown_not_zero_errors_and_electrical_refusal(result):
    matrix = result["transfer_matrix"]
    assert len(matrix["entries"]) == len(matrix["axes"]) ** 2
    assert all(entry["quantitative_error"] is None for entry in matrix["entries"])
    voltage = next(entry for entry in matrix["entries"] if entry["from"] == "hh1952_gap_chain" and entry["to"] == "finbeam_euler_bernoulli")
    assert voltage["status"] == "refused" and voltage["unit_check"]["status"] == "refused"
    aero = next(entry for entry in matrix["entries"] if entry["from"] == "flying_fish_constraints" and entry["to"] == "glide_pointmass")
    assert aero["status"] == "assumption_scenario"
    assert {row["id"] for row in aero["relations"]} == {"c01_mass", "c02_area", "c03_span", "c04_speed"}


def test_dimension_check_includes_electrical_current_and_never_promises_biology():
    assert dimension_check({"kg": 1, "m": 2, "s": -3, "A": -1}, {"kg": 1, "m": 3, "s": -2})["status"] == "refused"
    assert dimension_check(None, {"m": 1})["status"] == "unknown"
    check = dimension_check({"m": 1}, {"m": 1, "A": 0})
    assert check["status"] == "consistent_dimensions_only" and "no biological" in check["reason"]


def test_shared_assumptions_not_multiplied_and_no_fabricated_information_utility(result):
    groups = result["dependence_graph"]["groups"]
    assert len({group["id"] for group in groups}) == len(groups)
    aero = next(group for group in groups if group["id"] == "assumed-aerodynamic-coefficients")
    assert {"flying_fish_constraints", "glide_pointmass", "finbeam_euler_bernoulli"} <= set(aero["members"])
    assert result["project"]["weakest_essential_bridge_status"] == "unsupported"
    for action in result["project"]["next_actions"]:
        assert action["expected_information_gain"] is None and action["expected_utility"] is None


def test_equation_stack_links_actual_files_models_ports_and_explicit_gaps(result):
    equations = result["equation_registry"]
    assert len(equations) >= 10 and len({row["id"] for row in equations}) == len(equations)
    for equation in equations:
        assert equation["latex"] and equation["variables"] and equation["sources"] and equation["check_evidence"]
        assert equation["assumptions"] and equation["input_ports"] and equation["output_ports"]
    fin = node(result, "pectoral-left")
    assert {"eq-fin-beam", "eq-pressure-line-load"} <= set(fin["equation_ids"])
    assert fin["dependency_chain"]["transfers"]
    assert all(gap["latex"] is None for gap in result["equation_gaps"])
    assert any(gap["id"] == "gene-to-fin-program" for gap in result["equation_gaps"])


def test_projection_deterministic_and_source_paths_do_not_escape(result, tmp_path):
    assert build() == result
    outside = tmp_path.parent / "outside-assurance-test.json"
    with pytest.raises(ValueError):
        Sources(tmp_path).read(str(outside))


def test_categorical_region_schematic_is_derived_from_vector_not_numeric_confidence(result):
    svg = regional_svg(result)
    parsed = ET.fromstring(svg)
    assert parsed.tag.endswith("svg")
    assert "not a biological-success probability" in svg
    for label in REGIONS.values():
        assert label in svg
    assert "unknown" in svg and "partial_scoped" in svg


def ensemble_fixture(tmp_path, monkeypatch):
    """Test-only metrics; git ordering runner is explicitly stubbed, no simulation claim."""
    def write(name, value):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        return sha256(path.read_bytes()).hexdigest()
    predicate = {"id": "test-predicate", "declared_before_runs": True, "tip_over_length_limit": .1, "slope_limit_rad": .2}
    protocol = {"predicate": predicate, "parameter_draws": 3}
    protocol_hash = write("protocol.json", protocol)
    candidate = {"id": "test-only-candidate"}
    draws = [{"u": value} for value in [0, 1, 2]]
    actual, rows = [], []
    for index, tip in enumerate([.05, .1, .15]):
        metrics = {name: {"tip_over_L": tip, "max_slope_rad": .1} for name in ["uniform", "tip_same_total_force"]}
        passed = tip <= .1
        actual.append({"id": str(index), "passed": passed, "cases": {name: {"summary": value} for name, value in metrics.items()}})
        inputs = json.dumps({"draw": draws[index], "candidate": candidate}, sort_keys=True, separators=(",", ":")).encode()
        rows.append({"id": str(index), "summary": metrics, "passed": passed, "input_sha256": sha256(inputs).hexdigest(), "protocol_sha256": protocol_hash,
                     "region_ids": ["pectoral-left"], "shared_input_groups": ["paired:" + str(index)]})
    artifact_hash = write("results.json", {"draws": draws, "candidates": [{"candidate": candidate, "runs": actual}]})
    for index, row in enumerate(rows):
        row["result_artifact"] = {"path": "results.json", "sha256": artifact_hash, "selector": f"$.candidates[0].runs[{index}]"}
    value = {"schema": "frontier.assurance.ensemble/1", "protocol": {"path": "protocol.json", "sha256": protocol_hash},
             "protocol_commit": "a" * 40, "run_code_revision": "b" * 40, "predicate": predicate, "runs": rows,
             "candidate": candidate, "numerator": 2, "denominator": 3, "fraction": 2 / 3}
    write("ensemble.json", value)
    monkeypatch.setattr(ensembles.subprocess, "check_output", lambda *args, **kwargs: (tmp_path / "protocol.json").read_bytes())
    monkeypatch.setattr(ensembles.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0))
    return value


def test_prospective_fraction_recomputed_from_paired_metrics_not_load_or_mesh_counts(tmp_path, monkeypatch):
    ensemble_fixture(tmp_path, monkeypatch)
    value = ensembles.verify(Sources(tmp_path), "ensemble.json")
    assert value["numerator"] == 2 and value["denominator"] == 3
    assert value["fraction"] == 2 / 3 and value["biological_success_probability"] is None
    assert len(value["shared_input_groups"]) == 3


@pytest.mark.parametrize("mutation", ["numerator", "empty", "digest", "predicate", "passed"])
def test_tampered_or_vacuous_ensemble_cannot_earn_robustness(tmp_path, monkeypatch, mutation):
    value = ensemble_fixture(tmp_path, monkeypatch)
    if mutation == "numerator":
        value["numerator"] = 3
    elif mutation == "empty":
        value["runs"] = []
        value["denominator"] = 0
    elif mutation == "digest":
        value["runs"][0]["result_artifact"]["sha256"] = "0" * 64
    elif mutation == "predicate":
        value["predicate"] = dict(value["predicate"], tip_over_length_limit=1)
    else:
        value["runs"][0]["passed"] = False
    (tmp_path / "ensemble.json").write_text(json.dumps(value))
    with pytest.raises(ValueError):
        ensembles.verify(Sources(tmp_path), "ensemble.json")
