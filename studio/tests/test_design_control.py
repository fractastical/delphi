"""Design-control map: every value is re-read from pinned git blobs, drift and score-like fields are refused,
and the view renders the artifact without inventing a number. Skips (loudly) if the pinned commits are absent."""
import copy
import json
import os

import pytest

from engineering.design_control import build as dc

ART = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "artifacts/design-control/map.json")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _have_sources():
    try:
        for s in dc.SOURCES:
            dc.blob(s)
        return True
    except Exception:
        return False


needs_src = pytest.mark.skipif(not _have_sources(), reason="pinned source commits are not in this clone's object store")


@pytest.fixture()
def amap():
    return json.load(open(ART))


@needs_src
def test_committed_map_matches_pinned_sources(amap):
    assert dc.check(amap) == []


@needs_src
def test_ecology_table_is_the_fixed_endpoint_not_run_end():
    t = {(r["setting"], r["mode"]): r["responses_at_0_6s"] for r in dc.eco_delay_table()}
    # values the ecology owner reports for the same endpoint (messages/ecology-to-codex03.md): baseline 7/8 and 8/8 per
    # neighbor arm, slow 4/5, ablations 1; per two seeds these sum to 15, 16, 9 and 2.
    assert (t[("baseline", "neighbors")], t[("delay-fast", "neighbors")], t[("delay-slow", "neighbors")], t[("baseline", "ablation")]) == (15, 16, 9, 2)


@needs_src
@pytest.mark.parametrize("mutate,needle", [
    (lambda m: m["sources"][0].update(sha256="0" * 64), "blob differs"),
    (lambda m: m["layers"][2]["parameters"][1]["sensitivity"]["elasticity"].update(value=9.0), "value drift"),
    (lambda m: m["layers"][2]["parameters"][1]["sensitivity"]["elasticity"].update(ptr="/paired_sensitivity/nope"), "unresolved"),
    (lambda m: m.update(confidence_percent=87), "forbidden score-like"),
    (lambda m: m["layers"][2]["results"][0].update(plddt_analogue=0.9), "forbidden score-like"),
    (lambda m: m["layers"][3]["parameters"][0]["bound"].update(n={"value": None, "src": "knobs", "ptr": "/knobs/0/fit/n"}), "measured without an n"),
    (lambda m: m["layers"][2]["parameters"][0]["bound"].update(basis=""), "without basis"),
    (lambda m: m["layers"][2]["parameters"][0]["bound"].update(status="validated"), "bound status"),
    (lambda m: m["workpackages"][0].update(inputs=["wp-deformed-polar"]), "cycle"),
    (lambda m: m["workpackages"][5].update(inputs=["wp-ghost"]), "unknown input"),
])
def test_integrity_refuses_each_mutation(amap, mutate, needle):
    bad = copy.deepcopy(amap)
    mutate(bad)
    problems = dc.check(bad)
    assert any(needle in p for p in problems), problems


@needs_src
def test_unmutated_control_is_clean_and_every_failure_above_is_new(amap):
    assert dc.check(copy.deepcopy(amap)) == []


def test_no_probability_or_score_is_non_null(amap):
    assert amap["biological_success_probability"] is None and amap["confidence_percent"] is None and amap["aggregate_score"] is None
    ens = [r for lay in amap["layers"] for r in lay["results"] if "fraction" in r]
    assert len(ens) == 3 and all("not a probability" in r["meaning"] for r in ens)


def test_measured_bounds_are_only_the_fitted_specimen_data(amap):
    kinds = {p["id"]: p["bound"]["status"] for lay in amap["layers"] for p in lay["parameters"]}
    assert {k for k, s in kinds.items() if s == "measured"} == {"pectoral_vs_SL_flying_fish", "pelvic_vs_SL_flying_halfbeak"}


def test_independence_is_declared_from_inputs_only(amap):
    w = {x["id"]: x for x in amap["workpackages"]}
    assert w["wp-deformed-polar"]["inputs"] == ["wp-fin-EI-load", "wp-load-shape"]
    assert all(not x["inputs"] for k, x in w.items() if k != "wp-deformed-polar")
    assert all(x["status"] != "running" for x in w.values())


def _browser():
    pw = pytest.importorskip("playwright.sync_api")
    return pw.sync_playwright()


def _page(tmp_path):
    p = tmp_path / "t.html"
    p.write_text("<!doctype html><meta charset=utf-8><div id=out></div>")
    return p.as_uri()


def _render(tmp_path, data):
    with _browser() as pw:
        b = pw.chromium.launch()
        pg = b.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto(_page(tmp_path))
        pg.add_script_tag(path=os.path.join(ROOT, "site/js/util.js"))
        pg.add_script_tag(path=os.path.join(ROOT, "site/js/design-control.js"))
        pg.evaluate("d => { document.getElementById('out').innerHTML = String(window.DF.designControlPanel(d)); }", data)
        txt, n_layers, chips = pg.evaluate("[document.getElementById('out').innerText, document.querySelectorAll('.dc-layer').length, [...document.querySelectorAll('[data-bound]')].map(e=>e.dataset.bound)]")
        b.close()
    return txt, n_layers, chips, errs


def test_view_renders_artifact_without_invented_values(amap, tmp_path):
    txt, n_layers, chips, errs = _render(tmp_path, amap)
    assert errs == []
    assert n_layers == 6
    assert chips.count("measured") == 2 and "assumed" in chips
    for word in ("NaN", "undefined", "[object"):
        assert word not in txt
    assert "20/64" in txt and "0.3125" in txt and "not a probability" in txt
    assert "Evidence-led science. Goal-driven engineering." in txt
    assert "Independent: no declared input" in txt and "Depends on:" in txt
    assert "Biological success probability: unknown" in txt


def test_view_refuses_bad_schema_and_missing_map(amap, tmp_path):
    bad = dict(amap, schema="frontier.design-control/2")
    txt, n_layers, _, errs = _render(tmp_path, bad)
    assert errs == [] and n_layers == 0 and "Unexpected schema" in txt
    txt, n_layers, _, errs = _render(tmp_path, None)
    assert errs == [] and n_layers == 0 and "No design-control map is present" in txt


def test_pelvic_wording_is_practical_with_interval_and_scoped(amap):
    p = next(q for lay in amap["layers"] for q in lay["parameters"] if q["id"] == "pelvic_vs_SL_flying_halfbeak")
    lo, hi = p["bound"]["b_ci95_bootstrap"]["value"]
    assert lo < 0 < hi and p["bound"]["n"]["value"] == 15
    assert "practical" in p["identifiability_kind"] and "structurally identifiable" in p["identifiability"]
    assert "not identifiable" not in p["identifiability"].lower().replace("not structural", "")
    assert "causal control" in next(q for lay in amap["layers"] for q in lay["parameters"] if q["id"] == "pectoral_vs_SL_flying_fish")["identifiability"]
    pl = next(q for lay in amap["layers"] for q in lay["parameters"] if q["id"] == "EI_multiplier")
    assert "structural" in pl["identifiability_kind"]


def test_fractions_unranked_and_every_param_tagged(amap):
    fr = [r for lay in amap["layers"] for r in lay["results"] if "fraction" in r]
    assert all("unranked" in r["ranking"] and "paired difference is not computed" in r["ranking"] and r["tag"] == "source-only" for r in fr)
    assert all(q.get("tag") for lay in amap["layers"] for q in lay["parameters"])


def test_view_shows_tags_interval_and_unranked(amap, tmp_path):
    txt, _, _, errs = _render(tmp_path, amap)
    assert errs == [] and "source-only" in txt and "computed-here" in txt and "practical/statistical" in txt
    assert "paired difference is not computed" in txt and "b ci95 bootstrap" in txt and "2 seeds" in txt
