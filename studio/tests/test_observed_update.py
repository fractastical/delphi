import copy
import json
from pathlib import Path

import numpy as np
import pytest

from engineering.observed_update.model import (
    PredictionCache, StaleModelError, blocked_folds, fit, import_observations, predict,
)
from engineering.observed_update.run import update_demo, validation

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts/observed-allometry"


def observed():
    contract = json.loads((ART / "import-contract.json").read_text())
    return import_observations((ROOT / contract["path"]).read_bytes(), contract)


def test_observed_identity_missingness_and_bad_source_cell_are_preserved():
    rows = observed()
    assert len(rows) == 109 and len({r["id"] for r in rows}) == 109
    assert sum(r["measurements"]["pelvic_cm"] is None for r in rows) == 18
    assert [r["id"] for r in rows if r["source_ratio_mismatches"]] == ["daane2021-s1a-fish-001"]
    first = rows[0]
    assert first["raw_source_cells"]["sheet_pelvic_over_sl"] != first["raw_source_cells"]["recomputed_pelvic_over_sl"]
    assert first["measurements"]["pelvic_cm"] == 6.9


def test_species_and_catalog_groups_never_share_a_catalog_token():
    rows = observed()
    for scheme in ["species", "catalog"]:
        for split in blocked_folds(rows, scheme):
            a = {t for r in split["train"] for t in r["catalog_tokens"]}
            b = {t for r in split["test"] for t in r["catalog_tokens"]}
            assert not a & b
            if scheme == "species":
                assert not {r["species"] for r in split["train"]} & {r["species"] for r in split["test"]}


def test_deliberately_shared_cross_species_catalog_is_purged():
    # Dependence-label mutation fixture only; no scientific observation is changed.
    rows = copy.deepcopy([r for r in observed() if r["group"] == "flying fish"])
    held = next(r for r in rows if r["species"] == "Hirundichthys rondeleti")
    training = next(r for r in rows if r["species"] == "Cheilopogon furcatus")
    training["catalog_tokens"].append(held["catalog_tokens"][0])
    split = next(x for x in blocked_folds(rows, "species") if x["heldout_block"] == held["species"])
    assert training["id"] in split["purged_ids"]
    assert training["id"] not in {r["id"] for r in split["train"]}


def test_heldout_response_mutation_does_not_change_fit_noise_or_band():
    rows = [r for r in observed() if r["group"] == "flying fish"]
    changed = copy.deepcopy(rows)
    for row in changed:
        if row["species"] == "Hirundichthys rondeleti":
            row["measurements"]["pectoral_cm"] *= 100
    cfg = {"model": {"outcomes": ["pectoral_cm"]}}
    def select(folds):
        return next(x for x in folds if x["scheme"] == "species" and x["heldout_block"] == "Hirundichthys rondeleti")
    a, b = select(validation(rows, cfg)), select(validation(changed, cfg))
    assert a["model"] == b["model"]
    assert [x["working_band_cm"] for x in a["heldout"]] == [x["working_band_cm"] for x in b["heldout"]]
    assert a["heldout"][0]["residual_log10"] != b["heldout"][0]["residual_log10"]


def test_analytic_power_law_and_rank_deficiency_controls():
    # Synthetic numerical oracle only; never imported as observed scientific data.
    rows = [{"id": str(i), "species": "oracle", "group": "oracle", "catalog_tokens": [str(i)],
             "measurements": {"sl_cm": float(i), "pectoral_cm": 2 * i**1.5}} for i in range(1, 9)]
    model = fit(rows, "pectoral_cm")
    assert np.allclose(model["coefficients"], [np.log10(2), 1.5], atol=1e-12)
    assert predict(model, 3)["predicted_cm"] == pytest.approx(2 * 3**1.5)
    for row in rows:
        row["measurements"]["sl_cm"] = 1
    assert fit(rows, "pectoral_cm")["failure"] == "rank_deficient"


def test_real_observed_update_refuses_stale_prediction_and_preserves_history():
    result = update_demo(observed(), json.loads((ART / "protocol.json").read_text()))
    assert result["stale_cache_rejected"] and len(result["cache_history"]) == 2
    assert result["before"]["version"] != result["after"]["version"]
    assert len(result["before"]["training_ids"]) == 12 and len(result["after"]["training_ids"]) == 31
    assert result["old_result"]["predicted_cm"] != result["refreshed_result"]["predicted_cm"]
    cache = PredictionCache()
    cache.put(result["query"], result["before"])
    with pytest.raises(StaleModelError):
        cache.get(result["query"], result["after"]["version"])
    wrong = dict(result["query"], unit="m")
    with pytest.raises(ValueError, match="context/unit"):
        cache.put(wrong, result["after"])


def test_modified_observation_source_is_refused():
    contract = json.loads((ART / "import-contract.json").read_text())
    with pytest.raises(ValueError, match="digest"):
        import_observations((ROOT / contract["path"]).read_bytes() + b"\n", contract)


def test_prepared_bundle_is_valid_but_not_database_integration():
    from frontier_adapters.import_cli import load_frozen_bundle

    bundle = load_frozen_bundle(ART / "prepared-bundle-final/bundle.frontier-bundle-0.1.json")
    assert len(bundle["records"]) == 6 and bundle["review_claims"] == []
    evidence = [r for r in bundle["records"] if r["kind"] == "Evidence"]
    assert {r["payload"]["evidence_kind"] for r in evidence} == {"observed", "predicted"}
    assert all(a["availability"] == "referenced" for r in evidence for a in r["payload"]["artifacts"])
    action = next(r for r in bundle["records"] if r["kind"] == "Action")
    assert "not consumed before" in action["payload"]["cache_key"]["scope"]
    manifest = json.loads((ART / "prepared-bundle-final/manifest.json").read_text())
    assert len(manifest["source_commit"]) == 40
    derived = next(r for r in evidence if r["payload"]["evidence_kind"] == "predicted")
    assert "adapter_source_commit" not in derived["payload"]["provenance"]
    assert derived["payload"]["provenance"]["adapter_code_sha256"] == manifest["adapter_code_sha256"]
    assert all(x["ok"] for x in manifest["checks"])
    assert "no DB" in manifest["status"]


def test_transitive_cross_species_catalog_component_is_fully_purged():
    rows = [{"id": name, "species": name, "group": "fixture", "catalog_tokens": tokens}
            for name, tokens in [("held", ["A"]), ("bridge", ["A", "B"]), ("transitive", ["B"]), ("independent", ["C"])]]
    split = next(x for x in blocked_folds(rows, "species") if x["heldout_block"] == "held")
    assert [x["id"] for x in split["train"]] == ["independent"]
    assert set(split["purged_ids"]) == {"bridge", "transitive"}


def test_actual_corrected_outputs_preserve_all_numeric_values_and_no_original_leak(tmp_path):
    from engineering.observed_update.audit import compare

    comparisons, leaks = compare(ART / "run", ART / "run-component-purge-v2-complete", tmp_path / "audit.json")
    assert not leaks and len(comparisons) == 5
    assert all(x["all_scientific_fields_exactly_equal"] for x in comparisons)
    assert any(not x["bytes_equal"] for x in comparisons)


def test_observed_update_purges_transitive_heldout_dependence_fixture():
    rows = copy.deepcopy(observed())
    held = next(r for r in rows if r["species"] == "Hirundichthys rondeleti")
    bridge = next(r for r in rows if r["species"] == "Cheilopogon furcatus")
    tail = next(r for r in rows if r["species"] == "Exocoetus volitans")
    held["catalog_tokens"], bridge["catalog_tokens"], tail["catalog_tokens"] = ["fixture-A"], ["fixture-A", "fixture-B"], ["fixture-B"]
    result = update_demo(rows, json.loads((ART / "protocol.json").read_text()))
    assert bridge["id"] not in result["after"]["training_ids"]
    assert tail["id"] not in result["after"]["training_ids"]


def test_corrected_bundle_pins_separate_producer_result_and_adapter():
    from hashlib import sha256
    from frontier_adapters.import_cli import load_frozen_bundle

    directory = ART / "prepared-bundle-component-purge-v2"
    bundle = load_frozen_bundle(directory / "bundle.frontier-bundle-0.1.json")
    manifest = json.loads((directory / "manifest.json").read_text())
    assert len(bundle["records"]) == 6 and all(x["ok"] for x in manifest["checks"])
    assert manifest["adapter_code_sha256"] == sha256((ROOT / "engineering/observed_update/bundle.py").read_bytes()).hexdigest()
    predicted = next(r for r in bundle["records"] if r["kind"] == "Evidence" and r["payload"]["evidence_kind"] == "predicted")
    pins = predicted["payload"]["provenance"]
    assert pins["producer_code_commit"] != pins["result_snapshot_commit"]
    assert manifest["run_subdir"] == "run-component-purge-v2-complete"
