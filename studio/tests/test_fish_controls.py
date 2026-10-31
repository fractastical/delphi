"""Fish control-knob dataset: observations match the source, fits recompute, Fish 1990 transcription is self-consistent, and nothing is mixed or invented."""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from connectors.fish_controls import fish1990 as F  # noqa: E402

D = ROOT / "data" / "fish-controls"
J = lambda n: json.loads((D / n).read_text())
OBS = list(csv.DictReader(open(D / "daane2021_s1a_observations.csv")))
fl = lambda x: None if x == "" else float(x)


def test_observations_have_the_source_shape_and_missing_cells_stay_empty():
    assert len(OBS) == 109
    counts = {}
    for r in OBS:
        counts[r["group"]] = counts.get(r["group"], 0) + 1
    assert counts == {"flying fish": 49, "flying halfbeak": 19, "halfbeak": 22, "needlefish": 19}
    assert sum(1 for r in OBS if r["pelvic_cm"] == "") == 18 and all(r["sl_cm"] != "" and r["pectoral_cm"] != "" for r in OBS)
    assert not [r for r in OBS if r["pelvic_cm"] in ("0", "0.0", "nan", "None", "NA")], "a missing value must be empty, never a number or a string"
    assert min(fl(r["sl_cm"]) for r in OBS) == 1.68 and max(fl(r["sl_cm"]) for r in OBS) == 53.0


def test_the_corrupt_sheet_cell_is_recorded_and_ratios_are_recomputed_from_lengths():
    mm = J("daane2021_s1a_fits.json")["sheet_ratio_mismatches"]
    assert len(mm) == 1 and mm[0]["fish_no"] == 1 and mm[0]["sheet_value"] < 1e-10 and mm[0]["recomputed"] == pytest.approx(0.3, abs=1e-9)
    for r in OBS:
        if r["pelvic_cm"] != "":
            assert fl(r["recomputed_pelvic_over_sl"]) == pytest.approx(fl(r["pelvic_cm"]) / fl(r["sl_cm"]), rel=1e-12)


def test_every_fit_recomputes_from_the_stored_observations():
    fits = J("daane2021_s1a_fits.json")["fits"]
    assert len(fits) == 8
    for key, f in fits.items():
        g, var = key.split("|")
        pts = [(fl(r["sl_cm"]), fl(r[f"{var}_cm"])) for r in OBS if r["group"] == g and r[f"{var}_cm"] != ""]
        x, y = np.array([p[0] for p in pts]), np.array([p[1] for p in pts])
        b, la = np.polyfit(np.log10(x), np.log10(y), 1)
        assert f["n"] == len(pts) and f["b"] == pytest.approx(b, rel=1e-9) and f["log10_a"] == pytest.approx(la, rel=1e-9), key
        res = np.log10(y) - (la + b * np.log10(x))
        assert abs(res.sum()) < 1e-9, "OLS residuals sum to zero"
        assert f["loocv_rmse_log10"] >= np.sqrt((res ** 2).sum() / len(x)) * 0.99, "leave-one-out error cannot be below the in-sample error"
        assert f["sl_cm_range"] == [x.min(), x.max()] and f["bootstrap"]["seed"] == 20261031


def test_residual_file_matches_the_fits():
    rows = list(csv.DictReader(open(D / "daane2021_s1a_residuals.csv")))
    fits = J("daane2021_s1a_fits.json")["fits"]
    assert len(rows) == sum(f["n"] for f in fits.values())
    for key, f in fits.items():
        g, var = key.split("|")
        e = [float(r["residual_log10"]) for r in rows if r["group"] == g and r["variable"] == var]
        assert len(e) == f["n"] and abs(sum(e)) < 1e-9 and np.sqrt(sum(v * v for v in e) / (f["n"] - 2)) == pytest.approx(f["residual_sd_log10"], rel=1e-9)


def test_weak_fits_are_flagged_by_the_stated_rule():
    knobs = {k["id"]: k for k in J("knobs.json")["knobs"]}
    k = knobs["s1a-pelvic-length-vs-sl-flying-halfbeak"]
    assert k["fit"]["r2"] < 0.05 and k["fit_quality"].startswith("weak")
    for k in knobs.values():
        if k["kind"] == "observed_and_fitted_here":
            ok = k["fit"]["r2"] >= 0.8 and k["fit"]["n"] >= 15
            assert k["fit_quality"].startswith("usable") == ok, k["id"]


# ---- Fish 1990 transcription checks (these catch misread digits) --------------------------------


def test_specimen_counts_sum_to_the_papers_stated_199():
    for dim in F.PREDICTED:
        assert sum(F.TABLE_I[g][dim][0] for g in F.GENERA if dim != "Hypocaudal area") == 199 or dim == "Hypocaudal area"
    assert sum(F.TABLE_I[g]["Length"][0] for g in F.GENERA) == F.SPECIMENS["n"] == 199
    assert [sum(F.TABLE_II[g][0] for g in F.GENERA), sum(F.TABLE_III[g][0] for g in F.GENERA)] == [199, 199]


def test_every_printed_p_mark_agrees_with_whether_the_ci_contains_the_predicted_exponent():
    checked = 0
    for g, dims in F.TABLE_I.items():
        for d, (n, r, a, b, lo, hi, p) in dims.items():
            assert lo < b < hi, (g, d)
            contains = lo <= F.PREDICTED[d] <= hi
            assert (p == "ns") == contains, (g, d, p, lo, hi)
            checked += 1
    for g, (n, mn, mx, r, a, b, lo, hi, p) in F.TABLE_II.items():
        assert lo < b < hi and mn < mx
        assert (p == "ns") == (lo <= 0.33 <= hi), (g, p)
        checked += 1
    assert checked == 30


def test_restored_decimals_give_plausible_sizes_at_0_1_kg():
    for g, dims in F.TABLE_I.items():
        sl = lambda d: float(dims[d][2] if "." in dims[d][2] else "0." + dims[d][2][1:]) * 0.1 ** dims[d][3]
        assert 0.15 < sl("Length") < 0.25, (g, sl("Length"))                       # standard length in m of a 0.1 kg fish
        # span/length 1.03 (Fodiator, short-winged) to 1.55; a restored decimal off by a factor of 10 or a dropped digit falls far outside 0.9-1.7.
        # This is a magnitude check only: it cannot catch a wrong last digit, which is why `a` is documented as decimal-restored, not verified.
        assert 0.9 < sl("Wing span") / sl("Length") < 1.7, (g, sl("Wing span") / sl("Length"))
        assert 0.004 < sl("Wing area") < 0.016, (g, sl("Wing area"))             # m^2
        assert 0.0003 < sl("Hypocaudal area") < 0.003, (g, sl("Hypocaudal area"))


def test_table_ii_and_iii_internal_checks():
    for g, (n, mn, mx, r, a, b, lo, hi, p) in F.TABLE_II.items():
        assert mn <= a * 0.1 ** b * 3 and 0 < r <= 1                              # wing loading at 0.1 kg is of the order of the observed range
    for g, (n, mn, mx, r, sig, a, b, lo, hi) in F.TABLE_III.items():
        assert mn < mx and (lo is None) == (not sig), g                           # CIs are given exactly where r is significant
        if sig:
            assert lo < b < hi, g
    assert F.TABLE_III["Parexocoetus"][5] == 2.648 and F.TABLE_III["Parexocoetus"][6] < 0


def test_raw_data_unavailable_is_stated_on_every_published_knob_and_never_on_an_observed_one():
    knobs = J("knobs.json")["knobs"]
    for k in knobs:
        if k["kind"].startswith("published"):
            assert k["observations"] is None and k["raw_data_unavailable"] and k["source"]["id"] == "fish1990"
        else:
            assert k["observations"]["path"].endswith("observations.csv") and "raw_data_unavailable" not in k and k["source"]["id"] == "daane2021-data-s1"
    assert {"observed_and_fitted_here", "published_fit_only", "published_summary_only"} == {k["kind"] for k in knobs} and len(knobs) == 51


def test_every_knob_has_the_requested_fields_and_a_source_locator():
    for k in J("knobs.json")["knobs"]:
        for f in ("variable", "unit", "observations", "fit", "residuals", "validity_domain", "taxon_context", "source"):
            assert f in k, (k["id"], f)
        assert k["source"]["locator"] and re.fullmatch(r"[0-9a-f]{64}", k["source"]["sha256"]) and k["validity_domain"]
        if k["kind"] == "observed_and_fitted_here":
            assert k["residuals"]["path"].endswith("residuals.csv") and k["validity_domain"]["sl_cm"][0] < k["validity_domain"]["sl_cm"][1]


def test_validity_domains_equal_the_data_and_no_cross_source_conversion_is_made():
    for k in J("knobs.json")["knobs"]:
        if k["kind"] == "observed_and_fitted_here":
            f = k["observations"]["filter"]["group"]
            col = k["observations"]["column"]
            v = [fl(r["sl_cm"]) for r in OBS if r["group"] == f and r[col] != ""]
            assert k["validity_domain"]["sl_cm"] == [min(v), max(v)] and k["observations"]["n_nonmissing"] == len(v)
    d = J("knobs.json")
    assert "No conversion" in d["no_cross_source_conversion"] and len(d["inconsistencies_in_fish1990"]) == 2


def test_sources_pin_hashes_and_nothing_is_stored_that_should_not_be():
    s = {x["id"]: x for x in J("sources.json")["sources"]}
    assert s["daane2021-data-s1"]["sha256"] == "1ac98650f493036218837d235ed4451ff096d926fa50b797dcea4fc7fca52279" and s["fish1990"]["sha256"] == "1efed334ed4aa48ec8e23801ff0b420d1d5c21430100a6d86d0b3e569421f8ea"
    assert s["daane2021-data-s1"]["stored_in_repo"] is False and s["fish1990"]["stored_in_repo"] is False
    assert "NOT read" in s["daane2021-data-s1"]["license"]["article_record"] and "unresolved" in s["daane2021-data-s1"]["redistribution"]
    stray = [p for p in ROOT.rglob("*") if p.suffix in (".xlsx", ".pdf") and ".git" not in p.parts and "node_modules" not in p.parts]
    assert not stray, stray


def test_manifest_hashes_match_files():
    m = J("manifest.json")
    assert len(m["files"]) >= 6
    for f in m["files"]:
        p = ROOT / f["path"]
        assert hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"], f["path"]


def test_no_credential_patterns_in_the_dataset_or_code():
    pat = re.compile("|".join(["X-" + "Amz-", "AK" + "IA[0-9A-Z]{12,}", "Signa" + "ture=", "Creden" + "tial="]), re.I)
    for base in ("data/fish-controls", "connectors/fish_controls"):
        for p in (ROOT / base).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                assert not pat.search(p.read_text(errors="ignore")), p
