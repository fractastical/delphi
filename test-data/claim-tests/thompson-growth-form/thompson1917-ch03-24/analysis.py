#!/usr/bin/env python3
"""thompson1917-ch03-24: a regular ~150-yr period in Arizona ponderosa ring widths, 1390-1910?

Fetches ITRDB standard chronologies az572 (Flagstaff) and az547 (Walnut Canyon), runs a periodogram
test against an AR(1) red-noise null and Douglass-style century smoothing. Writes derived/measured.json,
derived/files.json and derived/series.csv.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)
BASE = "https://www.ncei.noaa.gov/pub/data/paleo/treering/chronologies/northamerica/usa/{f}"
SITES = {"az572": (1390, 1910), "az547": (1420, 1910)}
N_SURR = 5000
RNG = np.random.default_rng(20261031)
BAND = (120.0, 200.0)
TARGET = (130.0, 170.0)
SMOOTH = 101


def fetch(url, dest):
    if not os.path.exists(dest):
        r = requests.get(url, timeout=120, headers={"User-Agent": "delphi-claim-tests/1.0"})
        r.raise_for_status()
        open(dest, "wb").write(r.content)
    h = hashlib.sha256(open(dest, "rb").read()).hexdigest()
    return {"download_url": url, "retrieved_at": datetime.fromtimestamp(os.path.getmtime(dest), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "byte_size": os.path.getsize(dest), "sha256": h}


def read_crn(path):
    """Tucson .crn: 6-char id, 4-char decade year, then 10 x (4-char index, 3-char sample depth); 9990 = missing."""
    years, idx, depth = [], [], []
    for line in open(path, encoding="latin-1"):
        if len(line) < 20 or not line[6:10].strip().isdigit():
            continue
        if line[6:10].strip() == "" or line[7:10] in (" 1 ", " 2 ", " 3 "):
            continue
        try:
            y0 = int(line[6:10])
        except ValueError:
            continue
        body = line[10:].rstrip("\n")
        for k in range(10):
            chunk = body[7 * k: 7 * k + 7]
            if len(chunk) < 4 or chunk[:4].strip() == "":
                continue
            try:
                v = int(chunk[:4])
                d = int(chunk[4:7]) if chunk[4:7].strip() else 0
            except ValueError:
                continue
            if v == 9990:
                continue
            years.append(y0 + k)
            idx.append(v / 1000.0)
            depth.append(d)
    s = pd.Series(idx, index=years, name="index").sort_index()
    s = s[~s.index.duplicated(keep="first")]
    return s, pd.Series(depth, index=years).sort_index()


def ar1_surrogates(x, n):
    x = x - x.mean()
    r1 = float(np.corrcoef(x[:-1], x[1:])[0, 1])
    var = float(np.var(x, ddof=1))
    sig = np.sqrt(var * (1 - r1 ** 2))
    N = len(x)
    out = np.empty((n, N))
    e = RNG.normal(0, sig, size=(n, N + 100))
    for i in range(n):
        z = np.empty(N + 100)
        z[0] = e[i, 0] / np.sqrt(1 - r1 ** 2)
        for t in range(1, N + 100):
            z[t] = r1 * z[t - 1] + e[i, t]
        out[i] = z[100:]
    return out, r1


def periodogram(x):
    x = x - x.mean()
    N = len(x)
    f = np.fft.rfftfreq(N, d=1.0)[1:]
    p = (np.abs(np.fft.rfft(x)) ** 2)[1:] * 2.0 / N
    return f, p


def spectral_test(x):
    f, p = periodogram(x)
    per = 1.0 / f
    surr, r1 = ar1_surrogates(x, N_SURR)
    ps = np.array([periodogram(s)[1] for s in surr])
    q95 = np.percentile(ps, 95, axis=0)
    q99 = np.percentile(ps, 99, axis=0)
    band = (per >= BAND[0]) & (per <= BAND[1])
    i = np.where(band)[0][np.argmax(p[band])]
    # Band-wise (max-over-band) null, correcting for picking the band maximum
    band_max_null = np.percentile(ps[:, band].max(axis=1), 95)
    # Top-5 peaks anywhere, periods > 10 yr
    long = per > 10
    order = np.argsort(p[long])[::-1][:5]
    top = [{"period_yr": float(per[long][k]), "power": float(p[long][k]), "ratio_to_ar1_q95": float(p[long][k] / q95[long][k])} for k in order]
    return {
        "lag1_autocorrelation": r1,
        "peak_period_in_120_200_band_yr": float(per[i]),
        "peak_power": float(p[i]),
        "ar1_q95_at_peak": float(q95[i]),
        "ar1_q99_at_peak": float(q99[i]),
        "peak_exceeds_pointwise_q95": bool(p[i] > q95[i]),
        "peak_exceeds_bandmax_q95": bool(p[i] > band_max_null),
        "peak_period_in_130_170": bool(TARGET[0] <= per[i] <= TARGET[1]),
        "band_periods_yr": [float(v) for v in per[band]],
        "band_power": [float(v) for v in p[band]],
        "band_ar1_q95": [float(v) for v in q95[band]],
        "top5_peaks_gt10yr": top,
    }


def smoothed_maxima(series, window, lo, hi):
    sm = series.rolling(window, center=True).mean().dropna()
    sm = sm[(sm.index >= lo) & (sm.index <= hi)]
    v = sm.values
    yrs = sm.index.values
    maxima = []
    minima = []
    for t in range(1, len(v) - 1):
        if v[t] >= v[t - 1] and v[t] > v[t + 1]:
            maxima.append(int(yrs[t]))
        if v[t] <= v[t - 1] and v[t] < v[t + 1]:
            minima.append(int(yrs[t]))

    def thin(points):
        kept = []
        for y in points:
            if kept and y - kept[-1] < 50:
                # keep the more extreme of the pair
                a, b = sm.loc[kept[-1]], sm.loc[y]
                if (b > a) == (points is maxima):
                    kept[-1] = y
            else:
                kept.append(y)
        return kept

    maxima, minima = thin(maxima), thin(minima)
    intervals = [int(b - a) for a, b in zip(maxima[:-1], maxima[1:])]
    return sm, {"window_yr": window, "maxima_years": maxima, "minima_years": minima, "intervals_between_maxima_yr": intervals,
                "n_intervals": len(intervals), "all_intervals_in_125_175": bool(len(intervals) >= 2 and all(125 <= d <= 175 for d in intervals)),
                "mean_interval_yr": float(np.mean(intervals)) if intervals else None,
                "smoothed_amplitude_sd": float(np.std(v, ddof=1))}


def analyse(site, series, depth, lo, hi):
    x = series[(series.index >= lo) & (series.index <= hi)]
    full_cov = (x.index.min() == lo) and (x.index.max() == hi) and (len(x) == hi - lo + 1)
    out = {"window": [lo, hi], "n_years": int(len(x)), "complete_coverage": bool(full_cov),
           "mean_sample_depth_in_window": float(depth[(depth.index >= lo) & (depth.index <= hi)].mean()),
           "min_sample_depth_in_window": int(depth[(depth.index >= lo) & (depth.index <= hi)].min()),
           "series_start": int(series.index.min()), "series_end": int(series.index.max())}
    out["spectral"] = spectral_test(x.values)
    sm101, out["smoothed_101"] = smoothed_maxima(series, SMOOTH, lo, hi)
    sm51, out["smoothed_51_sensitivity"] = smoothed_maxima(series, 51, lo, hi)
    t1 = out["spectral"]["peak_exceeds_pointwise_q95"] and out["spectral"]["peak_period_in_130_170"]
    t2 = out["smoothed_101"]["all_intervals_in_125_175"]
    out["test1_spectral_pass"] = bool(t1)
    out["test2_smoothed_regular_pass"] = bool(t2)
    return out, x, sm101


def main():
    files = []
    results = {}
    cols = {}
    for site, (lo, hi) in SITES.items():
        dest = os.path.join(DATA, f"{site}.crn")
        files.append(fetch(BASE.format(f=f"{site}.crn"), dest))
        s, d = read_crn(dest)
        results[site], x, sm = analyse(site, s, d, lo, hi)
        cols[f"{site}_index"] = x
        cols[f"{site}_smoothed101"] = sm
    pd.DataFrame(cols).to_csv(os.path.join(DERIVED, "series.csv"), index_label="year")
    p = results["az572"]
    rep = results["az547"]
    if p["test1_spectral_pass"] and p["test2_smoothed_regular_pass"]:
        verdict = "mixed" if not (rep["test1_spectral_pass"] or rep["test2_smoothed_regular_pass"]) else "supports"
    elif not p["test1_spectral_pass"] and not p["test2_smoothed_regular_pass"]:
        verdict = "refutes"
    else:
        verdict = "mixed"
    out = {"sites": results, "n_surrogates": N_SURR, "verdict_by_prereg_rule": verdict}
    json.dump(out, open(os.path.join(DERIVED, "measured.json"), "w"), indent=2)
    json.dump(files, open(os.path.join(DERIVED, "files.json"), "w"), indent=2)
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
