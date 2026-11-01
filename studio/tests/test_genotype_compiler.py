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


@pytest.fixture()
def tree(tmp_path):
    (tmp_path / "seq").mkdir()
    (tmp_path / "meas").mkdir()
    (tmp_path / "ledger").mkdir()
    seq = b">candidate\nACGTACGTAC\n"
    (tmp_path / "seq/cand.fa").write_bytes(seq)
    for i in G.INTERFACES:
        (tmp_path / f"meas/{i}.json").write_text(json.dumps({"transfer": {"lo": 0.5, "hi": 2.0}}))
    ledger = {
        "schema": G.LEDGER_SCHEMA,
        "protocol": {"path": "p.json", "sha256": "0" * 64},
        "sequences": [
            {"id": "seq-len", "sequence_sha256": sha(seq), "length_nt": 10, "artifact_ref": {"path": "seq/cand.fa", "sha256": sha(seq)}, "sequence_kind": "natural_reference", "reference": None},
            {"id": "seq-null", "sequence_sha256": None, "length_nt": None, "artifact_ref": None, "sequence_kind": "unknown", "reference": None},
            {"id": "seq-evo", "sequence_sha256": "e" * 64, "length_nt": 100, "artifact_ref": None, "sequence_kind": "existing_model_output", "reference": None},
        ],
        "entries": [
            {
                "id": "e-len",
                "evidence_class": "paper_reported_experiment",
                "species": CTX["species"],
                "tissue": CTX["tissue"],
                "cell_state": CTX["cell_state"],
                "life_stage": CTX["life_stage"],
                "injury_or_condition": CTX["condition"],
                "allele": CTX["allele"],
                "tested_construct_or_promoter_context": CTX["construct_context"],
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


def ref(root, rel):
    return {"path": rel, "sha256": sha((root / rel).read_bytes())}


def evidence(root, i, status="calibrated_transfer", ctx=None, lo=0.5, hi=2.0):
    return {"interface": i, "status": status, "context": ctx or CTX, "transfer": {"quantity": "q", "unit": "1", "lo": lo, "hi": hi, "value_used": 1.0, "bound_ref": {**ref(root, f"meas/{i}.json"), "pointer": "/transfer"}}}


def design(root, claim="working_assembly", ifs=("I1", "I2", "I3", "I4", "I5"), **kw):
    d = {"schema": G.DESIGN_SCHEMA, "id": "d1", "claim": claim, "context": copy.deepcopy(CTX), "interface_evidence": [evidence(root, i) for i in ifs]}
    d.update(kw)
    return d


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
    assert any("outside the measured bound" in x for x in compile_(tree, out)["reasons"])


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
    d = design(tree, claim="proposal", ifs=(), ledger=led, interface_evidence=[{"interface": "I1", "ledger_bridge": "b-supported"}, {"interface": "I3", "ledger_bridge": "b-open"}])
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
    r = compile_(tree, design(tree, claim="proposal", ifs=(), ledger=led))
    assert r["verdict"] == "proposal_only" and any("stale ledger" in x for x in r["reasons"])  # a proposal is not rejected, but the changed ledger is reported and not read
    assert r["ledger_entries_consumed"] == [] and r["candidate_sequence_artifact_refs"] == [] and r["ledger"]["ref"] == led["ref"]
    assert compile_(tree, design(tree, ledger=led))["verdict"] == "rejected"


def test_propagation_invalidates_only_downstream_claims_and_keeps_independent_checks(tree):
    d = design(
        tree,
        claims=[{"id": "c-seq", "depends_on": ["dna", "I1"]}, {"id": "c-expr", "depends_on": ["expression", "I2"]}, {"id": "c-ei", "depends_on": ["I3"]}, {"id": "c-aero", "depends_on": ["I4"]}],
        checked_layers=[{"id": "regulatory-map", "node": "expression"}, {"id": "aero-numerical", "node": "performance"}, {"id": "fin-geometry", "node": "shape_mechanics"}],
    )
    p = G.propagate(GRAPH, d, {"node": "dna"})
    assert p["invalidated_claims"] == ["c-seq", "c-expr", "c-ei", "c-aero"] and p["invalidated_interfaces"] == ["I1", "I2", "I3", "I4", "I5"]
    assert p["retained_checked_layers"] == ["regulatory-map", "aero-numerical", "fin-geometry"], "an upstream sequence change does not touch another node's own numerical check"
    q = G.propagate(GRAPH, d, {"node": "shape_mechanics"})
    assert q["invalidated_interfaces"] == ["I4", "I5"] and q["retained_calibrations"] == ["I1", "I2", "I3"] and q["invalidated_calibrations"] == ["I4", "I5"]
    assert q["retained_claims"] == ["c-seq", "c-expr", "c-ei"] and q["invalidated_claims"] == ["c-aero"]
    assert q["invalidated_checked_layers"] == ["fin-geometry"] and q["retained_checked_layers"] == ["regulatory-map", "aero-numerical"]
    r = G.propagate(GRAPH, d, {"interface": "I3"})
    assert r["invalidated_interfaces"] == ["I3", "I4", "I5"] and r["retained_calibrations"] == ["I1", "I2"] and r["retained_claims"] == ["c-seq", "c-expr"]


def test_generated_graph_artifacts_are_current_and_acceptance_command_passes():
    files = G.build_files(ROOT)
    out = ROOT / "artifacts/biodesign-compiler"
    assert {k: (out / k).read_text() for k in files} == files
    p = subprocess.run([sys.executable, "-m", "engineering.biodesign_compiler.genotype", "--check"], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert p.returncode == 0 and p.stdout.strip() == "PASS"


def test_every_causal_boundary_has_an_exact_input_observation_controls_and_open_instrument_slots():
    v = G.validation_slices(GRAPH, {"context": CTX})
    assert list(v["interfaces"]) == ["I1", "I2", "I3", "I4", "I5"] and v["schema"] == G.VALIDATION_SCHEMA
    for iid, s in v["interfaces"].items():
        assert s["input"] and s["observation"] and len(s["controls"]) >= 2 and s["what_remains_unknown"] and s["recorded_bridges"]
        assert "closes only as calibrated_transfer" in s["decision_rule"] and s["context_required"] == list(G.CONTEXT_FIELDS) and s["context_stated"] == CTX
        assert [x["kind"] for x in s["instrument_slots"]] == ["physical", "virtual"] and all(x["contract_ref"] is None and x["required_fields"] for x in s["instrument_slots"])
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
    d = design(tree, claim="proposal", ifs=(), ledger=led, interface_evidence=[{"interface": "I1", "ledger_bridge": "b-supported"}])
    r = compile_(tree, d)
    v = G.validation_slices(GRAPH, d, r)
    assert v["interfaces"]["I1"]["ledger_readouts"] == [{"entry": "e-len", "falsifiable_validation_readout": "reporter signal after deleting the element", "missing_causal_bridge": "growth and EI"}]
    assert v["interfaces"]["I1"]["state"] == "measured_context" and v["interfaces"]["I3"]["ledger_readouts"] == []


# ---------------------------------------------------------------------------------------------- bidirectional: forward and inverse
def seq_candidate(root, name, cid, **kw):
    (root / "seq" / name).write_bytes(f">{cid}\nACGTACGT{cid}\n".encode())
    c = {"id": cid, "source_ref": ref(root, f"seq/{name}"), "evidence_kind": "measured_expression", "observed_context": copy.deepcopy(CTX), "provenance": {"proposer": "designer-A", "method": "enhancer scan constrained by the ledger", "source_refs": ["ledger:e-len"]}}
    c.update(kw)
    return c


def inv_req(cands, target="shape_mechanics"):
    return {"schema": G.INVERSE_SCHEMA, "id": "r1", "target_node": target, "candidates": cands}


def test_every_interface_carries_forward_and_inverse_directions_and_none_is_invertible_today():
    assert "context-conditioned effect prediction" in G.DIRECTIONS["forward"] and "CANDIDATE SET" in G.DIRECTIONS["inverse"] and "never one guaranteed genome" in G.DIRECTIONS["inverse"]
    for iid, v in GRAPH["interfaces"].items():
        assert v["directions"]["forward"]["label"] == "context-conditioned effect prediction" and v["directions"]["forward"]["state"] == "unknown"
        assert v["directions"]["inverse"]["invertible"] is False and "not a calibrated transfer" in v["directions"]["inverse"]["why"]
        assert v["directions"]["inverse"]["from"] == v["to"] and v["directions"]["inverse"]["to"] == v["from"]
    assert len(GRAPH["inverse_rules"]) == 4


def test_inverse_request_on_the_repository_baseline_is_not_proposable_and_names_the_unresolved_bridges():
    base = {"schema": G.DESIGN_SCHEMA, "id": "b", "context": CTX}
    cand = {"id": "x", "provenance": {"proposer": "p", "method": "m", "source_refs": ["s"]}}
    r = G.compile_inverse(ROOT, GRAPH, inv_req([cand]), base)
    assert r["verdict"] == "not_proposable" and [b["interface"] for b in r["blocked_interfaces"]] == ["I1", "I2", "I3"] and r["candidate_set"] == []
    assert r["single_genome_guaranteed"] is False and r["added_sequences"] == 0
    assert any("fin-stiffness-calibration" in u["bridges"] for u in r["unresolved_bridges"] if u["interface"] == "I3")
    assert r["unscreened_or_failed_candidates"][0]["id"] == "x" and "no pinned source artifact" in r["unscreened_or_failed_candidates"][0]["issues"]
    pinned = {"id": "y", "provenance": cand["provenance"], "source_ref": ref(ROOT, "artifacts/design-control/map.json"), "evidence_kind": "measured_expression"}
    r = G.compile_inverse(ROOT, GRAPH, inv_req([pinned]), base)
    assert r["candidate_set"] == [] and "not screened: an interface on the path is not calibrated" in r["unscreened_or_failed_candidates"][0]["issues"]


def test_a_candidate_set_is_proposed_only_when_every_interface_on_the_path_is_calibrated(tree):
    fwd = design(tree, claim="proposal", ifs=("I1", "I2", "I3"))
    cands = [seq_candidate(tree, "a.fa", "a"), seq_candidate(tree, "b.fa", "b")]
    r = G.compile_inverse(tree, GRAPH, inv_req(cands), fwd)
    assert r["verdict"] == "candidate_set" and [c["id"] for c in r["candidate_set"]] == ["a", "b"] and r["interfaces_crossed"] == ["I1", "I2", "I3"]
    assert r["candidate_set"][0]["provenance"]["method"] == "enhancer scan constrained by the ledger" and r["candidate_set"][0]["forward_check"]["interface_state"] == {"I1": "calibrated_transfer", "I2": "calibrated_transfer", "I3": "calibrated_transfer"}
    assert r["single_genome_guaranteed"] is False and r["added_sequences"] == 0 and r["unresolved_bridges"] == []
    assert [c["sequence"]["path"] for c in r["candidate_set"]] == ["seq/a.fa", "seq/b.fa"], "the compiler returns the candidates it was given, never a sequence of its own"


def test_the_path_to_the_target_decides_what_can_be_inverted(tree):
    fwd = design(tree, claim="proposal", ifs=("I1", "I2"))  # I3 (growth to EI) is not calibrated
    c = [seq_candidate(tree, "a.fa", "a")]
    assert G.compile_inverse(tree, GRAPH, inv_req(c, "growth_material"), fwd)["verdict"] == "candidate_set"
    r = G.compile_inverse(tree, GRAPH, inv_req(c, "shape_mechanics"), fwd)
    assert r["verdict"] == "not_proposable" and [b["interface"] for b in r["blocked_interfaces"]] == ["I3"]


def test_a_measured_context_is_not_enough_to_invert_an_edge(tree):
    fwd = design(tree, claim="proposal", ifs=())
    fwd["interface_evidence"] = [evidence(tree, "I1", status="measured_context")]
    r = G.compile_inverse(tree, GRAPH, inv_req([seq_candidate(tree, "a.fa", "a")], "expression"), fwd)
    assert r["verdict"] == "not_proposable" and r["blocked_interfaces"][0]["state"] == "measured_context"


def test_candidates_need_provenance_a_matching_pinned_sequence_and_are_never_assumed_interchangeable(tree):
    fwd = design(tree, claim="proposal", ifs=("I1", "I2", "I3"))
    good = seq_candidate(tree, "a.fa", "good")
    noprov = seq_candidate(tree, "b.fa", "noprov")
    noprov["provenance"] = {"proposer": "x"}
    stale = seq_candidate(tree, "c.fa", "stale")
    (tree / "seq/c.fa").write_bytes(b"changed after pinning")
    ortho = seq_candidate(tree, "d.fa", "ortholog", ortholog_of={"species": "Danio rerio", "gene": "lepb"}, evidence_kind="homology", observed_context={**CTX, "species": "Hirundichthys speculiger"})
    r = G.compile_inverse(tree, GRAPH, inv_req([good, noprov, stale, ortho]), fwd)
    assert r["verdict"] == "candidate_set" and [c["id"] for c in r["candidate_set"]] == ["good"]
    why = {c["id"]: " ".join(c["issues"]) for c in r["unscreened_or_failed_candidates"]}
    assert "provenance is missing: method, source_refs" in why["noprov"] and "stale sequence reference" in why["stale"] and "not interchangeable across species or contexts" in why["ortholog"]


def test_no_passing_candidate_or_a_bad_request_never_produces_a_genome(tree):
    fwd = design(tree, claim="proposal", ifs=("I1", "I2", "I3"))
    only_bad = seq_candidate(tree, "a.fa", "a")
    only_bad["provenance"] = {}
    r = G.compile_inverse(tree, GRAPH, inv_req([only_bad]), fwd)
    assert r["verdict"] == "no_candidate_passed" and r["candidate_set"] == [] and r["single_genome_guaranteed"] is False
    assert G.compile_inverse(tree, GRAPH, {"schema": "x", "target_node": "nowhere", "candidates": []}, fwd)["verdict"] == "invalid_request"
