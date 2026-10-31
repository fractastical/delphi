"""Test of thompson1917-ch16-13: do aquatic mammals lack the tall 'withers' and 'haunch' neural spines?

Run `python3 fetch.py` first (downloads ~2 MB into data/). Then `python3 analysis.py` writes
derived/*.csv and prints the JSON that fills `measured` in result.json.

Test A: Figueirido et al. 2021 (Dryad 10.5061/dryad.3j9kd51ft), 3D landmarks on every presacral
vertebra of 44 carnivoran species, including two pinnipeds (Phoca vitulina, Otaria byronia).
Test B: Gillet et al. 2019 (Dryad 10.5061/dryad.7dj6850), calliper measurements on thoracic,
lumbar and caudal vertebrae of 204 cetacean specimens (73 species).
"""
import json
import os
import re
import zipfile
from itertools import combinations

import numpy as np
import pandas as pd
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DERIVED, exist_ok=True)

PINNIPEDS = {"Phoca_vitulina", "Otaria_byronia"}
# Habitually swimming non-pinnipeds; excluded from the terrestrial reference set (sensitivity run keeps them).
SEMI_AQUATIC = {"Lutra_lutra", "Aonyx_cinerea", "Mustela_vison"}

# 0-based landmark indices (Figueirido et al. 2021, Supplementary Table 2).
# Thoracic: 1-2 cranial spinous process, 3 cranial neural-canal midpoint, 12-15 cranial body, 18-19 caudal spinous process.
# Lumbar:   1-2 cranial spinous process, 3 cranial neural-canal midpoint, 12-15 cranial body, 20-21 caudal spinous process.
LM = {
    "T": {"spinous": [0, 1, 17, 18], "canal": 2, "body": [11, 12, 13, 14]},
    "L": {"spinous": [0, 1, 19, 20], "canal": 2, "body": [11, 12, 13, 14]},
}


def read_landmark_file(path):
    """Parse an IDAV Landmark export: [names] block then [rawpoints] block of 'name + k rows of xyz."""
    text = open(path, encoding="utf-8", errors="replace").read().splitlines()
    n_lm = int(text[text.index("[landmarks]") + 1])
    start = text.index("[rawpoints]") + 1
    out = {}
    i = start
    while i < len(text):
        line = text[i].strip()
        if line.startswith("'"):
            name = line[1:]
            pts = []
            j = i + 1
            while len(pts) < n_lm:
                row = text[j].strip()
                if row:
                    pts.append([float(v) for v in row.split()])
                j += 1
            out[name] = np.array(pts)
            i = j
        else:
            i += 1
    return out


def parse_name(name):
    name = name.replace(" ", "")  # 'Vulpes _vulpes _150_T01' is the only irregular label
    m = re.match(r"^([A-Z][a-z]+_[a-z]+)(?:_(.+?))?_([TL])(\d{2})$", name)
    if not m:
        raise ValueError(name)
    species, specimen, region, num = m.groups()
    if species == "Felis_concolor":  # thoracics are labelled Felis_concolor, lumbars Puma_concolor: one species
        species = "Puma_concolor"
    return species, specimen or "", region, int(num)


def vertebra_metrics(pts, region):
    lm = LM[region]
    body = pts[lm["body"]]
    body_centroid = body.mean(axis=0)
    hc = max(np.linalg.norm(a - b) for a, b in combinations(body, 2))
    spin = pts[lm["spinous"]]
    d_body = np.linalg.norm(spin - body_centroid, axis=1)
    apex = spin[int(np.argmax(d_body))]
    s_body = float(d_body.max())
    s_canal = float(np.linalg.norm(apex - pts[lm["canal"]]))
    return {"S_body": s_body, "S_canal": s_canal, "Hc": float(hc), "h": s_body / hc, "h_canal": s_canal / hc}


def test_a():
    inner = os.path.join(DATA, "figueirido2021", "inner")
    if not os.path.isdir(inner):
        with zipfile.ZipFile(os.path.join(DATA, "figueirido2021", "Data.zip")) as z:
            z.extractall(inner)
    rows = []
    for fname, region in [("Thoracic_Complete-1.txt", "T"), ("Lumbar_Complete-1.txt", "L")]:
        for name, pts in read_landmark_file(os.path.join(inner, fname)).items():
            species, specimen, reg, num = parse_name(name)
            assert reg == region
            m = vertebra_metrics(pts, region)
            rows.append({"species": species, "specimen": specimen, "region": region, "num": num, "name": name, **m})
    vert = pd.DataFrame(rows)
    vert.round(4).to_csv(os.path.join(DERIVED, "carnivora_vertebra_relative_spine_height.csv"), index=False)

    # specimen-level then species-level indices
    def indices(g):
        t = g[g.region == "T"].set_index("num").sort_index()
        l = g[g.region == "L"].set_index("num").sort_index()
        w = t.loc[t.index.isin([1, 2, 3, 4]), "h"].mean()
        p = t.loc[t.index.isin([10, 11, 12, 13]), "h"].mean()
        last3 = l.index[-3:] if len(l) else []
        haunch = l.loc[last3, "h"].mean() if len(last3) else np.nan
        return pd.Series({"W": w, "P": p, "WI": w / p, "Haunch": haunch, "HI": haunch / p,
                          "nT": len(t), "nL": len(l), "h_max_T": t["h"].max(),
                          "T_of_max": int(t["h"].idxmax()) if len(t) else np.nan})

    spec = vert.groupby(["species", "specimen"]).apply(indices, include_groups=False).reset_index()
    spec.round(4).to_csv(os.path.join(DERIVED, "carnivora_specimen_indices.csv"), index=False)
    sp = spec.groupby("species")[["W", "P", "WI", "Haunch", "HI", "h_max_T"]].mean()
    sp["n_specimens"] = spec.groupby("species").size()
    sp["group"] = ["pinniped" if s in PINNIPEDS else ("semi-aquatic" if s in SEMI_AQUATIC else "terrestrial") for s in sp.index]
    sp = sp.sort_values(["group", "W"])
    sp.round(4).to_csv(os.path.join(DERIVED, "carnivora_species_indices.csv"))

    terr = sp[sp.group == "terrestrial"]
    terr_all = sp[sp.group != "pinniped"]
    pin = sp[sp.group == "pinniped"]
    res = {"n_species": int(len(sp)), "n_terrestrial": int(len(terr)), "n_pinniped": int(len(pin)),
           "n_vertebrae": int(len(vert)),
           "pinniped": {s: {k: round(float(v), 3) for k, v in pin.loc[s, ["W", "P", "WI", "Haunch", "HI"]].items()} for s in pin.index}}
    for col in ["W", "WI", "HI"]:
        q = terr[col].quantile([0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]).round(3).to_dict()
        u = stats.mannwhitneyu(pin[col].dropna(), terr[col].dropna(), alternative="less", method="exact")
        u_all = stats.mannwhitneyu(pin[col].dropna(), terr_all[col].dropna(), alternative="less", method="exact")
        res[col] = {"terrestrial_quantiles": {str(k): v for k, v in q.items()},
                    "pinniped_values": pin[col].round(3).to_dict(),
                    "mwu_p_less": round(float(u.pvalue), 4),
                    "mwu_p_less_incl_semiaquatic": round(float(u_all.pvalue), 4)}
    res["supports_component"] = bool((pin["W"] < terr["W"].quantile(0.25)).all()
                                     and res["W"]["mwu_p_less"] < 0.05 and res["WI"]["mwu_p_less"] < 0.05)
    res["refutes_component"] = bool((pin["W"] >= terr["W"].median()).any())
    res["terrestrial_WI_min"] = round(float(terr["WI"].min()), 3)
    res["terrestrial_WI_median"] = round(float(terr["WI"].median()), 3)
    res["terrestrial_species_with_WI_le_1"] = terr.index[terr["WI"] <= 1].tolist()
    return res, terr


def test_b(terr):
    path = os.path.join(DATA, "gillet2019", "Vertebral_shape.xlsx")
    xl = pd.ExcelFile(path)
    rows = []
    for sheet in xl.sheet_names:
        df = pd.read_excel(xl, sheet, header=None)
        label = str(df.iloc[0, 0])
        species = re.sub(r"_\(.*$", "", label)
        cols = df.iloc[0, 1:].tolist()
        body = df.iloc[1:].copy()
        body.columns = ["vertebra"] + cols
        body = body[body["vertebra"].astype(str).str.match(r"^(T|L|Ca)\d+$")]
        for _, r in body.iterrows():
            lnp, hc = pd.to_numeric(r["Neural_spine_height"], errors="coerce"), pd.to_numeric(r["Centrum_height"], errors="coerce")
            rows.append({"species": species, "specimen": label, "vertebra": r["vertebra"],
                         "region": re.match(r"^[A-Za-z]+", r["vertebra"]).group(0),
                         "num": int(re.search(r"\d+", r["vertebra"]).group(0)),
                         "Lnp": lnp, "Hc": hc, "h": lnp / hc if (pd.notna(lnp) and pd.notna(hc) and hc > 0) else np.nan})
    vert = pd.DataFrame(rows)
    # 8.7k rows (~800 KB): too large for derived/, so it is written next to the raw data instead.
    vert.round(4).to_csv(os.path.join(DATA, "cetacea_vertebra_relative_spine_height.csv"), index=False)

    def indices(g):
        t = g[(g.region == "T") & g.h.notna()].set_index("num").sort_index()
        l = g[(g.region == "L") & g.h.notna()].set_index("num").sort_index()
        if len(t) < 6:
            return pd.Series({"W": np.nan, "P": np.nan, "WI": np.nan, "Lum": np.nan, "nT": len(t)})
        w = t["h"].iloc[:3].mean()
        p = t["h"].iloc[-3:].mean()
        return pd.Series({"W": w, "P": p, "WI": w / p, "Lum": l["h"].mean() if len(l) else np.nan,
                          "nT": len(t), "T_of_max": int(t["h"].idxmax())})

    spec = vert.groupby(["species", "specimen"]).apply(indices, include_groups=False).reset_index().dropna(subset=["WI"])
    sp = spec.groupby("species")[["W", "P", "WI", "Lum"]].mean()
    sp["n_specimens"] = spec.groupby("species").size()
    sp.sort_values("WI").round(4).to_csv(os.path.join(DERIVED, "cetacea_species_indices.csv"))
    terr_min, terr_med = float(terr["WI"].min()), float(terr["WI"].median())
    frac_below_min = float((sp["WI"] < terr_min).mean())
    frac_ge_median = float((sp["WI"] >= terr_med).mean())
    res = {"n_specimens": int(len(spec)), "n_species": int(len(sp)), "n_vertebrae": int(vert.h.notna().sum()),
           "WI_median": round(float(sp["WI"].median()), 3),
           "WI_quantiles": {str(k): round(float(v), 3) for k, v in sp["WI"].quantile([0, 0.1, 0.25, 0.5, 0.75, 0.9, 1]).items()},
           "WI_max_species": sp["WI"].idxmax(), "WI_max": round(float(sp["WI"].max()), 3),
           "fraction_species_WI_below_terrestrial_min": round(frac_below_min, 3),
           "fraction_species_WI_ge_terrestrial_median": round(frac_ge_median, 3),
           "fraction_specimens_spine_max_in_first3_thoracics": round(float((spec["T_of_max"] <= 3).mean()), 3),
           "W_median": round(float(sp["W"].median()), 3), "P_median": round(float(sp["P"].median()), 3)}
    res["supports_component"] = bool(sp["WI"].median() <= 1 and frac_below_min >= 0.8)
    res["refutes_component"] = bool(frac_ge_median >= 0.2)
    return res


def main():
    a, terr = test_a()
    b = test_b(terr)
    if a["supports_component"] and b["supports_component"]:
        verdict = "supports"
    elif a["refutes_component"] or b["refutes_component"]:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out = {"test_A_carnivora": a, "test_B_cetacea": b, "verdict_by_preregistered_rule": verdict}
    json.dump(out, open(os.path.join(DERIVED, "summary.json"), "w"), indent=1, default=str)
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
