import importlib.util
import json
import os
import shutil

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "artifacts", "genetic-blueprints")
CACHE = "/data/artifacts/delphi-evolve-rethink/genetic-blueprints-sources"
spec = importlib.util.spec_from_file_location("gb_check", os.path.join(PKG, "check.py"))
gb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gb)


def mutated(tmp_path, fn):
    d = tmp_path / "pkg"
    shutil.copytree(PKG, d)
    b = json.load(open(d / "blueprints.json"))
    fn(b)
    json.dump(b, open(d / "blueprints.json", "w"))
    return gb.check(str(d), repo_root=ROOT)[0]


def test_package_passes_and_reports_a_skipped_cache_check():
    errs, notes = gb.check()
    assert errs == [] and any("SKIPPED" in n for n in notes)


@pytest.mark.skipif(not os.path.isdir(CACHE), reason="source response cache not present on this host")
def test_pinned_hashes_and_every_quote_match_the_cached_responses():
    assert gb.check(cache=CACHE)[0] == []


def test_bac_called_an_autonomous_chromosome_is_refused(tmp_path):
    def f(b):
        d = next(x for x in b["designs"] if x["id"] == "bp-4-bac-carried-locus-reporter")
        d["implementation"]["carrier"] = "a BAC, which acts as an autonomous fish chromosome"
    assert any("NOT an autonomous fish chromosome" in e for e in mutated(tmp_path, f))


def test_citation_read_level_drift_is_refused(tmp_path):
    assert any("read_level" in e for e in mutated(tmp_path, lambda b: b["citation_table"]["bac1"].update(read_level="full-text")))


def test_an_invented_sequence_known_kinetics_or_fish_transfer_is_refused(tmp_path):
    def f(b):
        d = b["designs"][0]
        d["implementation"]["cargo"] = {"enhancer": {"name": "LEN", "source": "tree2016", "coordinates": "chr1:1-2", "sequence": "ACGTACGTACGTACGT"}, "reporter": "GFP"}
        d["expression_kinetics"]["status"] = "measured"
        d["flying_fish_transfer"] = "validated"
    errs = mutated(tmp_path, f)
    assert any("coordinates or sequence are set" in e for e in errs) and any("nucleotide-like" in e for e in errs) and any("expression_kinetics" in e for e in errs) and any("flying_fish_transfer" in e for e in errs)


def test_merged_carrier_delivery_integration_and_hidden_off_target_gap_are_refused(tmp_path):
    def f(b):
        d = b["designs"][0]
        d["implementation"]["delivery"] = d["implementation"]["integration"] = d["implementation"]["carrier"]
        d["off_target_coverage"] = "all tissues covered"
    errs = mutated(tmp_path, f)
    assert any("three distinct" in e for e in errs) and any("off_target_coverage" in e for e in errs)


def test_human_chromosome_source_must_not_be_presented_as_fish_evidence(tmp_path):
    def f(b):
        r = next(x for x in b["comparison"]["rows"] if x["id"] == "autonomous-artificial-chromosome")
        r["evidence"] = "Human artificial chromosomes work and could be used in fish"
    assert any("no fish source" in e for e in mutated(tmp_path, f))


def test_a_named_source_element_with_null_coordinates_is_accepted_and_a_stale_claim_is_refused(tmp_path):
    b = json.load(open(os.path.join(PKG, "blueprints.json")))
    enh = b["designs"][0]["implementation"]["cargo"]["enhancer"]
    assert enh["name"].startswith("LEN") and enh["coordinates"] is None and enh["sequence"] is None
    assert any("stale or contradicted" in e for e in mutated(tmp_path, lambda x: x["global_causal_gaps"].append("every enhancer evidence item here is from regenerating adult fin")))


def test_unvalidated_cell_program_binding_cannot_be_marked_validated(tmp_path):
    def f(b):
        b["designs"][0]["cell_program_binding"]["validation_status"] = "validated"
        b["cell_program_blueprints"][0]["validation_status"] = "validated"
    errs = mutated(tmp_path, f)
    assert any("validation_status must be unknown" in e for e in errs) and any("3 cell-program blueprints" in e for e in errs)
