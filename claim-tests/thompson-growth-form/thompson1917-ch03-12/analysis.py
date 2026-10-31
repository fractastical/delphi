#!/usr/bin/env python3
"""Test of thompson1917-ch03-12: human growth in length has its velocity maximum about the
fifth month of intra-uterine life.

Pre-registered bracketing test (see result.json):
  (a) INTERGROWTH-21st fetal crown-rump length (CRL) 50th centile, 9+0 to 14+0 weeks:
      velocity still increasing at 13-14 weeks relative to 9-10 weeks.
  (b) INTERGROWTH-21st newborn crown-heel length 50th centile by gestational age at birth,
      24+0 to 42+6 weeks (sexes averaged): velocity at 24-28 weeks exceeds 36-40 weeks and the
      24-40 velocity series trends downward.
  Secondary: gestational age of maximum velocity of the INTERGROWTH-21st fetal femur-length
  median equation (14-40 weeks).

Data are the INTERGROWTH-21st published tables / equations as redistributed in the rOpenSci
`gigs` R package (GitHub, commit fb58fe6, GPL-3). Run: python3 analysis.py
"""
import datetime, hashlib, json, os, re, sys
import numpy as np
import pandas as pd
import requests

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
DERIVED = os.path.join(HERE, "derived")
os.makedirs(DATA, exist_ok=True)
os.makedirs(DERIVED, exist_ok=True)

COMMIT = "fb58fe6596d4b289d5362c5efe00f882984d3186"
RAW = f"https://raw.githubusercontent.com/ropensci/gigs/{COMMIT}/"
FILES = {
    "ig_fet_crlfga_centiles.txt": ("data-raw/tables/ig_fet/ig_fet_crlfga_centiles.txt",
                                   "93af76b58e280c2511b8653a9845c55d9278d29e962ec7100e08155c328d37e4"),
    "ig_nbs_len_female_percentiles.csv": ("data-raw/tables/ig_nbs/ig_nbs_len_female_percentiles.csv",
                                          "a2ce9801720415d15f5e3fc917727fa13641cb71bf166c353003ebfab16624b7"),
    "ig_nbs_len_male_percentiles.csv": ("data-raw/tables/ig_nbs/ig_nbs_len_male_percentiles.csv",
                                        "53c9c5663c7594b7ffdfbcdc8cd00f166fd7b8070f71e1bf80ae90ce52864ba4"),
    "ig_fet.R": ("R/ig_fet.R", "2335ba623ef76b140db8526df93505a52555d42f6a69993cffa788a6d54be2b2"),
}


def fetch_all():
    meta = {}
    for name, (path, sha_expected) in FILES.items():
        local = os.path.join(DATA, name)
        url = RAW + path
        if not os.path.exists(local):
            r = requests.get(url, timeout=120)
            r.raise_for_status()
            open(local, "wb").write(r.content)
            retrieved = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        else:
            retrieved = None
        content = open(local, "rb").read()
        sha = hashlib.sha256(content).hexdigest()
        if sha != sha_expected:
            print(f"WARNING: {name} sha256 {sha} != recorded {sha_expected}", file=sys.stderr)
        meta[name] = dict(download_url=url, byte_size=len(content), sha256=sha, retrieved_at=retrieved)
    return meta


def ga_weeks(s):
    w, d = str(s).split("+")
    return int(w) + int(d) / 7.0


def crl_velocity():
    df = pd.read_csv(os.path.join(DATA, "ig_fet_crlfga_centiles.txt"), sep=r"\s+")
    df["ga"] = df["gest_wks"].map(ga_weeks)
    df = df[(df.ga >= 9.0) & (df.ga <= 14.0)].reset_index(drop=True)   # standard's stated range
    ga = df.ga.values; y = df.P50.values                                # CRL in mm, daily rows
    v = np.gradient(y, ga)                                              # mm per week
    out = pd.DataFrame(dict(ga_weeks=ga, crl_p50_mm=y, velocity_mm_per_week=v))
    out.to_csv(os.path.join(DERIVED, "crl_p50_velocity.csv"), index=False)
    v_9_10 = float(v[(ga >= 9) & (ga < 11)].mean())
    v_13_14 = float(v[(ga >= 13) & (ga <= 14)].mean())
    acc = np.gradient(v, ga)
    return dict(n_rows=int(len(df)), ga_range=[float(ga.min()), float(ga.max())],
                velocity_wk9_10=round(v_9_10, 2), velocity_wk13_14=round(v_13_14, 2),
                still_accelerating_at_14wk=bool(v_13_14 > v_9_10),
                mean_acceleration_mm_per_wk2=round(float(acc.mean()), 3))


def chl_velocity():
    cols = ["gest_days", "P03", "P05", "P10", "P50", "P90", "P95", "P97"]
    frames = []
    for sex in ["female", "male"]:
        d = pd.read_csv(os.path.join(DATA, f"ig_nbs_len_{sex}_percentiles.csv"), sep=r"\s+", header=None, names=cols,
                        encoding="utf-8-sig")
        d["ga"] = d["gest_days"].map(ga_weeks)
        frames.append(d.set_index("ga")["P50"].rename(sex))
    both = pd.concat(frames, axis=1)
    both["P50_mean_cm"] = both.mean(axis=1)
    ga = both.index.values.astype(float); y = both["P50_mean_cm"].values * 10.0   # mm, daily rows
    v = np.gradient(y, ga)
    out = pd.DataFrame(dict(ga_weeks=ga, length_p50_female_cm=both["female"].values,
                            length_p50_male_cm=both["male"].values, velocity_mm_per_week=v))
    out.to_csv(os.path.join(DERIVED, "newborn_length_p50_velocity.csv"), index=False)
    # weekly means smooth the step-like daily table
    wk = pd.DataFrame(dict(ga=np.floor(ga).astype(int), v=v)).groupby("ga").v.mean()
    v_24_28 = float(wk.loc[24:27].mean()); v_36_40 = float(wk.loc[36:39].mean())
    sel = wk.loc[24:39]
    slope = float(np.polyfit(sel.index.values.astype(float), sel.values, 1)[0])
    return dict(n_rows=int(len(both)), ga_range=[float(ga.min()), float(ga.max())],
                velocity_wk24_28=round(v_24_28, 2), velocity_wk36_40=round(v_36_40, 2),
                trend_slope_mm_per_wk2_24_40=round(slope, 3),
                decelerating_from_24wk=bool(v_24_28 > v_36_40 and slope < 0),
                weekly_velocity=[(int(k), round(float(x), 2)) for k, x in wk.items()])


def femur_peak():
    src = open(os.path.join(DATA, "ig_fet.R"), encoding="utf-8").read()
    m = re.search(r"flfga = list\(\s*mu = ([-\d.]+) \+ ([\d.]+) \* ga_wks - ([\d.]+) \* ga_wks\^2", src)
    a, b, c = map(float, m.groups())
    ga = np.arange(14.0, 40.0 + 1e-9, 1 / 7)
    mu = a + b * ga - c * ga ** 2
    v = b - 2 * c * ga                                 # analytic derivative, mm/week
    return dict(coefficients=dict(a=a, b=b, c=c), ga_of_max_velocity=float(ga[np.argmax(v)]),
                velocity_at_14wk=round(float(v[0]), 2), velocity_at_40wk=round(float(v[-1]), 2),
                velocity_monotonic_decreasing=bool(np.all(np.diff(v) < 0)),
                fl_mm_at_14_and_40=[round(float(mu[0]), 1), round(float(mu[-1]), 1)])


def main():
    meta = fetch_all()
    crl = crl_velocity(); chl = chl_velocity(); fl = femur_peak()
    pass_a = crl["still_accelerating_at_14wk"]
    pass_b = chl["decelerating_from_24wk"]
    fl_ok = fl["ga_of_max_velocity"] <= 24.0
    out = dict(crl_first_trimester=crl, newborn_crown_heel_length=chl, femur_length_secondary=fl,
               decision=dict(pass_a_crl_still_accelerating_at_14wk=pass_a,
                             pass_b_chl_decelerating_24_to_40wk=pass_b,
                             peak_bracketed_in_14_24_weeks=bool(pass_a and pass_b),
                             femur_peak_not_later_than_24wk=fl_ok),
               files=meta)
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
