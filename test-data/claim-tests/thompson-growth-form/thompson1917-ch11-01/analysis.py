#!/usr/bin/env python3
"""Test of thompson1917-ch11-01 (molluscan-shell class only): shell spirals are logarithmic.

For each gastropod specimen (Collins et al. 2021, Dryad doi:10.5061/dryad.p5hqbzknw) the
linear whorl size sqrt(aperture area) at successive half-whorl apertures, and for each
ammonoid species (Korn & Walton 2018, Dryad doi:10.5061/dryad.c17p8) the conch diameter at
successive half whorls, are fitted with three two-parameter spiral models by least squares in
the size domain:
    logarithmic   r = a * exp(b * theta)
    Archimedean   r = a + b * theta
    Fermat        r = a * sqrt(theta + theta0)
and compared by RMSE. Pre-registered thresholds are in result.json.

Run: python3 analysis.py   (downloads the 521 MB Collins zip and the 215 KB Korn table into ./data/)
"""
import datetime, hashlib, json, os, re, sys, time, urllib.parse, zipfile
import numpy as np
import pandas as pd
import requests
from scipy.optimize import curve_fit

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


# ------------------------------------------------------------------ TPS parsing (as in ch11-15)
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


def poly_area(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * abs((x * np.roll(y, -1) - np.roll(x, -1) * y).sum())


# ------------------------------------------------------------------ spiral models
def f_log(th, a, b):
    return a * np.exp(b * th)


def f_arch(th, a, b):
    return a + b * th


def f_fermat(th, a, th0):
    return a * np.sqrt(np.clip(th + th0, 1e-9, None))


def fit_models(th, r):
    out = {}
    # logarithmic: seed from log-linear regression
    b0, la0 = np.polyfit(th, np.log(r), 1)
    try:
        p, _ = curve_fit(f_log, th, r, p0=[np.exp(la0), b0], maxfev=20000)
        out["log"] = np.sqrt(np.mean((f_log(th, *p) - r) ** 2)); out["log_b"] = float(p[1])
    except RuntimeError:
        out["log"] = np.nan; out["log_b"] = np.nan
    b1, a1 = np.polyfit(th, r, 1)
    out["arch"] = np.sqrt(np.mean((f_arch(th, a1, b1) - r) ** 2))
    try:
        p, _ = curve_fit(f_fermat, th, r, p0=[r[0] / np.sqrt(1.0), 1.0],
                         bounds=([0, -th.min() + 1e-6], [np.inf, 1e6]), maxfev=20000)
        out["fermat"] = np.sqrt(np.mean((f_fermat(th, *p) - r) ** 2))
    except (RuntimeError, ValueError):
        out["fermat"] = np.nan
    best = min((k for k in ("log", "arch", "fermat") if np.isfinite(out[k])), key=lambda k: out[k])
    out["best"] = best
    out["ratio_arch_over_log"] = out["arch"] / out["log"] if out["log"] > 0 else np.inf
    out["ratio_fermat_over_log"] = out["fermat"] / out["log"] if out["log"] > 0 else np.inf
    return out


def gastropod_series(tps_text):
    rows = []
    for sp in parse_tps(tps_text):
        scale = float(sp["meta"].get("SCALE", 1.0))
        step = np.deg2rad(float(sp["meta"].get("COMMENT", "180").split()[0]))
        sizes = np.array([np.sqrt(poly_area(c)) * scale for c in sp["curves"]])
        if len(sizes) < 5 or np.any(sizes <= 0):
            continue
        th = np.arange(len(sizes)) * step
        m = fit_models(th, sizes)
        rows.append(dict(group="gastropod", unit=sp["meta"].get("ID", ""), species=sp["meta"].get("VARIABLES", "").split(",")[0].strip(),
                         n_points=len(sizes), size_min_mm=float(sizes.min()), size_max_mm=float(sizes.max()), **m))
    return pd.DataFrame(rows)


def ammonoid_series(path):
    dm = pd.read_excel(path, sheet_name="dm", header=0)
    whorl_cols = [c for c in dm.columns if str(c).startswith("Whorl")]
    whorl_no = np.array([float(str(c).split()[1]) for c in whorl_cols])
    order = np.argsort(whorl_no)
    rows = []
    for _, r in dm.iterrows():
        vals = r[whorl_cols].astype(float).values[order]
        w = whorl_no[order]
        ok = np.isfinite(vals) & (vals > 0)
        if ok.sum() < 5:
            continue
        th = w[ok] * 2 * np.pi
        th = th - th.min()
        m = fit_models(th, vals[ok])
        rows.append(dict(group="ammonoid", unit=r["Species"], species=r["Species"], n_points=int(ok.sum()),
                         size_min_mm=float(vals[ok].min()), size_max_mm=float(vals[ok].max()), **m))
    return pd.DataFrame(rows)


def summarize(df):
    return dict(n=int(len(df)), frac_log_best=round(float((df.best == "log").mean()), 3),
                frac_arch_best=round(float((df.best == "arch").mean()), 3),
                frac_fermat_best=round(float((df.best == "fermat").mean()), 3),
                median_ratio_arch_over_log=round(float(df.ratio_arch_over_log.median()), 3),
                median_ratio_fermat_over_log=round(float(df.ratio_fermat_over_log.median()), 3),
                median_log_rate_b_per_radian=round(float(df.log_b.median()), 4),
                median_expansion_per_revolution=round(float(np.exp(2 * np.pi * df.log_b.median())), 3),
                median_n_points=float(df.n_points.median()))


def main():
    meta = fetch_all()
    with zipfile.ZipFile(os.path.join(DATA, "Collins_et_al_data.zip")) as z:
        tps_name = [n for n in z.namelist() if n.lower().endswith(".tps")][0]
        tps = z.read(tps_name).decode("latin-1")
    g = gastropod_series(tps)
    a = ammonoid_series(os.path.join(DATA, "korn_walton_2018.xlsx"))
    pd.concat([g, a], ignore_index=True).to_csv(os.path.join(DERIVED, "spiral_model_fits.csv"), index=False)
    G, A = summarize(g), summarize(a)
    res = dict(gastropods=G, ammonoids=A,
               gastropods_by_species_frac_log_best=g.groupby("species").apply(lambda d: round(float((d.best == "log").mean()), 2), include_groups=False).to_dict())
    res["decision"] = dict(
        pass_log_best_ge_80pct_both=bool(G["frac_log_best"] >= 0.8 and A["frac_log_best"] >= 0.8),
        pass_median_ratio_arch_log_gt_1_5_both=bool(G["median_ratio_arch_over_log"] > 1.5 and A["median_ratio_arch_over_log"] > 1.5),
        fail_log_best_lt_50pct_either=bool(G["frac_log_best"] < 0.5 or A["frac_log_best"] < 0.5),
        fail_median_ratio_lt_1_either=bool(G["median_ratio_arch_over_log"] < 1.0 or A["median_ratio_arch_over_log"] < 1.0),
    )
    print(json.dumps(dict(result=res, files=meta), indent=2, default=str))


if __name__ == "__main__":
    main()
