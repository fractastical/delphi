"""The O2-source diagnostic and the renders: numbers shown come from the stored files, labels are present, the animation is the stored sweep."""
import csv, hashlib, json, re
from pathlib import Path

R = Path(__file__).resolve().parents[2]
V3 = R / "artifacts" / "metabolism" / "basic-nutrients-v3"
J = lambda n: json.loads((V3 / n).read_text())
RM, DG, RES = J("render_manifest.json"), J("o2_source_diagnostic.json"), J("metabolism_results.json")
TABLE = {r["reaction_id"]: r for r in csv.DictReader(open(V3 / "flux_table_pfba_o2_20.csv"))}


def sha(n): return hashlib.sha256((V3 / n).read_bytes()).hexdigest()


def parse(eq):
    def side(s):
        d = {}
        for t in s.split(" + "):
            m = re.match(r"^([0-9.]+) (\S+)$", t.strip()); d[m.group(2) if m else t.strip()] = float(m.group(1)) if m else 1.0
        return d
    l, r = re.split(r"<=>|-->", eq); return side(l), side(r)


def test_the_diagnostic_shows_the_internal_o2_source_by_blocking_it():
    r = {(x["o2_uptake_limit"], x["MAR04071_blocked"]): x for x in DG["results"]}
    assert r[(0, False)]["biomass"] > 0.25 and r[(0, False)]["MAR04071_flux"] == 1000.0 and r[(0, False)]["o2_exchange_flux"] == 0.0
    assert r[(0, True)]["biomass"] < 1e-9 and r[(20, True)]["biomass"] < 0.5 * r[(20, False)]["biomass"] and r[(20, True)]["status"] == "optimal"
    sweep20 = next(s for s in RES["o2_sweep"] if s["o2_uptake_limit"] == 20)["biomass"]
    assert abs(r[(20, False)]["biomass"] - sweep20) < 1e-9, "the unblocked diagnostic condition is the stored sweep point, not a new one"
    assert "not a measurement" in DG["reading"] and "ASSUMED" in DG["reading"]


def test_o2_balance_in_the_stored_table_matches_the_claim():
    """recompute the cytosolic O2 balance from the stored equations and fluxes instead of trusting the caption"""
    net = {}
    for r in TABLE.values():
        f = float(r["flux"]); L, Rr = parse(r["equation"])
        for m, c in L.items():
            if m == "MAM02630c": net[r["reaction_id"]] = net.get(r["reaction_id"], 0) - c * f
        for m, c in Rr.items():
            if m == "MAM02630c": net[r["reaction_id"]] = net.get(r["reaction_id"], 0) + c * f
    assert abs(sum(net.values())) < 1e-6, "cytosolic O2 balances"
    assert net["MAR04071"] == 1000.0 and net["MAR04896"] == 20.0 and net["MAR04071"] > 10 * net["MAR04896"], "internal production dwarfs the uptake"
    left, right = parse(TABLE["MAR04071"]["equation"]); assert "MAM02630c" in right and "MAM02630c" not in left, "at positive flux the reaction makes O2 (it is on the product side)"


def test_every_flux_in_the_network_diagram_equals_the_stored_table():
    assert len(RM["network_fluxes_shown"]) == 14
    for i, v in RM["network_fluxes_shown"].items(): assert v == float(TABLE[i]["flux"]), i
    assert RM["network_fluxes_shown"]["MAR09048"] == -20.0 and RM["network_fluxes_shown"]["MAR06916"] == 1000.0 and RM["arrows"].startswith("schematic")


def test_render_inputs_and_outputs_are_hash_pinned_and_current():
    for k in ("inputs", "outputs"):
        for n, h in RM[k].items(): assert sha(n) == h, n
    assert RM["render_code_sha256"] == hashlib.sha256((R / "engineering" / "metabolism" / "render.py").read_bytes()).hexdigest()


def test_the_animation_is_the_stored_sweep_without_interpolation_and_within_size():
    a = RM["animation"]; p = a["ffprobe"]
    assert a["interpolated"] is False and a["sweep_points"] == len(RES["o2_sweep"]) == 11 and a["bytes"] < 8_000_000
    assert int(p["nb_frames"]) == 11 * a["frames_per_sweep_point"] + 30 and p["r_frame_rate"] == "10/1" and 10 <= float(p["duration"]) <= 20
    assert (V3 / "o2_sweep.mp4").stat().st_size == a["bytes"]
    assert (V3 / "o2_sweep.mp4").read_bytes()[4:8] == b"ftyp"


def test_pngs_are_real_images_and_the_labels_are_declared():
    for n in ("energy_flow_network.png", "o2_atp_sweep_diagram.png", "o2_sweep_poster.png"):
        assert (V3 / n).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n" and (V3 / n).stat().st_size > 20_000, n
    src = (R / "engineering" / "metabolism" / "render.py").read_text()
    for w in RM["labels"]: assert w in RM["banner"] and w in src
    assert src.count("BANNER") >= 3 and "style(fig)" in src, "every figure gets the banner"


def test_render_script_has_no_hand_typed_flux_values_in_the_network():
    src = (R / "engineering" / "metabolism" / "render.py").read_text()
    net = src[src.index("def network"):src.index("def sweep")]
    assert not re.findall(r"flux \+?-?\d", net) and "f(ids[0])" in net, "boxes print fluxes read from the table"
