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
