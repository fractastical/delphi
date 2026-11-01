"""The genotype-to-design interface layer: bookkeeping and refusals only. All fixtures live in a temporary tree; nothing is fetched or run."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from engineering.biodesign_compiler import compile as bc
from engineering.biodesign_compiler import genotype as G

ROOT = Path(__file__).resolve().parents[1]
CTX = {"species": "Danio rerio", "tissue": "caudal fin", "cell_state": "regenerating blastema", "life_stage": "adult", "condition": "amputation", "allele": "wild type", "construct_context": "LEN-P2:EGFP reporter"}


def sha(b):
    return hashlib.sha256(b).hexdigest()


NSHA = sha(b"ACGTACGTAC")  # the normalised nucleotide digest of the fixture sequence (not the digest of the file's bytes)


def measurement(lo=0.5, hi=2.0, ctx=None, evidence_class="measured_experiment", unit="1", schema=G.MEASUREMENT_SCHEMA, inputs=None, transfer_version="v1"):
    return {"schema": schema, "inputs": inputs, "transfer_version": transfer_version, "transfer": {"quantity": "q", "unit": unit, "lo": lo, "hi": hi, "context": ctx or CTX, "evidence_class": evidence_class}}


def ref(root, rel):
    return {"path": rel, "sha256": sha((root / rel).read_bytes())}


def default_inputs(i, digest=None):
    return {"sequence_sha256": digest or NSHA} if i == "I1" else {"upstream": sha(f"upstream-{i}".encode())}


def evidence(root, i, status="calibrated_transfer", ctx=None, lo=0.5, hi=2.0, quantity="q", unit="1", value=1.0, digest=None, inputs=None):
    """Interface evidence plus the pinned measurement it cites (always written with the default bounds, unit and context, so a changed argument is a mismatch)."""
    inp = inputs if inputs is not None else default_inputs(i, digest)
    name = f"meas/{i}-{(digest or '')[:8]}.json" if digest else f"meas/{i}.json"
    (root / name).write_text(json.dumps(measurement(inputs=default_inputs(i, digest))))
    return {"interface": i, "status": status, "context": ctx or CTX, "inputs": inp, "transfer_version": "v1", "transfer": {"quantity": quantity, "unit": unit, "lo": lo, "hi": hi, "value_used": value, "bound_ref": {**ref(root, name), "pointer": "/transfer"}}}


def vplan(root, cand=None, status="pass", cases=None, check_extra=None, plan_id="vp1", version=1, res_extra=None, checks=None, validator=True, cand_digest=None):
    """A frozen validation plan and its separate result record, each written as a pinned artifact whose bytes carry the same metadata."""
    checks = checks if checks is not None else [{"id": "c1", "interface": "I3", "endpoint": True, "executable": True, **(check_extra or {})}]
    meta = {"id": plan_id, "version": version, "candidate_id": cand, "endpoint": "EI in the stated context", "decision": "whether to build", "required_checks": checks, **({"candidate_sequence_sha256": cand_digest} if cand_digest else {})}
    (root / f"meas/plan-{plan_id}.json").write_text(json.dumps({"schema": G.PLAN_SCHEMA, **meta}))
    plan = {**meta, "ref": ref(root, f"meas/plan-{plan_id}.json")}
    res = {
        "plan_id": plan_id,
        "plan_version": version,
        "check_id": checks[0]["id"],
        "status": status,
        "cases": cases if cases is not None else {"positive": 2, "negative": 1, "negative_rejected": True},
        "scope": "one context",
        "licenses": "the interface in this context only",
        **({"candidate_sequence_sha256": cand_digest} if cand_digest else {}),
        **(res_extra or {}),
    }
    doc = {"schema": G.RESULT_SCHEMA, **{k: res[k] for k in ("plan_id", "plan_version", "check_id", "status", "cases", "scope", "licenses")}, **({"candidate_sequence_sha256": cand_digest} if cand_digest else {})}
    if validator:
        doc["validator"] = {"role": "independent checker", "identity": "checker-B", "dependence_identity": "no shared data with the author"}
    (root / f"meas/res-{plan_id}.json").write_text(json.dumps(doc))
    res["ref"] = ref(root, f"meas/res-{plan_id}.json")
    return plan, res


def design(root, claim="working_assembly", ifs=("I1", "I2", "I3", "I4", "I5"), **kw):
    plan, res = vplan(root)
    d = {
        "schema": G.DESIGN_SCHEMA,
        "id": "d1",
        "claim": claim,
        "context": copy.deepcopy(CTX),
        "interface_evidence": [evidence(root, i) for i in ifs],
        "validation_plans": [plan],
        "validation_results": [res],
        "sequence_candidates": [{"id": "default", "source_ref": ref(root, "seq/cand.fa"), "evidence_kind": "measured_expression"}],
    }
    d.update(kw)
    return d


@pytest.fixture()
def tree(tmp_path):
    (tmp_path / "seq").mkdir()
    (tmp_path / "meas").mkdir()
    (tmp_path / "ledger").mkdir()
    seq = b">candidate\nACGTACGTAC\n"
    (tmp_path / "seq/cand.fa").write_bytes(seq)
    for i in G.INTERFACES:
        (tmp_path / f"meas/{i}.json").write_text(json.dumps(measurement(inputs=default_inputs(i))))
    ledger = {
        "schema": G.LEDGER_SCHEMA,
        "protocol": {"path": "p.json", "sha256": "0" * 64},
        "sequences": [
            {"id": "seq-len", "sequence_sha256": NSHA, "length_nt": 10, "artifact_ref": {"path": "seq/cand.fa", "sha256": sha(seq)}, "sequence_kind": "natural_reference", "reference": None},
            {"id": "seq-null", "sequence_sha256": None, "length_nt": None, "artifact_ref": None, "sequence_kind": "unknown", "reference": None},
            {"id": "seq-evo", "sequence_sha256": "e" * 64, "length_nt": 100, "artifact_ref": None, "sequence_kind": "existing_model_output", "reference": None},
        ],
        "entries": [
            {
                "id": "e-len",
                "evidence_class": "paper_reported_experiment",
                "species": CTX["species"],
                "context": {"tissue": CTX["tissue"], "cell_state": CTX["cell_state"], "life_stage": CTX["life_stage"], "condition": CTX["condition"], "allele": CTX["allele"], "construct_context": CTX["construct_context"]},
                "demonstrated_readout": "reporter expression",
                "model_ready": False,
            },
            {"id": "e-evo", "evidence_class": "model_output", "species": CTX["species"], "tissue": None, "cell_state": None, "life_stage": None, "injury_or_condition": None, "allele": None, "tested_construct_or_promoter_context": None},
        ],
        "bridges": [
            {"id": "b-supported", "from_entry": "e-len", "to_layer": "expression", "status": "context_supported", "conditions": "adult caudal regeneration"},
            {"id": "b-contra", "from_entry": "e-len", "to_layer": "growth_material", "status": "contradicted"},
            {"id": "b-open", "from_entry": "e-len", "to_layer": "growth_material", "status": "unresolved"},
        ],
    }
    (tmp_path / "ledger/ledger.json").write_text(json.dumps(ledger))
    return tmp_path


GRAPH = G.baseline_graph(ROOT)


def compile_(root, d):
    return G.compile_design(root, GRAPH, d)


def test_baseline_graph_has_five_unknown_interfaces_grounded_in_real_bridges():
    g = GRAPH
    assert [n["id"] for n in g["nodes"]] == list(G.NODES) and list(g["interfaces"]) == ["I1", "I2", "I3", "I4", "I5"]
    assert all(v["state"] == "unknown" and v["bridges"] and not v["bridges_not_in_sources"] for v in g["interfaces"].values())
    assert any(b["bridge"] == "regulatory-expression-to-channel-density-conductance" for b in g["interfaces"]["I2"]["bridges"])
    assert g["interfaces"]["I1"]["proposed_experiments"][0].get("note", "").startswith("no experiment")
    assert [e["id"] for e in g["interfaces"]["I3"]["proposed_experiments"]] == ["wp-fin-EI-load"]
    for k, v in g["sources"].items():
        assert bc.sha((ROOT / v["path"]).read_bytes()) == v["sha256"]
    assert g["biological_success_probability"] is None and "a working genome or construct was designed" in g["must_not_say"]


def test_a_claimed_working_assembly_is_rejected_when_the_baseline_has_no_evidence():
    r = G.compile_design(ROOT, GRAPH, {"schema": G.DESIGN_SCHEMA, "id": "b", "claim": "working_assembly", "context": CTX})
    assert r["verdict"] == "rejected" and [u["interface"] for u in r["assembly_unresolved_interfaces"]] == ["I1", "I2", "I3", "I4", "I5"]
    assert r["candidate_sequence_artifact_refs"] == [] and "no DNA was generated" in r["scope"]


def test_a_missing_bridge_rejects_a_working_claim_but_a_proposal_is_allowed(tree):
    r = compile_(tree, design(tree, ifs=("I1", "I2", "I4", "I5")))
    assert r["verdict"] == "rejected" and [u["interface"] for u in r["assembly_unresolved_interfaces"]] == ["I3"]
    assert any("not calibrated for this context: I3" in x for x in r["reasons"])
    assert compile_(tree, design(tree, claim="proposal", ifs=("I1", "I2", "I4", "I5")))["verdict"] == "proposal_only"


def test_all_five_calibrated_for_the_stated_context_is_only_consistent_evidence_not_a_biological_result(tree):
    r = compile_(tree, design(tree))
    assert r["verdict"] == "consistent_evidence_for_the_stated_context" and r["reasons"] == [] and r["assembly_unresolved_interfaces"] == []
    assert "no biological claim follows" in r["scope"]


def test_stale_sequence_reference_and_unpinned_literal_are_refused(tree):
    d = design(tree, sequence_candidates=[{"id": "c1", "source_ref": ref(tree, "seq/cand.fa"), "evidence_kind": "measured_expression", "length": 10}])
    assert compile_(tree, d)["verdict"] == "consistent_evidence_for_the_stated_context"
    (tree / "seq/cand.fa").write_bytes(b">candidate\nACGTACGTAA\n")  # the pinned bytes change after pinning
    r = compile_(tree, d)
    assert r["verdict"] == "rejected" and any("stale sequence reference" in x for x in r["reasons"]) and r["candidate_sequence_artifact_refs"] == []
    lit = design(tree, sequence_candidates=[{"id": "c2", "sequence": "ACGT"}])
    r = compile_(tree, lit)
    assert r["verdict"] == "rejected" and any("no unpinned DNA" in x for x in r["reasons"])


def test_cross_species_context_mismatch_makes_the_calibration_inapplicable(tree):
    d = design(tree)
    d["context"]["species"] = "Hirundichthys speculiger"  # the design is for a flying fish, the measurements were zebrafish
    r = compile_(tree, d)
    assert r["verdict"] == "rejected" and len(r["assembly_unresolved_interfaces"]) == 5
    a = r["interface_assessment"][0]
    assert a["applicable"] is False and a["effective"] == "unknown" and "species: evidence 'Danio rerio' vs design 'Hirundichthys speculiger'" in a["reasons"][0]
    d2 = design(tree)
    d2["context"]["life_stage"] = "larva"
    assert compile_(tree, d2)["verdict"] == "rejected", "another stage does not inherit the calibration either"


def test_a_mutated_measured_transfer_bound_is_rejected(tree):
    d = design(tree)
    d["interface_evidence"][2] = evidence(tree, "I3", lo=0.1)  # the design claims a wider bound than the measurement states
    r = compile_(tree, d)
    assert r["verdict"] == "rejected" and any("differs from the pinned measurement [0.5, 2.0]" in x for x in r["reasons"]) and r["interface_state"]["I3"] == "unknown"
    d = design(tree)
    (tree / "meas/I2.json").write_text(json.dumps({"transfer": {"lo": 0.5, "hi": 9.0}}))  # or the pinned measurement itself is edited
    r = compile_(tree, d)
    assert r["verdict"] == "rejected" and any("I2" in x and "changed" in x for x in r["reasons"])
    out = design(tree)
    out["interface_evidence"][0]["transfer"]["value_used"] = 5.0
    assert any("inside the stated bound" in x for x in compile_(tree, out)["reasons"])


def test_homology_or_marker_evidence_never_raises_an_interface_above_unknown(tree):
    d = design(tree, claim="proposal", ifs=(), sequence_candidates=[{"id": "h", "source_ref": ref(tree, "seq/cand.fa"), "evidence_kind": "homology"}])
    r = compile_(tree, d)
    assert r["interface_state"]["I1"] == "unknown" and r["candidate_sequence_artifact_refs"][0]["evidence_kind"] == "homology" and "not function" in r["candidate_sequence_artifact_refs"][0]["note"]


def test_build_plans_stay_proposals_and_no_order_is_accepted(tree):
    d = design(tree, claim="proposal", ifs=(), build_plan_proposals=[{"id": "p1", "ref": ref(tree, "seq/cand.fa"), "state": "ordered"}])
    r = compile_(tree, d)
    assert r["build_plan_proposal_refs"] == [] and r["verdict"] == "proposal_only"
    assert compile_(tree, design(tree, claim="working_assembly", ifs=(), build_plan_proposals=[{"id": "p1", "ref": ref(tree, "seq/cand.fa"), "state": "ordered"}]))["verdict"] == "rejected"


def test_pinned_ledger_carries_context_evidence_class_and_keeps_missing_data_null(tree):
    led = {"ref": ref(tree, "ledger/ledger.json"), "sequence_ids": ["seq-len", "seq-null", "seq-evo"], "entry_ids": ["e-len", "e-evo"]}
    d = design(tree, claim="proposal", ifs=(), ledger=led, sequence_candidates=[], interface_evidence=[{"interface": "I1", "ledger_bridge": "b-supported"}, {"interface": "I3", "ledger_bridge": "b-open"}])
    r = compile_(tree, d)
    assert r["verdict"] == "proposal_only" and r["ledger"]["ref"]["sha256"] == led["ref"]["sha256"]
    assert [s["id"] for s in r["candidate_sequence_artifact_refs"]] == ["seq-len"]
    assert {s["id"] for s in r["sequences_without_artifact"]} == {"seq-null", "seq-evo"}, "a null artifact is carried as null, never guessed"
    ent = {e["id"]: e for e in r["ledger_entries_consumed"]}
    assert ent["e-evo"]["functional_validation"] == "unknown" and ent["e-len"]["context"]["construct_context"] == CTX["construct_context"]
    # a context-supported ledger bridge is measured for ONE context, never a calibrated transfer function
    assert r["interface_state"]["I1"] == "measured_context" and r["interface_state"]["I3"] == "unknown"
    claim = copy.deepcopy(d)
    claim["claim"] = "working_assembly"
    assert compile_(tree, claim)["verdict"] == "rejected"


def test_a_changed_ledger_or_a_contradicted_bridge_blocks_a_working_claim(tree):
    led = {"ref": ref(tree, "ledger/ledger.json"), "sequence_ids": ["seq-len"], "entry_ids": ["e-len"]}
    ifs = [{"interface": "I2", "ledger_bridge": "b-contra"}]
    r = compile_(tree, design(tree, ifs=("I1", "I3", "I4", "I5"), ledger=led, interface_evidence=[evidence(tree, i) for i in ("I1", "I3", "I4", "I5")] + ifs))
    assert r["verdict"] == "rejected" and any("contradicted" in x for x in r["reasons"]) and r["interface_state"]["I2"] == "unknown"
    p = tree / "ledger/ledger.json"
    p.write_text(p.read_text().replace("adult caudal regeneration", "any context"))
    r = compile_(tree, design(tree, claim="proposal", ifs=(), ledger=led, sequence_candidates=[]))
    assert r["verdict"] == "proposal_only" and any("stale ledger" in x for x in r["reasons"])  # a proposal is not rejected, but the changed ledger is reported and not read
    assert r["ledger_entries_consumed"] == [] and r["candidate_sequence_artifact_refs"] == [] and r["ledger"]["ref"] == led["ref"]
    assert compile_(tree, design(tree, ledger=led))["verdict"] == "rejected"


def test_propagation_invalidates_only_downstream_claims_and_retains_pinned_independent_checks(tree):
    pins = [ref(tree, "meas/I1.json")]
    d = design(
        tree,
        claims=[{"id": "c-seq", "depends_on": ["dna", "I1"]}, {"id": "c-expr", "depends_on": ["expression", "I2"]}, {"id": "c-ei", "depends_on": ["I3"]}, {"id": "c-aero", "depends_on": ["I4"]}],
        checked_layers=[{"id": "regulatory-map", "node": "expression", "pins": pins}, {"id": "aero-numerical", "node": "performance", "pins": pins}, {"id": "fin-geometry", "node": "shape_mechanics", "pins": pins}],
    )
    p = G.propagate(GRAPH, d, {"node": "dna"}, tree)
    assert p["invalidated_claims"] == ["c-seq", "c-expr", "c-ei", "c-aero"] and p["invalidated_interfaces"] == ["I1", "I2", "I3", "I4", "I5"]
    assert p["retained_checked_layers"] == ["regulatory-map", "aero-numerical", "fin-geometry"] and "original pinned model or geometry only" in p["retained_scope"]
    q = G.propagate(GRAPH, d, {"node": "shape_mechanics"}, tree)
    assert q["invalidated_interfaces"] == ["I4", "I5"] and q["retained_calibrations"] == ["I1", "I2", "I3"] and q["invalidated_calibrations"] == ["I4", "I5"]
    assert q["retained_claims"] == ["c-seq", "c-expr", "c-ei"] and q["invalidated_claims"] == ["c-aero"]
    assert q["invalidated_checked_layers"] == ["fin-geometry"] and q["retained_checked_layers"] == ["regulatory-map", "aero-numerical"]
    r = G.propagate(GRAPH, d, {"interface": "I3"}, tree)
    assert r["invalidated_interfaces"] == ["I3", "I4", "I5"] and r["retained_calibrations"] == ["I1", "I2"] and r["retained_claims"] == ["c-seq", "c-expr"]


def test_a_checked_layer_without_dependency_pins_or_with_changed_pins_is_not_silently_retained(tree):
    d = design(tree, checked_layers=[{"id": "unpinned", "node": "performance"}, {"id": "pinned", "node": "performance", "pins": [ref(tree, "meas/I1.json")]}, {"id": "stale", "node": "expression", "pins": [ref(tree, "meas/I2.json")]}])
    (tree / "meas/I2.json").write_text("changed")
    p = G.propagate(GRAPH, d, {"node": "dna"}, tree)
    assert p["retained_checked_layers"] == ["pinned"]
    why = {x["id"]: x["why"] for x in p["unverified_checked_layers"]}
    assert "no dependency pins" in why["unpinned"] and "no longer verify" in why["stale"]
    assert [x["id"] for x in G.propagate(GRAPH, d, {"node": "dna"})["unverified_checked_layers"]] == ["unpinned", "pinned", "stale"], "without a root nothing can be checked, so nothing is retained"


def test_generated_graph_artifacts_are_current_and_acceptance_command_passes():
    files = G.build_files(ROOT)
    out = ROOT / "artifacts/biodesign-compiler"
    assert {k: (out / k).read_text() for k in files} == files
    p = subprocess.run([sys.executable, "-m", "engineering.biodesign_compiler.genotype", "--check"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and p.stdout.strip() == "PASS"


def test_every_causal_boundary_has_an_exact_input_observation_controls_and_open_instrument_slots():
    v = G.validation_slices(GRAPH, {"context": CTX}, None, ROOT)
    assert list(v["interfaces"]) == ["I1", "I2", "I3", "I4", "I5"] and v["schema"] == G.VALIDATION_SCHEMA
    for iid, s in v["interfaces"].items():
        assert s["input"] and s["observation"] and len(s["controls"]) >= 2 and s["what_remains_unknown"] and s["recorded_bridges"]
        assert "closes only as calibrated_transfer" in s["decision_rule"] and s["context_required"] == list(G.CONTEXT_FIELDS) and s["context_stated"] == CTX
        kinds = {x["kind"] for x in s["instrument_slots"]}
        assert kinds == {"physical", "virtual"} and all((x["contract_ref"] is not None) != ("gap" in x) for x in s["instrument_slots"])
        assert s["state"] == "unknown" and s["invalidated_by_dna_change"] is True
    assert [e["id"] for e in v["interfaces"]["I3"]["recorded_experiments"]] == ["wp-fin-EI-load"]
    assert "requirements for validation, not protocols, not results" in v["scope"] and "no calibrated genotype-to-phenotype transfer" in v["scope"]
    assert "transfer_function" not in json.dumps(v)


def test_cutsets_list_the_interfaces_a_claim_crosses_and_which_are_not_calibrated():
    v = G.validation_slices(GRAPH, {"context": CTX})
    cs = {c["claim"]: c for c in v["cutsets"]}
    assert cs["genotype to fin shape"]["interfaces"] == ["I1", "I2", "I3"]
    assert cs["genotype to aerodynamic performance"]["interfaces"] == ["I1", "I2", "I3", "I4"]
    assert cs["genotype to organism behaviour"]["interfaces"] == ["I1", "I2", "I3", "I4", "I5"]
    assert cs["expression to fin shape"]["interfaces"] == ["I2", "I3"] and cs["fin shape to performance, genotype held fixed"]["interfaces"] == ["I4"]
    assert all(c["not_calibrated"] == c["interfaces"] for c in v["cutsets"])
    done = G.cutset(GRAPH, "dna", "shape_mechanics", {"interface_state": {"I1": "calibrated_transfer", "I2": "measured_context", "I3": "unknown"}})
    assert done["not_calibrated"] == ["I2", "I3"]


def test_a_proposed_dna_change_invalidates_every_slice_but_not_another_layers_own_check(tree):
    rep = compile_(tree, design(tree))
    v = G.validation_slices(GRAPH, design(tree), {**rep, "compiled": json.loads((ROOT / "artifacts/biodesign-compiler/report.json").read_text())["compiled"]})
    assert v["after_proposed_dna_change"]["invalidated_interfaces"] == ["I1", "I2", "I3", "I4", "I5"] and v["after_proposed_dna_change"]["retained_calibrations"] == []
    assert v["layers"]["dna"]["retained_when_dna_changes"] is False and v["layers"]["performance"]["retained_when_dna_changes"] is True
    assert v["layers"]["performance"]["compiler_axes"].get("numerical", "").startswith("measured") and v["layers"]["shape_mechanics"]["compiler_axes"]["structural_refs"] == "pass"
    assert all(s["state"] == "calibrated_transfer" for s in v["interfaces"].values()), "slices show the design's own interface state from the report"


def test_ledger_readouts_travel_with_the_expression_slices(tree):
    p = tree / "ledger/ledger.json"
    L = json.loads(p.read_text())
    L["entries"][0]["falsifiable_validation_readout"] = "reporter signal after deleting the element"
    L["entries"][0]["missing_causal_bridge"] = "growth and EI"
    p.write_text(json.dumps(L))
    led = {"ref": ref(tree, "ledger/ledger.json"), "sequence_ids": ["seq-len"], "entry_ids": ["e-len"]}
    d = design(tree, claim="proposal", ifs=(), ledger=led, sequence_candidates=[], interface_evidence=[{"interface": "I1", "ledger_bridge": "b-supported"}])
    r = compile_(tree, d)
    v = G.validation_slices(GRAPH, d, r)
    assert v["interfaces"]["I1"]["ledger_readouts"] == [{"entry": "e-len", "falsifiable_validation_readout": "reporter signal after deleting the element", "missing_causal_bridge": "growth and EI"}]
    assert v["interfaces"]["I1"]["state"] == "measured_context" and v["interfaces"]["I3"]["ledger_readouts"] == []


# ---------------------------------------------------------------------------------------------- bidirectional: forward and inverse
def seq_candidate(root, name, cid, **kw):
    dna = "".join("ACGT"[b % 4] for b in cid.encode()) + "ACGTACGT"
    (root / "seq" / name).write_bytes(f">{cid}\n{dna}\n".encode())
    c = {"id": cid, "source_ref": ref(root, f"seq/{name}"), "evidence_kind": "measured_expression", "observed_context": copy.deepcopy(CTX), "provenance": {"proposer": "designer-A", "method": "enhancer scan constrained by the ledger", "source_refs": ["ledger:e-len"]}}
    c.update(kw)
    return c


def inv_req(cands, target="shape_mechanics"):
    return {"schema": G.INVERSE_SCHEMA, "id": "r1", "target_node": target, "candidates": cands}


def test_every_interface_carries_forward_and_inverse_directions_and_none_is_invertible_today():
    assert "context-conditioned effect prediction" in G.DIRECTIONS["forward"] and "CANDIDATE SET" in G.DIRECTIONS["inverse"] and "never one guaranteed genome" in G.DIRECTIONS["inverse"]
    for iid, v in GRAPH["interfaces"].items():
        assert v["directions"]["forward"]["label"] == "context-conditioned effect prediction" and v["directions"]["forward"]["state"] == "unknown"
        assert v["directions"]["inverse"]["invertible"] is False and v["directions"]["inverse"]["proposable"] is True and "not a calibrated transfer" in v["directions"]["inverse"]["why"]
        assert v["directions"]["inverse"]["from"] == v["to"] and v["directions"]["inverse"]["to"] == v["from"]
    assert len(GRAPH["inverse_rules"]) == 5


def cdig(root, c):
    return G.check_sequence(root, c)["sequence_sha256"]


def fwd_for(root, cands, ifs=("I1", "I2", "I3"), plans=True, **kw):
    """A forward design for an inverse request: I1 evidence bound to each candidate's exact nucleotide digest, downstream evidence with input pins, and a
    validation plan per candidate that names that digest."""
    d = design(root, claim="proposal", ifs=(), **kw)
    d["sequence_candidates"] = []
    d["interface_evidence"] = [evidence(root, i) for i in ifs if i != "I1"] + ([evidence(root, "I1", digest=cdig(root, c)) for c in cands] if "I1" in ifs else [])
    d["validation_plans"], d["validation_results"] = [], []
    for c in cands if plans else []:
        plan, res = vplan(root, cand=c["id"], plan_id=f"vp-{c['id']}", cand_digest=cdig(root, c))
        d["validation_plans"].append(plan)
        d["validation_results"].append(res)
    return d


def test_inverse_on_the_repository_baseline_retains_proposals_but_endorses_nothing_and_names_the_bridges():
    base = {"schema": G.DESIGN_SCHEMA, "id": "b", "context": CTX}
    unresolved = {"id": "x", "sequence_unresolved": True, "unresolved_ref": "ledger:lepb-lenp2", "provenance": {"proposer": "p", "method": "m", "source_refs": ["s"]}}
    pinned = {"id": "y", "provenance": unresolved["provenance"], "source_ref": ref(ROOT, "artifacts/design-control/map.json")}
    r = G.compile_inverse(ROOT, GRAPH, inv_req([unresolved, pinned]), base)
    assert r["verdict"] == "proposals_only" and r["endorsed_candidate_set"] == [] and [b["interface"] for b in r["blocked_interfaces"]] == ["I1", "I2", "I3"]
    assert {p["id"] for p in r["proposals"]} == {"x"} and r["ineligible_candidates"][0]["id"] == "y", "y is a JSON file, not a sequence: a proposal needs a parsable sequence artifact"
    assert any("sequence unresolved" in f for f in r["proposals"][0]["flags"]) and all(not p["endorsed"] for p in r["proposals"])
    assert r["single_genome_guaranteed"] is False and r["added_sequences"] == 0
    assert any("fin-stiffness-calibration" in u["bridges"] for u in r["unresolved_bridges"] if u["interface"] == "I3")


def test_proposing_is_allowed_without_calibration_endorsing_is_not(tree):
    c = seq_candidate(tree, "a.fa", "a")
    r = G.compile_inverse(tree, GRAPH, inv_req([c]), fwd_for(tree, [c], ifs=("I1", "I2")))  # I3 uncalibrated
    assert r["verdict"] == "proposals_only" and r["proposals"][0]["id"] == "a" and r["endorsed_candidate_set"] == []
    assert any("not a calibrated transfer" in w for w in r["proposals"][0]["not_endorsed_because"]) and [b["interface"] for b in r["blocked_interfaces"]] == ["I3"]
    assert G.compile_inverse(tree, GRAPH, inv_req([c], "growth_material"), fwd_for(tree, [c], ifs=("I1", "I2")))["verdict"] == "endorsed_candidate_set", "a shallower target needs fewer interfaces"


def test_endorsement_needs_a_calibrated_path_forward_checks_and_a_passed_validation_plan(tree):
    cands = [seq_candidate(tree, "a.fa", "a"), seq_candidate(tree, "b.fa", "b")]
    r = G.compile_inverse(tree, GRAPH, inv_req(cands), fwd_for(tree, cands))
    assert r["verdict"] == "endorsed_candidate_set" and [c["id"] for c in r["endorsed_candidate_set"]] == ["a", "b"] and r["interfaces_crossed"] == ["I1", "I2", "I3"]
    assert r["endorsed_candidate_set"][0]["provenance"]["method"] == "enhancer scan constrained by the ledger" and r["unresolved_bridges"] == []
    assert [c["sequence"]["path"] for c in r["endorsed_candidate_set"]] == ["seq/a.fa", "seq/b.fa"], "only the candidates it was given"
    noplan = G.compile_inverse(tree, GRAPH, inv_req(cands), fwd_for(tree, cands[:1]) | {"interface_evidence": fwd_for(tree, cands)["interface_evidence"]})
    assert [c["id"] for c in noplan["endorsed_candidate_set"]] == ["a"] and any("no validation plan is attached" in w for p in noplan["proposals"] if p["id"] == "b" for w in p["not_endorsed_because"])
    bad = fwd_for(tree, cands[:1])
    bad["validation_results"][0]["status"] = "fail"
    assert G.compile_inverse(tree, GRAPH, inv_req(cands[:1]), bad)["verdict"] == "proposals_only"


def test_different_dna_with_identical_context_labels_cannot_inherit_a_measurement(tree):
    a, b = seq_candidate(tree, "a.fa", "a"), seq_candidate(tree, "b.fa", "b")
    assert cdig(tree, a) != cdig(tree, b)
    f = fwd_for(tree, [a])  # I1 is measured for a's nucleotide digest only; b carries the very same allele and construct labels
    f["validation_plans"].append(f["validation_plans"][0] | {"id": "vp-b", "candidate_id": "b"})
    r = G.compile_inverse(tree, GRAPH, inv_req([a, b]), f)
    assert [c["id"] for c in r["endorsed_candidate_set"]] == ["a"]
    why = " ".join(next(p for p in r["proposals"] if p["id"] == "b")["not_endorsed_because"])
    assert "did not pass the forward checks" in why or "no validation plan" in why
    fwd = compile_(tree, {**f, "sequence_candidates": [b]})  # the forward check for b alone: a's measurement is for other DNA
    assert fwd["interface_state"]["I1"] == "unknown" and any("not a candidate in this design" in x for x in fwd["reasons"])


def test_a_plan_or_result_bound_to_other_dna_cannot_validate_this_candidate(tree):
    a, b = seq_candidate(tree, "a.fa", "a"), seq_candidate(tree, "b.fa", "b")
    f = fwd_for(tree, [a])
    plan, res = vplan(tree, cand="a", plan_id="vp-a", cand_digest=cdig(tree, b))  # the plan and result name b's digest for candidate a
    f["validation_plans"], f["validation_results"] = [plan], [res]
    r = G.compile_inverse(tree, GRAPH, inv_req([a]), f)
    assert r["endorsed_candidate_set"] == [] and any("no validation plan is attached" in w for w in r["proposals"][0]["not_endorsed_because"])
    plan, res = vplan(tree, cand="a", plan_id="vp-a", cand_digest=cdig(tree, a))
    res["candidate_sequence_sha256"] = cdig(tree, b)  # result metadata for other DNA than its plan
    f["validation_plans"], f["validation_results"] = [plan], [res]
    c = G.evaluate_validation(tree, f)["plans"][0]["checks"][0]
    assert c["status"] == "blocked" and "different candidate sequence" in c["reason"]


def test_downstream_interfaces_need_declared_input_pins_and_a_transfer_version_not_sequence_binding(tree):
    d = design(tree)
    d["interface_evidence"][2]["inputs"] = {}  # I3 without declared inputs
    assert any("must name its exact inputs" in x for x in compile_(tree, d)["reasons"])
    d = design(tree)
    d["interface_evidence"][2].pop("transfer_version")
    assert any("transfer version" in x for x in compile_(tree, d)["reasons"])
    d = design(tree)
    d["interface_evidence"][2]["inputs"] = {"geometry": ref(tree, "seq/cand.fa")}
    assert any("different inputs" in x for x in compile_(tree, d)["reasons"]), "the measurement carries other inputs than the evidence states"
    (tree / "meas/I3.json").write_text(json.dumps(measurement(inputs={"geometry": ref(tree, "seq/cand.fa")})))
    d["interface_evidence"][2]["transfer"]["bound_ref"]["sha256"] = sha((tree / "meas/I3.json").read_bytes())
    d["interface_evidence"][2]["inputs"] = {"geometry": ref(tree, "seq/cand.fa")}
    assert compile_(tree, d)["interface_state"]["I3"] == "calibrated_transfer", "declared upstream pins that match the measurement are enough for a downstream interface"
    (tree / "seq/cand.fa").write_text(">candidate\nACGTACGTAA\n")  # the pinned upstream input changed
    assert any("input 'geometry'" in x and "changed" in x for x in compile_(tree, d)["reasons"])
    d = design(tree)
    d["interface_evidence"][0]["inputs"] = {"sequence_sha256": "nothex"}
    assert any("inputs.sequence_sha256" in x for x in compile_(tree, d)["reasons"])


def test_a_measured_context_is_not_enough_to_endorse_through_an_edge(tree):
    a = seq_candidate(tree, "a.fa", "a")
    f = fwd_for(tree, [a], ifs=())
    f["interface_evidence"] = [evidence(tree, "I1", status="measured_context", digest=cdig(tree, a))]
    r = G.compile_inverse(tree, GRAPH, inv_req([a], "expression"), f)
    assert r["verdict"] == "proposals_only" and r["blocked_interfaces"][0]["state"] == "measured_context"


def test_an_invalid_forward_design_cannot_endorse_even_with_an_empty_path(tree):
    c = seq_candidate(tree, "a.fa", "a")
    f = fwd_for(tree, [c])
    f["context"].pop("species")  # an invalid context
    r = G.compile_inverse(tree, GRAPH, inv_req([c], "dna"), f)  # target dna: the path is empty
    assert r["interfaces_crossed"] == [] and r["endorsed_candidate_set"] == [] and r["verdict"] == "proposals_only"
    assert any("context.species is required" in x for x in r["forward_design_problems"]) and any("forward design is invalid" in w for w in r["proposals"][0]["not_endorsed_because"])
    none = G.compile_inverse(tree, GRAPH, inv_req([], "dna"), f)
    assert none["verdict"] == "invalid_forward_design"


def test_candidates_need_provenance_a_pinned_parsed_sequence_and_are_never_assumed_interchangeable(tree):
    good = seq_candidate(tree, "a.fa", "good")
    noprov = seq_candidate(tree, "b.fa", "noprov")
    noprov["provenance"] = {"proposer": "x"}
    stale = seq_candidate(tree, "c.fa", "stale")
    ortho = seq_candidate(tree, "d.fa", "ortholog", ortholog_of={"species": "Danio rerio", "gene": "lepb"}, evidence_kind="homology", observed_context={**CTX, "species": "Hirundichthys speculiger"})
    f = fwd_for(tree, [good, noprov, ortho])
    (tree / "seq/c.fa").write_bytes(b"changed after pinning")
    r = G.compile_inverse(tree, GRAPH, inv_req([good, noprov, stale, ortho]), f)
    assert r["verdict"] == "endorsed_candidate_set" and [c["id"] for c in r["endorsed_candidate_set"]] == ["good"]
    inel = {c["id"]: " ".join(c["issues"]) for c in r["ineligible_candidates"]}
    assert "provenance is missing: method, source_refs" in inel["noprov"] and "stale sequence reference" in inel["stale"]
    orth = next(p for p in r["proposals"] if p["id"] == "ortholog")
    assert not orth["endorsed"] and any("not interchangeable across species or contexts" in x for x in orth["flags"]), "an ortholog stays a retained, unendorsed proposal"


def test_a_bad_request_never_produces_a_genome(tree):
    only_bad = seq_candidate(tree, "a.fa", "a")
    f = fwd_for(tree, [only_bad])
    only_bad["provenance"] = {}
    r = G.compile_inverse(tree, GRAPH, inv_req([only_bad]), f)
    assert r["verdict"] == "no_eligible_proposal" and r["endorsed_candidate_set"] == [] and r["proposals"] == [] and r["single_genome_guaranteed"] is False
    assert G.compile_inverse(tree, GRAPH, {"schema": "x", "target_node": "nowhere", "candidates": []}, f)["verdict"] == "invalid_request"


# -------------------------------------------------------------------------------------------- finding 1: safe pins
@pytest.mark.parametrize("bad", ["/etc/passwd", "../outside.txt", "seq/../../outside.txt", "C:\\windows\\x", "", "seq/a\x00.fa"])
def test_pins_reject_absolute_traversal_and_odd_paths(tree, bad):
    assert G._pinned(tree, {"path": bad, "sha256": "0" * 64})[1]


def test_pins_reject_symlink_escape_and_oversize_files(tree, tmp_path_factory, monkeypatch):
    outside = tmp_path_factory.mktemp("outside") / "secret.txt"
    outside.write_text("secret")
    (tree / "seq/link.fa").symlink_to(outside)
    err = G._pinned(tree, {"path": "seq/link.fa", "sha256": sha(b"secret")})[1]
    assert err and "outside the repository" in err
    monkeypatch.setattr(G, "MAX_PIN_BYTES", 8)
    assert "larger than" in G._pinned(tree, ref(tree, "seq/cand.fa"))[1]
    assert G._pinned(tree, {"path": "seq/cand.fa", "sha256": "XYZ"})[1] == "no pinned path and sha256"


# ------------------------------------------------------------------------------------ finding 2: sequences bound to the artifact
def cand_from(root, name, text, **kw):
    (root / "seq" / name).write_text(text)
    return {"id": name, "source_ref": ref(root, f"seq/{name}"), "evidence_kind": "measured_expression", **kw}


def test_sequence_digest_and_length_are_bound_to_the_artifact_and_the_two_digests_stay_apart(tree):
    c = cand_from(tree, "x.fa", ">rec one\nacgt\nACGT\n")  # lower case and wrapping are normalised
    r = G.check_sequence(tree, c)
    assert r["valid"] and r["length_nt"] == 8 and r["sequence_sha256"] == sha(b"ACGTACGT") and r["file_sha256"] == c["source_ref"]["sha256"] != r["sequence_sha256"] and r["record_id"] == "rec"
    assert G.check_sequence(tree, {**c, "length": 8, "sequence_sha256": sha(b"ACGTACGT"), "sequence": "ACGT acgt"})["valid"]
    for kw, why in [
        ({"length": 9}, "declared length"),
        ({"length": True}, "declared length"),
        ({"length": float("nan")}, "declared length"),
        ({"length_nt": "8"}, "declared length"),
        ({"sequence_sha256": c["source_ref"]["sha256"]}, "normalised nucleotide digest"),
        ({"sequence": "ACGTACGA"}, "sequence literal differs"),
    ]:
        res = G.check_sequence(tree, {**c, **kw})
        assert not res["valid"] and any(why in p for p in res["problems"]), (kw, res["problems"])


def test_sequence_formats_are_explicit_and_ambiguity_is_rejected(tree):
    multi = cand_from(tree, "m.fa", ">a\nACGT\n>b\nTTTT\n")
    r = G.check_sequence(tree, multi)
    assert not r["valid"] and "2 records" in r["problems"][0]
    ok = G.check_sequence(tree, {**multi, "record_id": "b"})
    assert ok["valid"] and ok["sequence_sha256"] == sha(b"TTTT") and ok["record_id"] == "b" and ok["format"] == "fasta"
    assert "matches 0 records" in G.check_sequence(tree, {**multi, "record_id": "zzz"})["problems"][0]
    assert G.check_sequence(tree, cand_from(tree, "r.txt", "ACGT\nACGT\n"))["format"] == "raw"
    for name, text, why in [("e.fa", "", "empty"), ("p.fa", ">p\nACGT*\n", "non-nucleotide"), ("o.fa", ">o\nHELLO\n", "non-nucleotide")]:
        assert why in " ".join(G.check_sequence(tree, cand_from(tree, name, text))["problems"])
    (tree / "seq/bin.fa").write_bytes(b"\xff\xfe\x00")
    assert "not ASCII" in " ".join(G.check_sequence(tree, {"id": "bin", "source_ref": ref(tree, "seq/bin.fa")})["problems"])


def test_ledger_sequences_are_bound_to_their_artifacts_too(tree):
    p = tree / "ledger/ledger.json"
    L = json.loads(p.read_text())
    L["sequences"][0]["length_nt"] = 11  # the ledger claims a length the artifact does not have
    p.write_text(json.dumps(L))
    led = {"ref": ref(tree, "ledger/ledger.json"), "sequence_ids": ["seq-len"], "entry_ids": []}
    r = compile_(tree, design(tree, claim="proposal", ifs=(), ledger=led, sequence_candidates=[]))
    assert r["candidate_sequence_artifact_refs"] == [] and any("declared length 11" in x for x in r["rejected_sequence_candidates"][0]["problems"])


# ---------------------------------------------------------------------------- finding 3: evidence bound to its measurement
def calibrated(tree, **kw):
    d = design(tree)
    d["interface_evidence"][2] = evidence(tree, "I3", **kw)
    return compile_(tree, d)


def test_bounds_must_be_finite_ordered_and_have_a_quantity_and_unit(tree):
    for kw, why in [({"lo": float("nan")}, "finite numbers"), ({"hi": float("inf")}, "finite numbers"), ({"lo": 3.0, "hi": 1.0}, "lo <= hi"), ({"quantity": ""}, "quantity and unit"), ({"unit": " "}, "quantity and unit"), ({"value": float("nan")}, "finite number")]:
        r = calibrated(tree, **kw)
        assert r["verdict"] == "rejected" and r["interface_state"]["I3"] == "unknown" and any(why in x for x in r["reasons"]), (kw, r["reasons"])


def test_context_quantity_unit_and_artifact_class_are_bound_to_the_pinned_measurement(tree):
    def with_meas(doc):
        d = design(tree)  # evidence() rewrites the default measurement, so the altered artifact is written afterwards and the pin is its own
        doc_path = tree / "meas/I3.json"
        doc_path.write_text(json.dumps(doc))
        d["interface_evidence"][2]["transfer"]["bound_ref"]["sha256"] = sha(doc_path.read_bytes())
        return compile_(tree, d)

    ins = default_inputs("I3")
    r = with_meas(measurement(unit="N", inputs=ins))  # the design says unit 1, the measurement says N
    assert r["verdict"] == "rejected" and any("quantity/unit" in x for x in r["reasons"])
    r = with_meas(measurement(ctx={**CTX, "life_stage": "larva"}, inputs=ins))
    assert any("made in a different context" in x and "life_stage" in x for x in r["reasons"])
    assert any("not a measured experiment" in x for x in with_meas(measurement(evidence_class="model_output", inputs=ins))["reasons"])
    assert any("unsupported source artifact class" in x for x in with_meas({"transfer": {"lo": 0.5, "hi": 2.0}})["reasons"]), "an arbitrary {lo, hi} file"
    assert any("finite ordered" in x for x in with_meas(measurement(lo=2.0, hi=0.5, inputs=ins))["reasons"])


# ---------------------------------------------------------------------------- SPEC-017: versioned validation plans and results
def with_validation(tree, **kw):
    d = design(tree)  # written first: design() writes its own default plan and result files
    plan, res = vplan(tree, **kw)
    d["validation_plans"], d["validation_results"] = [plan], [res]
    return compile_(tree, d)


def test_a_working_claim_needs_a_validation_plan_and_every_required_check_must_pass(tree):
    d = design(tree)
    d["validation_plans"], d["validation_results"] = [], []
    r = compile_(tree, d)
    assert r["verdict"] == "rejected" and any("no validation plan is attached" in x for x in r["reasons"])
    assert with_validation(tree)["verdict"] == "consistent_evidence_for_the_stated_context"


def test_check_statuses_distinguish_missing_not_run_fail_blocked_and_stale(tree):
    def status(**kw):
        r = with_validation(tree, **kw)
        return r["validation"]["plans"][0]["checks"][0], r

    d = design(tree)
    plan, res = vplan(tree)
    d["validation_plans"], d["validation_results"] = [plan], []
    r = compile_(tree, d)
    assert r["validation"]["plans"][0]["checks"][0]["status"] == "missing" and r["verdict"] == "rejected"
    assert status(status="not_run")[0]["status"] == "not_run" and status(status="fail")[0]["status"] == "fail"
    c, r = status(cases={"positive": 0, "negative": 0})
    assert c["status"] == "blocked" and "vacuous pass refused" in c["reason"] and "no evaluable positive case" in c["reason"] and r["function_assurance"]["level"] == "none"
    assert "no meaningful negative case" in status(cases={"positive": 3, "negative": 0})[0]["reason"]
    assert "not shown to be rejected" in status(cases={"positive": 3, "negative": 1, "negative_rejected": False})[0]["reason"]
    c, _ = status(status="not_applicable", check_extra={"endpoint": True}, res_extra={"reason": "not measured in this context"})
    assert c["status"] == "blocked" and "cannot remove a required endpoint" in c["reason"]
    c, _ = status(status="not_applicable", check_extra={"endpoint": False})
    assert c["status"] == "blocked" and "needs a stated reason" in c["reason"]
    c, _ = status(status="not_applicable", check_extra={"endpoint": False}, res_extra={"reason": "no such readout for this layer"})
    assert c["status"] == "not_applicable" and c["reason"] == "no such readout for this layer"
    d = design(tree)
    plan, res = vplan(tree)
    d["validation_plans"], d["validation_results"] = [plan], [res]
    (tree / "meas/res-vp1.json").write_text("the execution record changed")
    r = compile_(tree, d)
    c = r["validation"]["plans"][0]["checks"][0]
    assert c["status"] == "stale" and "stale result" in c["reason"] and r["verdict"] == "rejected"


def test_a_changed_plan_or_version_makes_results_stale_and_a_missing_pin_never_passes(tree):
    d = design(tree)
    plan, res = vplan(tree, version=2)
    res["plan_version"] = 1  # the result is for the previous plan version
    d["validation_plans"], d["validation_results"] = [plan], [res]
    c = compile_(tree, d)["validation"]["plans"][0]["checks"][0]
    assert c["status"] == "stale" and "plan version 1" in c["reason"]
    plan, res = vplan(tree)
    (tree / "meas/plan-vp1.json").write_text("the frozen plan was edited")
    d["validation_plans"], d["validation_results"] = [plan], [res]
    c = compile_(tree, d)["validation"]["plans"][0]["checks"][0]
    assert c["status"] == "stale" and "stale plan" in c["reason"]
    assert G.map_axis_status("pass") == "pass" and G.map_axis_status("unresolved") == "blocked" and G.map_axis_status("fail (retained)") == "fail"
    assert G.map_axis_status("measured, no frozen threshold: not called converged") == "not_run" and G.map_axis_status("something new") == "blocked"


def test_proposal_eligibility_is_separate_from_function_assurance(tree):
    d = design(tree, claim="proposal", ifs=(), sequence_candidates=[seq_candidate(tree, "a.fa", "a")])
    r = compile_(tree, d)
    assert r["proposal_eligibility"]["eligible"] is True and r["function_assurance"]["level"] == "none" and r["function_assurance"]["interfaces_calibrated"] is False
    full = compile_(tree, design(tree))
    assert full["function_assurance"]["level"] == "checks_pass_for_the_stated_context" and "no biological claim follows" in full["scope"]
    bad = compile_(tree, design(tree, claim="proposal", ifs=(), sequence_candidates=[{"id": "u", "sequence": "ACGT"}]))
    assert bad["proposal_eligibility"]["eligible"] is False


# ------------------------------------------------------------------------- SPEC-017: real instrument contract refs
def test_instrument_slots_carry_real_pinned_contract_refs_and_explicit_gaps():
    v = G.validation_slices(GRAPH, {"context": CTX}, None, ROOT)
    ids = {i: [(x["contract_ref"] or {}).get("instrument_id") for x in s["instrument_slots"]] for i, s in v["interfaces"].items()}
    assert "P1-reporter-expression" in ids["I1"] and {"P2-growth-to-EI", "R1-ray-bending"} <= set(ids["I3"]) and {"R2-inflow-tip", "R3-load"} <= set(ids["I4"])
    c = next(x for x in v["interfaces"]["I1"]["instrument_slots"] if x["contract_ref"])["contract_ref"]
    assert c["path"] == G.INSTRUMENT_FILE and c["status"] == "proposed_uncalibrated" and c["sha256"] == json.loads((ROOT / G.INSTRUMENT_MANIFEST).read_text())["files"]["protocol.json"]["sha256"]
    assert any("gap" in x for x in v["interfaces"]["I2"]["instrument_slots"]), "a boundary without a contract says so"
    virt = {x["contract_ref"]["instrument_id"] for x in v["layers"]["shape_mechanics"]["instrument_slots"] if x["kind"] == "virtual" and x["contract_ref"]}
    assert virt == {"V1-saved-deflection-section", "V2-saved-tip-and-slope"} and v["instrument_contracts_ref"]["path"] == G.INSTRUMENT_FILE


def test_stale_or_missing_instrument_contracts_become_gaps_not_hidden_nulls(tmp_path):
    for rel in (G.INSTRUMENT_FILE, G.INSTRUMENT_MANIFEST):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_bytes((ROOT / rel).read_bytes())
    assert G.instrument_contracts(tmp_path)["contracts"]
    (tmp_path / G.INSTRUMENT_FILE).write_text((tmp_path / G.INSTRUMENT_FILE).read_text() + " ")
    stale = G.instrument_contracts(tmp_path)
    assert stale["contracts"] == {} and "changed" in stale["why"]
    v = G.validation_slices(GRAPH, {"context": CTX}, None, tmp_path)
    assert all(x["contract_ref"] is None and "changed" in x["gap"] for s in v["interfaces"].values() for x in s["instrument_slots"])
    assert "no contract exists" in G.instrument_slots({"contracts": {}, "why": None}, ["P1"])[0]["gap"]
