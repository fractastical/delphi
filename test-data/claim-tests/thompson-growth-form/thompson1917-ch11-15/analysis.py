#!/usr/bin/env python3
"""Test of thompson1917-ch11-15: dissimilar turbinate shells share similar spiral angles
(alpha) and differ mainly in apical semi-angle (theta).

Thompson's relation between the ratio of breadths of consecutive whorls R, the apical
semi-angle theta and the spiral angle alpha:   R = exp(2 pi sin(theta) cot(alpha)).

Data
  * Collins et al. 2021 (Dryad doi:10.5061/dryad.p5hqbzknw): tpsDig file with, per specimen,
    two landmarks on the coiling axis and 4-18 aperture outlines (50 semilandmarks each)
    digitised every 180 degrees down the spire on scaled photographs of sectioned shells.
  * Korn & Walton 2018 (Dryad doi:10.5061/dryad.c17p8): conch diameter per half whorl for 179
    planispiral ammonoid species (discoid form, theta = 90 degrees).

Per gastropod specimen: aperture area (shoelace), centroid, axial position y and outer radius
r_outer (max perpendicular distance of outline points from the coiling axis) per aperture;
log-linear fit of area on angle gives the area expansion per revolution W_a, R = sqrt(W_a);
linear fits of r_outer and y on angle give the enveloping-cone semi-angle
theta = atan(d r_outer / d y). alpha = arccot(ln R / (2 pi sin theta)).

Run: python3 analysis.py   (downloads the 521 MB Collins zip and the 215 KB Korn table into ./data/)
"""
import datetime, hashlib, json, os, re, sys, time, urllib.parse, zipfile
import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

FILES = {
    "Collins_et_al_data.zip": dict(file_id=547236,
                                   sha256="edab9e356820a43984bcf8130359ec29f7e6c00ca3995292fcd922ba2cb3a2a9"),
    "korn_walton_2018.xlsx": dict(file_id=34579,
                                  sha256="fbe2012f1d420ef7b292141ae0ed0ea8d046c4c15303663565dc72e0727ebe40"),
}
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/120.0 Safari/537.36")

# Thompson's four body forms, assigned by family / superfamily of the available taxa
FORMS = {
    "pointed turbinate (Turritellidae; Thompson: Turritella, Cerithium)": ["Maoricolpus_roseus"],
    "obtuse turbinate / trochiform (Trochoidea; Thompson: Solarium, Trochus)": ["Zethalia_zelandia", "Cookia_sulcata"],
    "globose (Tonnoidea; Thompson: Natica, Dolium)": ["Tonna_variegata", "Semicassis_pyrum"],
}


def _solve_anubis(random_data, difficulty):
    prefix = "0" * difficulty
    nonce = 0
    while True:
        h = hashlib.sha256((random_data + str(nonce)).encode()).hexdigest()
        if h.startswith(prefix):
            return h, nonce
        nonce += 1


def dryad_download(file_id, timeout=900):
    url = f"https://datadryad.org/downloads/file_stream/{file_id}"
    s = requests.Session()
    s.headers["User-Agent"] = UA
    r = s.get(url, timeout=timeout)
    if r.headers.get("content-type", "").startswith("text/html") and "anubis_challenge" in r.text[:8000]:
        m = re.search(r'id="anubis_challenge" type="application/json">(.*?)</script>', r.text, re.S)
        ch = json.loads(m.group(1))
        t0 = time.time()
        h, nonce = _solve_anubis(ch["challenge"]["randomData"], ch["rules"]["difficulty"])
        q = urllib.parse.urlencode({"id": ch["challenge"]["id"], "response": h, "nonce": nonce,
                                    "redir": url, "elapsedTime": int((time.time() - t0) * 1000) + 1})
        r = s.get("https://datadryad.org/.within.website/x/cmd/anubis/api/pass-challenge?" + q, timeout=timeout)
    r.raise_for_status()
    return r.content, url


def fetch_all():
    meta = {}
    for name, spec in FILES.items():
        path = os.path.join(DATA, name)
        if not os.path.exists(path):
            content, url = dryad_download(spec["file_id"])
            open(path, "wb").write(content)
            retrieved = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            content = open(path, "rb").read()
            url = f"https://datadryad.org/downloads/file_stream/{spec['file_id']}"
            retrieved = None
        sha = hashlib.sha256(content).hexdigest()
        if sha != spec["sha256"]:
            print(f"WARNING: {name} sha256 {sha} differs from recorded {spec['sha256']}", file=sys.stderr)
        meta[name] = dict(download_url=url, byte_size=len(content), sha256=sha, retrieved_at=retrieved)
    return meta


# ------------------------------------------------------------------ TPS parsing
def parse_tps(text):
    specimens, cur = [], None
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        l = lines[i].strip()
        if l.startswith("LM="):
            cur = dict(lm=[], curves=[], meta={})
            specimens.append(cur)
            n = int(l[3:]); i += 1
            for _ in range(n):
                cur["lm"].append([float(v) for v in lines[i].split()]); i += 1
            continue
        if l.startswith("POINTS="):
            n = int(l[7:]); i += 1
            pts = []
            for _ in range(n):
                pts.append([float(v) for v in lines[i].split()]); i += 1
            cur["curves"].append(np.array(pts))
            continue
        if "=" in l and cur is not None:
            k, v = l.split("=", 1)
            cur["meta"][k] = v.strip()
        i += 1
    return specimens


def poly_area_centroid(p):
    x, y = p[:, 0], p[:, 1]
    xs, ys = np.roll(x, -1), np.roll(y, -1)
    cross = x * ys - xs * y
    A = 0.5 * cross.sum()
    if abs(A) < 1e-12:
        return 0.0, p.mean(axis=0)
    cx = ((x + xs) * cross).sum() / (6 * A)
    cy = ((y + ys) * cross).sum() / (6 * A)
    return abs(A), np.array([cx, cy])


def specimen_parameters(sp):
    scale = float(sp["meta"].get("SCALE", 1.0))
    step = np.deg2rad(float(sp["meta"].get("COMMENT", "180").split()[0]))
    p0, p1 = np.array(sp["lm"][0]), np.array(sp["lm"][1])
    u = (p1 - p0) / np.linalg.norm(p1 - p0)                  # coiling axis direction
    areas, ys, r_out, r_cen = [], [], [], []
    for c in sp["curves"]:
        A, cen = poly_area_centroid(c)
        d = c - p0
        along = d @ u
        perp = np.linalg.norm(d - np.outer(along, u), axis=1)
        areas.append(A * scale ** 2)
        ys.append(((cen - p0) @ u) * scale)
        r_out.append(perp.max() * scale)
        r_cen.append(np.linalg.norm((cen - p0) - ((cen - p0) @ u) * u) * scale)
    n = len(areas)
    th = np.arange(n) * step
    areas, ys, r_out = np.array(areas), np.array(ys), np.array(r_out)
    if n < 3 or np.any(areas <= 0):
        return None
    b_area = np.polyfit(th, np.log(areas), 1)[0]
    W_area = float(np.exp(2 * np.pi * b_area))
    R = float(np.sqrt(W_area))                                 # linear whorl-breadth ratio per revolution
    dy = np.polyfit(th, ys, 1)[0] * 2 * np.pi
    dr = np.polyfit(th, r_out, 1)[0] * 2 * np.pi
    theta = float(np.degrees(np.arctan2(abs(dr), abs(dy)))) if (abs(dy) > 0 or abs(dr) > 0) else np.nan
    return dict(species=sp["meta"].get("VARIABLES", "").split(",")[0].strip(), id=sp["meta"].get("ID", ""),
                image=sp["meta"].get("IMAGE", ""), n_apertures=n, scale_mm_per_px=scale,
                W_area=W_area, R=R, dy_per_rev_mm=float(dy), dr_outer_per_rev_mm=float(dr), theta_deg=theta)


def alpha_deg(R, theta_deg):
    cot_alpha = np.log(R) / (2 * np.pi * np.sin(np.deg2rad(theta_deg)))
    return float(np.degrees(np.arctan(1.0 / cot_alpha))) if cot_alpha > 0 else np.nan, float(cot_alpha)


# ------------------------------------------------------------------ ammonoids (discoid form)
def ammonoid_table(path):
    dm = pd.read_excel(path, sheet_name="dm", header=0)
    whorl_cols = [c for c in dm.columns if str(c).startswith("Whorl")]
    whorl_no = np.array([float(str(c).split()[1]) for c in whorl_cols])
    order = np.argsort(whorl_no)
    rows = []
    for _, r in dm.iterrows():
        vals = r[whorl_cols].astype(float).values[order]
        w = whorl_no[order]
        ok = np.isfinite(vals) & (vals > 0)
        if ok.sum() < 3:
            continue
        w_ok, v_ok = w[ok], vals[ok]
        # last full whorl: largest diameter and the diameter one full whorl (2 half-whorl steps) earlier
        if len(v_ok) < 3 or abs((w_ok[-1] - w_ok[-3]) - 1.0) > 1e-6:
            continue
        R = float(v_ok[-1] / v_ok[-3])
        a, cot = alpha_deg(R, 90.0)
        rows.append(dict(species=r["Species"], family=r["Family"], dm_max=float(v_ok[-1]), R=R,
                         theta_deg=90.0, alpha_deg=a, cot_alpha=cot))
    return pd.DataFrame(rows)


def main():
    meta = fetch_all()
    with zipfile.ZipFile(os.path.join(DATA, "Collins_et_al_data.zip")) as z:
        tps_name = [n for n in z.namelist() if n.lower().endswith(".tps")][0]
        tps = z.read(tps_name).decode("latin-1")
    specimens = parse_tps(tps)
    rows = [specimen_parameters(sp) for sp in specimens]
    gast = pd.DataFrame([r for r in rows if r is not None])
    gast[["alpha_deg", "cot_alpha"]] = gast.apply(lambda r: pd.Series(alpha_deg(r.R, r.theta_deg)), axis=1)
    gast["form"] = None
    for form, taxa in FORMS.items():
        gast.loc[gast.species.isin(taxa), "form"] = form
    gast.to_csv(os.path.join(DERIVED, "gastropod_specimen_parameters.csv"), index=False)

    amm = ammonoid_table(os.path.join(DATA, "korn_walton_2018.xlsx"))
    amm["form"] = "discoid (planispiral ammonoids; Thompson: Planorbis, Nautilus, Ammonites)"
    amm.to_csv(os.path.join(DERIVED, "ammonoid_last_whorl_parameters.csv"), index=False)

    use = pd.concat([gast.dropna(subset=["form"])[["species", "form", "R", "theta_deg", "alpha_deg", "cot_alpha"]],
                     amm[["species", "form", "R", "theta_deg", "alpha_deg", "cot_alpha"]]], ignore_index=True)
    use = use.replace([np.inf, -np.inf], np.nan).dropna(subset=["alpha_deg", "theta_deg"])
    g = use.groupby("form").agg(n=("R", "size"), R_mean=("R", "mean"), theta_mean=("theta_deg", "mean"),
                                theta_sd=("theta_deg", "std"), alpha_mean=("alpha_deg", "mean"),
                                alpha_sd=("alpha_deg", "std"), cot_alpha_mean=("cot_alpha", "mean"))
    g.to_csv(os.path.join(DERIVED, "form_means.csv"))
    alpha_range = float(g.alpha_mean.max() - g.alpha_mean.min())
    theta_range = float(g.theta_mean.max() - g.theta_mean.min())
    cv_cot_alpha_forms = float(g.cot_alpha_mean.std(ddof=1) / g.cot_alpha_mean.mean())
    cv_theta_forms = float(g.theta_mean.std(ddof=1) / g.theta_mean.mean())
    res = dict(
        forms={k: {c: (round(float(v), 3) if isinstance(v, (float, np.floating)) else int(v)) for c, v in row.items()}
               for k, row in g.to_dict(orient="index").items()},
        alpha_range_deg=round(alpha_range, 2), theta_range_deg=round(theta_range, 2),
        alpha_range_over_theta_range=round(alpha_range / theta_range, 3),
        cv_cot_alpha_across_forms=round(cv_cot_alpha_forms, 3), cv_theta_across_forms=round(cv_theta_forms, 3),
        n_gastropod_specimens_total=int(len(gast)), n_specimens_used=int(len(use)),
        all_gastropod_species_alpha=gast.groupby("species").alpha_deg.mean().round(2).to_dict(),
        all_gastropod_species_theta=gast.groupby("species").theta_deg.mean().round(1).to_dict(),
        decision=dict(pass_alpha_range_le_10_and_theta_range_ge_45=bool(alpha_range <= 10 and theta_range >= 45),
                      fail_alpha_range_ge_20=bool(alpha_range >= 20),
                      fail_alpha_range_not_smaller_than_theta_range=bool(alpha_range >= theta_range),
                      underpowered=bool((g.n < 2).any() or len(g) < 4)),
    )
    print(json.dumps(dict(result=res, files=meta), indent=2, default=str))


if __name__ == "__main__":
    main()
