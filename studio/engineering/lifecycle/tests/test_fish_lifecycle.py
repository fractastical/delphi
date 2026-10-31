"""Fish lifecycle source/equation layer: quotes are verbatim, formulas are verified, nothing is claimed beyond what was read.

Offline. Quotes from open-licence sources are re-checked against the stored full text; the two sources whose text is not stored (no open licence)
are checked for structure and recorded hashes only.
"""

import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from engineering.lifecycle import diffusion as df  # noqa: E402

D = ROOT / "data" / "fish-lifecycle"
norm = lambda s: re.sub(r"\s+", " ", s).strip()
J = lambda n: json.loads((D / n).read_text())


def stored_text(card):
    root = ET.parse(ROOT / card["full_text_path"]).getroot()
    return norm("".join(root.itertext())), [norm("".join(c.itertext())) for c in root.iter() if c.tag in ("td", "th")]


# ---- quotes ---------------------------------------------------------------------------------


def test_every_quote_from_a_stored_source_is_verbatim_and_short():
    cards = {c["id"]: c for c in J("sources.json")["cards"]}
    seen = 0
    for e in J("equations.json")["equations"]:
        for q in e["quotes"]:
            assert len(q["quote"].split()) <= 25 and q["verified_verbatim"] is True
            c = cards[q["source"]]
            if c["text_in_repo"]:
                text, cells = stored_text(c)
                assert q["quote"] in text or any(q["quote"] in x for x in cells), (e["id"], q["quote"])
                seen += 1
    assert seen >= 20


def test_negative_control_an_altered_quote_is_not_found():
    c = next(c for c in J("sources.json")["cards"] if c["id"] == "konadu2023")
    text, _ = stored_text(c)
    assert "embryos consume 126 ± 4.6 pmol O2 per minute per embryo" in text
    assert "embryos consume 162 ± 4.6 pmol O2 per minute per embryo" not in text


def test_stored_full_texts_match_their_recorded_hashes():
    for c in J("sources.json")["cards"]:
        if c["text_in_repo"]:
            p = ROOT / c["full_text_path"]
            assert hashlib.sha256(p.read_bytes()).hexdigest() == c["full_text_sha256"] and p.stat().st_size == c["full_text_bytes"], c["id"]


def test_texts_without_an_open_licence_are_not_in_the_repo_but_their_hashes_are_recorded():
    cards = {c["id"]: c for c in J("sources.json")["cards"]}
    for sid in ("parichy2009", "mateus2020"):
        assert cards[sid]["text_in_repo"] is False and re.fullmatch(r"[0-9a-f]{64}", cards[sid]["full_text_sha256"])
    stray = [p.name for p in (D / "artifacts").iterdir() if "3030279" in p.name or "7109522" in p.name or "3826579" in p.name]
    assert not stray, stray
    assert any("Loh" in n["citation"] for n in J("sources.json")["not_used"])


def test_every_card_has_a_full_citation_licence_note_and_read_level():
    for c in J("sources.json")["cards"]:
        assert re.search(r"doi:10\.", c["citation"]) and c["read_level"] and "license_note" in c and c["limits"] and c["pmcid"].startswith("PMC")


# ---- formulas, verified symbolically --------------------------------------------------------


def test_sphere_and_slab_solutions_satisfy_the_equation_and_boundary_conditions():
    sp = pytest.importorskip("sympy")
    r, R, D, c0, a = sp.symbols("r R D c0 a", positive=True)
    C = c0 - a / (6 * D) * (R ** 2 - r ** 2)
    assert sp.simplify(D * (1 / r ** 2) * sp.diff(r ** 2 * sp.diff(C, r), r) - a) == 0          # D * spherical Laplacian = a
    assert sp.simplify(C.subs(r, R) - c0) == 0 and sp.diff(C, r).subs(r, 0) == 0                 # C = Co at the edge, dC/dr = 0 at the centre
    rl = sp.sqrt(6 * D * c0 / a)
    assert sp.simplify(C.subs({R: rl, r: 0})) == 0                                               # centre just reaches zero at r_l
    x, L = sp.symbols("x L", positive=True)
    S = c0 - a / (2 * D) * (L ** 2 - x ** 2)
    assert sp.simplify(D * sp.diff(S, x, 2) - a) == 0 and sp.diff(S, x).subs(x, 0) == 0 and sp.simplify(S.subs(x, L) - c0) == 0
    assert sp.simplify(S.subs({L: sp.sqrt(2 * D * c0 / a), x: 0})) == 0


def test_negative_control_a_wrong_closed_form_fails_the_verification():
    sp = pytest.importorskip("sympy")
    r, R, D, c0, a = sp.symbols("r R D c0 a", positive=True)
    C = c0 - a / (6 * D) * (R ** 2 - r ** 2)
    wrong = sp.sqrt(2 * D * c0 / a)                                  # the slab form used for a sphere
    assert sp.simplify(C.subs({R: wrong, r: 0})) != 0


def test_numeric_helpers_agree_with_each_other_and_with_the_papers_stated_limit():
    D, rl = 2e-9, 233e-6
    c = df.c0_over_a_from_sphere_limit(D, rl)
    assert df.sphere_limit_radius(D, c) == pytest.approx(rl, rel=1e-12)
    assert df.slab_limit_thickness(D, c) == pytest.approx(rl / 3 ** 0.5, rel=1e-12)
    assert df.slab_max_total_thickness(D, c) == pytest.approx(2 * rl / 3 ** 0.5, rel=1e-12)
    assert df.sphere_profile(0.0, rl, D, c, 1.0) == pytest.approx(0.0, abs=1e-12)
    assert df.slab_profile(0.0, df.slab_limit_thickness(D, c), D, c, 1.0) == pytest.approx(0.0, abs=1e-12)


def test_the_saved_sizing_check_recomputes_and_carries_its_limits():
    c = J("nutrient_diffusion_check.json")
    D, rl = c["inputs"]["D_m2_per_s"]["value"], c["inputs"]["r_l_m"]["value"]
    cc = df.c0_over_a_from_sphere_limit(D, rl)
    assert c["derived"]["slab_two_sided_total_thickness_um"] == pytest.approx(df.slab_max_total_thickness(D, cc) * 1e6)
    assert c["derived"]["sphere_check_um"] == pytest.approx(233.0)
    for row in c["comparison_with_fish_body_height"]["rows"]:
        assert row["ratio_haa_to_two_sided_slab_limit"] == pytest.approx(round(row["haa_mm"] * 1e-3 / df.slab_max_total_thickness(D, cc), 2))
    assert "SIZING AID" in c["status"] and "not a fish-tissue result" in c["status"] and len(c["not_known"]) >= 4
    assert any("feasible" in x for x in c["claims_not_made"]) and len(c["claims_not_made"]) == 3


# ---- stages, interfaces, assurance ----------------------------------------------------------


def test_stage_json_is_zebrafish_only_orders_milestones_and_keeps_missing_missing():
    s = J("stages.json")
    assert [x["id"] for x in s["stages"]] == ["embryo", "larva", "juvenile", "adult"] and "NOT a flying fish" in s["organism"]
    mil = [x for x in s["stages"] if x["id"] == "larva"][0]["size"]["milestones"]
    assert [m["ssl_mm"] for m in mil] == sorted(m["ssl_mm"] for m in mil) and mil[0]["milestone"] == "pSB"
    assert mil[0]["haa_pre_mm"] is None and mil[-1]["milestone"] == "SA", "a dash in the source is a missing value, not 0 or a string"
    assert s["stages"][2]["size"]["entry"]["ssl_mm"] == 11.0
    assert all(x["locomotion"]["status"] == "unknown" for x in s["stages"])
    assert "flying" not in json.dumps(s["stages"]).lower()


def test_disagreements_between_sources_are_kept_visible():
    s = J("stages.json")
    larva = [x for x in s["stages"] if x["id"] == "larva"][0]
    assert any("disagreement" in i for i in larva["metabolism"]["items"]), "Konadu 'embryo' at 5 dpf versus Parichy's 72 hpf boundary"
    e = {x["id"]: x for x in J("equations.json")["equations"]}
    assert "disagreement" in e["win-scaffold-pore"] and "50-700" in e["win-scaffold-pore"]["disagreement"] and "100-600" in e["win-scaffold-pore"]["disagreement"]
    adult = [x for x in s["stages"] if x["id"] == "adult"][0]
    assert "suspect" in adult["metabolism"]["items"][0]["flag"]


def test_interfaces_cite_known_sources_and_say_what_they_are_not_for():
    ids = {c["id"] for c in J("sources.json")["cards"]}
    for i in J("stages.json")["interfaces"]:
        assert i["evidence"] in J("assurance.json")["statuses"]
        assert any(sid in i["source"] for sid in ids), i["id"]
    assert any("not_for" in i for i in J("stages.json")["interfaces"])


def test_assurance_map_is_complete_in_vocabulary_and_does_not_claim_a_whole_fish_bioprint():
    a = J("assurance.json")
    procs = a["processes"]
    assert len(procs) >= 9
    for name, row in procs.items():
        assert set(row) == set(a["stages"]), name
        for cell in row.values():
            assert cell["status"] in a["statuses"]
    assert all(c["status"] == "unknown" for c in procs["whole_organism_bioprint"].values())
    assert all(c["status"] == "unknown" for c in procs["locomotion"].values())
    assert all(c["status"] == "borrowed_nonfish" for c in procs["nutrient_diffusion_constraint"].values())
    assert any("whole-fish bioprint is feasible" in x for x in a["claims_not_made"]) and any("flying fish" in x for x in a["claims_not_made"]) and len(a["gaps_first"]) >= 6
    assert not [1 for row in procs.values() for c in row.values() if c["status"] == "measured_in_fish" and not c["sources"]], "a measured cell must name its source"


def test_equations_are_labelled_with_what_is_not_established():
    for e in J("equations.json")["equations"]:
        assert e["status"] in J("assurance.json")["statuses"] + ["derived_here_from_stated_setup"], e["id"]
        assert e["quotes"] and e["units"] is not None
    named = {e["id"] for e in J("equations.json")["equations"]}
    assert {"eq-exp-gradient", "eq-diffusion-consumption", "eq-diffusion-limit", "reg-sl-haa", "param-growth-rate"} <= named
    assert J("equations.json")["equations"][2]["status"] == "derived_here_from_stated_setup"


def test_manifest_pins_every_file_and_hashes_match():
    m = J("manifest.json")
    assert m["files"] and "not a flying fish" in m["organism"]
    for f in m["files"]:
        p = ROOT / f["path"]
        assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == f["sha256"] and p.stat().st_size == f["bytes"], f["path"]
    assert {"docs/fish-lifecycle.md", "data/fish-lifecycle/stages.json", "data/fish-lifecycle/assurance.json"} <= {f["path"] for f in m["files"]}


def test_the_doc_states_the_numbers_that_are_in_the_data_and_the_limits():
    doc = (ROOT / "docs" / "fish-lifecycle.md").read_text()
    c = J("nutrient_diffusion_check.json")
    assert f"{c['derived']['slab_two_sided_total_thickness_um']:.0f} um" in doc and "233" in doc and "0.45" in doc and "0.54" in doc and "SL = 3.56 HAA + 4.40" in doc
    for must in ("sizing aid, not a feasibility statement", "Derived here", "unknown at every stage", "not a flying fish", "Not used: Loh"):
        assert must in doc, must
    rest = doc.replace("feasible or infeasible", "").replace("feasibility statement", "").replace("is feasible or infeasible", "")
    assert "feasible" not in rest.replace("infeasible", ""), "feasibility may only appear inside an explicit non-claim"
    assert "feasible" in doc, "the non-claim itself must be stated"


def test_pelvic_abbreviation_is_expanded_and_the_dash_markers_are_missing_values():
    mil = [x for x in J("stages.json")["stages"] if x["id"] == "larva"][0]["size"]["milestones"]
    pb = next(m for m in mil if m["milestone"] == "PB")
    assert "pelvic" in pb["description"] and pb["ssl_mm"] == 7.2
    assert next(m for m in mil if m["milestone"] == "pSB")["sl_p50_mm"] is None
