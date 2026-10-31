"""Artifact-consistency tests for the Zebrafish-GEM FBA slice. They read the stored results; the model file is not in the repo."""
import hashlib, json
from pathlib import Path

R = Path(__file__).resolve().parents[2]
A = R / "artifacts" / "metabolism"
J = lambda p: json.loads((A / p).read_text())
V1, V2, V3 = J("metabolism_results.json"), J("basic-nutrients-v2/metabolism_results.json"), J("basic-nutrients-v3/metabolism_results.json")
SHA = "3424f584f3f48711d79a0a5af475e0ad0413af10c93345a7bb76e53874a1e217"


def test_model_is_pinned_measured_and_not_stored():
    m = V3["model"]
    assert m["sha256"] == SHA and m["commit"] == "846f0b7b34701801b2f5e15f549807d2e71ffa62"
    assert (m["reactions"], m["metabolites"], m["genes"], m["exchanges"]) == (12833, 8435, 2709, 1658)
    assert m["default_exchange_bounds"] == [[-1000.0, 1000.0]], "the file defines no medium"
    assert not [p for p in R.rglob("*.xml") if ".git" not in p.parts and (p.name.startswith("Zebrafish-GEM") or p.stat().st_size == 35687914)]
    assert J("manifest.json")["model"]["sha256"] == SHA


def test_controls_behave_and_balance():
    for V in (V1, V3):
        c = V["controls"]
        assert c["B_all_uptake_closed"]["objective"] < 1e-9 and c["C_glucose_only"]["objective"] < 1e-9
        assert c["F_objective_validity"] == {"objective_ids": ["MAR00021"], "biomass_flux_equals_objective": True}
        for k, v in c.items():
            if "max_abs_Sv" in v: assert v["max_abs_Sv"] < 1e-9 and v["status"] == "optimal" and v["bounds_ok"], k
    assert V3["controls"]["G_unrestricted_minimal_medium_is_degenerate"]["uses_ATP_uptake"] is True


def test_default_all_open_run_is_not_called_a_medium():
    assert V3["controls"]["A_source_default_all_exchanges_open"]["objective"] > 4
    assert "ASSUMED" in V3["assumed_medium"]["basis"] and "not a published" in V3["assumed_medium"]["basis"]
    assert V3["assumed_medium"]["allowlist_names_without_an_exchange"] == [] and "ASSUMED" in V3["units"]


def test_v2_zero_growth_is_kept_and_v3_grows():
    assert max(s["biomass"] for s in V2["o2_sweep"]) < 1e-9
    assert min(s["biomass"] for s in V3["o2_sweep"]) > 0.2


def test_o2_sweep_is_monotone_and_status_optimal():
    s = V3["o2_sweep"]; b = [x["biomass"] for x in s]
    assert [x["o2_uptake_limit"] for x in s] == sorted(x["o2_uptake_limit"] for x in s)
    assert all(b[i] <= b[i + 1] + 1e-9 for i in range(len(b) - 1)) and all(x["status"] == "optimal" for x in s)
    assert all(x["o2_flux"] <= x["o2_uptake_limit"] + 1e-6 for x in s)


def test_atp_tradeoff_is_monotone_decreasing():
    for lim in (20, 0):
        b = [x["biomass"] for x in V3["atp_tradeoff"] if x["o2_uptake_limit"] == lim]
        assert len(b) == 8 and all(b[i] >= b[i + 1] - 1e-9 for i in range(7)) and b[0] > b[-1]


def test_egc_negative_and_pfba_balance():
    e = J("basic-nutrients-v3/egc_test.json"); assert e["energy_generating_cycle_found"] is False
    p = J("basic-nutrients-v3/pfba_summary.json"); assert p["max_abs_Sv"] < 1e-8 and abs(p["biomass"] - V3["controls"]["E_baseline_o2_20"]["objective"]) < 1e-6


def test_the_diagnosis_names_the_blocker_and_docs_keep_the_limits():
    d = J("basic-nutrients-v2/precursor_diagnosis.json")
    assert [x["name"] for x in d["blocked_pool_inputs"] if not x["max_sink_flux"] or x["max_sink_flux"] < 1e-9] == ["vitamin E derivatives"]
    t = (R / "docs" / "metabolism.md").read_text()
    for w in ("not** time-dynamic", "not** fin-", "uptake-uncapped", "Assumed, not published"): assert w in t, w


def test_manifest_hashes_match():
    m = J("manifest.json")
    for f in m["files"] + m["code"]:
        assert hashlib.sha256((R / f["path"]).read_bytes()).hexdigest() == f["sha256"], f["path"]
