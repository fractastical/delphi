#!/usr/bin/env python3
"""Test of thompson1917-ch11-05: a coiled shell grows without changing its shape.

Pre-registered operationalization (see result.json): within a species, log-log exponents of
the linear conch dimensions on conch diameter across growth stages equal 1 (isometry).

Data
  1. Korn & Walton 2018 (Dryad doi:10.5061/dryad.c17p8): ontogenetic series of conch
     diameter (dm), conch width index CWI = ww/dm, umbilical width index UWI = uw/dm and
     whorl expansion rate WER at every half whorl for 179 Devonian-Jurassic ammonoid species.
  2. Tajika et al. 2017 (Dryad doi:10.5061/dryad.4cb86): Nautilus pompilius, per-specimen
     ontogenetic series of DM, WW, WER, WWI from CT scans (three populations).

Linear dimensions reconstructed from the published indices:
  ww = CWI * dm ;  uw = UWI * dm ;  ah = dm * (1 - WER**-0.5)
(ah is the aperture height, the radial increment over the preceding half whorl, since Korn's
WER = (dm / (dm - ah))^2). The pre-registration named whorl height (wh); the released tables
carry WER instead, so ah, the equivalent radial increment, is used in its place.

Run:  python3 analysis.py            (downloads ~340 KB into ./data/, writes ./derived/)
"""
import hashlib, json, os, re, sys, time, urllib.parse, datetime
import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

FILES = {
    "korn_walton_2018.xlsx": dict(
        file_id=34579,
        sha256="fbe2012f1d420ef7b292141ae0ed0ea8d046c4c15303663565dc72e0727ebe40"),
    "tajika_2017_nautilus.xlsx": dict(
        file_id=75500,
        sha256="db9ee691bc10f3c03ce78340f61c5b6f2fd98f9c3b1a1f3e194b8353aee4bb9f"),
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


def dryad_download(file_id, timeout=180):
    """Dryad fronts file downloads with the Anubis proof-of-work page; complete it like a
    browser (SHA-256 nonce search), then fetch the file."""
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
        r = s.get("https://datadryad.org/.within.website/x/cmd/anubis/api/pass-challenge?" + q,
                  timeout=timeout)
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


def loglog_slope(x, y):
    """OLS slope of log(y) on log(x) over positive, finite pairs; returns (slope, n)."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y) & (x > 0) & (y > 0)
    if ok.sum() < 4:
        return np.nan, int(ok.sum())
    lx, ly = np.log(x[ok]), np.log(y[ok])
    slope = np.polyfit(lx, ly, 1)[0]
    return float(slope), int(ok.sum())


# ---------------------------------------------------------------- ammonoids (Korn & Walton)
def ammonoid_species_table(path, min_dm=None):
    sheets = {s: pd.read_excel(path, sheet_name=s, header=0) for s in ["dm", "CWI", "UWI", "WER"]}
    whorl_cols = [c for c in sheets["dm"].columns if str(c).startswith("Whorl")]
    rows = []
    for i in range(len(sheets["dm"])):
        sp = sheets["dm"].iloc[i]
        dm = sheets["dm"].iloc[i][whorl_cols].astype(float).values
        cwi = sheets["CWI"].iloc[i][whorl_cols].astype(float).values
        uwi = sheets["UWI"].iloc[i][whorl_cols].astype(float).values
        wer = sheets["WER"].iloc[i][whorl_cols].astype(float).values
        assert sheets["CWI"].iloc[i]["Species"] == sp["Species"] == sheets["UWI"].iloc[i]["Species"] == sheets["WER"].iloc[i]["Species"]
        if min_dm is not None:
            keep = dm >= min_dm
            dm, cwi, uwi, wer = dm[keep], cwi[keep], uwi[keep], wer[keep]
        ww = cwi * dm
        uw = uwi * dm
        ah = dm * (1 - wer ** -0.5)
        b_ww, n_ww = loglog_slope(dm, ww)
        b_uw, n_uw = loglog_slope(dm, uw)
        b_ah, n_ah = loglog_slope(dm, ah)
        ok = np.isfinite(dm) & (dm > 0)
        rows.append(dict(species=sp["Species"], family=sp["Family"], period=sp["Period"],
                         n_stages=int(ok.sum()),
                         dm_min=float(np.nanmin(dm)) if ok.any() else np.nan,
                         dm_max=float(np.nanmax(dm)) if ok.any() else np.nan,
                         b_ww=b_ww, n_ww=n_ww, b_uw=b_uw, n_uw=n_uw, b_ah=b_ah, n_ah=n_ah))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- Nautilus (Tajika et al.)
def nautilus_specimen_table(path, min_dm=None):
    rows = []
    for pop in ["Philippines", "Malaysia", "Indonesia"]:
        raw = pd.read_excel(path, sheet_name=f"{pop}_WER_WWI", header=None)
        # specimens are laid out side by side in blocks of 4 columns (DM, WW, WER, WWI) + 1 blank
        c = 0
        while c < raw.shape[1]:
            block = raw.iloc[:, c:c + 4]
            if block.shape[1] < 4 or str(block.iloc[1, 0]).strip() != "DM":
                c += 1
                continue
            spec_id = str(raw.iloc[0, c]).strip()
            vals = block.iloc[2:].apply(pd.to_numeric, errors="coerce")
            vals.columns = ["DM", "WW", "WER", "WWI"]
            vals = vals.dropna(how="all")
            dm = vals["DM"].values; ww = vals["WW"].values; wer = vals["WER"].values
            if min_dm is not None:
                keep = dm >= min_dm
                dm, ww, wer = dm[keep], ww[keep], wer[keep]
            ah = dm * (1 - wer ** -0.5)
            b_ww, n_ww = loglog_slope(dm, ww)
            b_ah, n_ah = loglog_slope(dm, ah)
            rows.append(dict(population=pop, specimen=spec_id, n_stages=int(np.isfinite(dm).sum()),
                             dm_min=float(np.nanmin(dm)), dm_max=float(np.nanmax(dm)),
                             b_ww=b_ww, n_ww=n_ww, b_ah=b_ah, n_ah=n_ah))
            c += 5
    return pd.DataFrame(rows)


def summarize_ammonoids(df):
    d = df.dropna(subset=["b_ww", "b_uw", "b_ah"])
    iso = lambda b: (b >= 0.9) & (b <= 1.1)
    all_iso = iso(d.b_ww) & iso(d.b_uw) & iso(d.b_ah)
    return dict(
        n_species=int(len(d)),
        median_b_ww=round(float(d.b_ww.median()), 3),
        median_b_uw=round(float(d.b_uw.median()), 3),
        median_b_ah=round(float(d.b_ah.median()), 3),
        iqr_b_ww=[round(float(q), 3) for q in d.b_ww.quantile([0.25, 0.75])],
        iqr_b_uw=[round(float(q), 3) for q in d.b_uw.quantile([0.25, 0.75])],
        iqr_b_ah=[round(float(q), 3) for q in d.b_ah.quantile([0.25, 0.75])],
        frac_species_ww_iso=round(float(iso(d.b_ww).mean()), 3),
        frac_species_uw_iso=round(float(iso(d.b_uw).mean()), 3),
        frac_species_ah_iso=round(float(iso(d.b_ah).mean()), 3),
        frac_species_all_three_iso=round(float(all_iso.mean()), 3),
    )


def summarize_nautilus(df):
    d = df.dropna(subset=["b_ww", "b_ah"])
    iso = lambda b: (b >= 0.9) & (b <= 1.1)
    return dict(
        n_specimens=int(len(d)),
        median_b_ww=round(float(d.b_ww.median()), 3),
        median_b_ah=round(float(d.b_ah.median()), 3),
        iqr_b_ww=[round(float(q), 3) for q in d.b_ww.quantile([0.25, 0.75])],
        iqr_b_ah=[round(float(q), 3) for q in d.b_ah.quantile([0.25, 0.75])],
        frac_specimens_both_iso=round(float((iso(d.b_ww) & iso(d.b_ah)).mean()), 3),
        # species-level exponent: pooled OLS across all stage observations of all specimens
    )


def nautilus_pooled(path):
    xs, ws, ahs = [], [], []
    for pop in ["Philippines", "Malaysia", "Indonesia"]:
        raw = pd.read_excel(path, sheet_name=f"{pop}_WER_WWI", header=None)
        c = 0
        while c < raw.shape[1]:
            block = raw.iloc[:, c:c + 4]
            if block.shape[1] < 4 or str(block.iloc[1, 0]).strip() != "DM":
                c += 1; continue
            vals = block.iloc[2:].apply(pd.to_numeric, errors="coerce"); vals.columns = ["DM", "WW", "WER", "WWI"]
            xs.append(vals.DM.values); ws.append(vals.WW.values); ahs.append(vals.DM.values * (1 - vals.WER.values ** -0.5))
            c += 5
    x = np.concatenate(xs); w = np.concatenate(ws); a = np.concatenate(ahs)
    return dict(b_ww_pooled=round(loglog_slope(x, w)[0], 3), n_ww_pooled=loglog_slope(x, w)[1],
                b_ah_pooled=round(loglog_slope(x, a)[0], 3), n_ah_pooled=loglog_slope(x, a)[1])


def main():
    meta = fetch_all()
    korn = os.path.join(DATA, "korn_walton_2018.xlsx")
    naut = os.path.join(DATA, "tajika_2017_nautilus.xlsx")

    amm = ammonoid_species_table(korn)
    amm.to_csv(os.path.join(DERIVED, "ammonoid_species_exponents.csv"), index=False)
    amm2 = ammonoid_species_table(korn, min_dm=2.0)
    nau = nautilus_specimen_table(naut)
    nau.to_csv(os.path.join(DERIVED, "nautilus_specimen_exponents.csv"), index=False)

    out = dict(
        ammonoids_all_stages=summarize_ammonoids(amm),
        ammonoids_dm_ge_2mm=summarize_ammonoids(amm2),
        nautilus_specimens=summarize_nautilus(nau),
        nautilus_pooled=nautilus_pooled(naut),
        files=meta,
    )
    # pre-registered decision
    A = out["ammonoids_all_stages"]
    meds = [A["median_b_ww"], A["median_b_uw"], A["median_b_ah"]]
    pass_a = all(0.9 <= m <= 1.1 for m in meds)
    pass_b = A["frac_species_all_three_iso"] >= 2 / 3
    fail_a = any(m < 0.8 or m > 1.2 for m in meds)
    fail_b = A["frac_species_all_three_iso"] < 0.5
    N = out["nautilus_pooled"]
    naut_pass = all(0.9 <= v <= 1.1 for v in [N["b_ww_pooled"], N["b_ah_pooled"]])
    out["decision"] = {"ammonoid_pass_a_medians_in_0.9_1.1": pass_a,
                       "ammonoid_pass_b_two_thirds_all_iso": pass_b,
                       "ammonoid_fail_a_median_outside_0.8_1.2": fail_a,
                       "ammonoid_fail_b_less_than_half_all_iso": fail_b,
                       "nautilus_pass_pooled_exponents_in_0.9_1.1": naut_pass}
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
