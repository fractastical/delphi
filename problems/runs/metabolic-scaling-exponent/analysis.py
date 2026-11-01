#!/usr/bin/env python3
"""Pre-registered PGLS model comparison of mammalian basal metabolic scaling (see PREREG.md).

Usage:  python3 fetch.py && python3 analysis.py [--fast]
Writes derived/summary.json (all numbers quoted in RESULTS.md and result.json) and small tables.
--fast skips the 1,000-replicate bootstrap (uses 100) for quick checks; the committed summary used no flag.
"""
import csv, json, os, sys, time
import numpy as np
from scipy import stats

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pgls

DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "derived")
os.makedirs(OUT, exist_ok=True)
SEED = 20261101
NBOOT = 100 if "--fast" in sys.argv else 1000
KB = 8.617333262e-5  # eV/K

# ---- pre-registered thresholds ------------------------------------------------------------------
D_AICC = 10.0      # AICc gap needed for curvature / clade models
D_CURV = 0.05      # |slope(q95) - slope(q05)|
P_LRT = 0.01
R_SPREAD = 0.10
MIN_ORDER = 10
ROBUST_TREES = 95
B23, B34 = 2.0 / 3.0, 0.75


# ---- data ---------------------------------------------------------------------------------------
def key_of(label):
    p = label.split("_")
    return "_".join(p[:2]) if p[0] else "_" + p[1]


def load_tree_mcc(name="upham_NDexp_MCC.tre"):
    txt = open(os.path.join(DATA, name)).read()
    return read_one_nexus(txt)


def read_one_nexus(txt):
    import re
    translate = {}
    m = re.search(r"translate(.*?);", txt, flags=re.S | re.I)
    if m:
        for part in m.group(1).split(","):
            kv = part.split()
            if len(kv) == 2:
                translate[kv[0]] = kv[1]
    tm = re.search(r"^\s*tree\s+[^=]*=\s*(.*?;)", txt[(m.end() if m else 0):], flags=re.S | re.I | re.M)
    return pgls.parse_newick(tm.group(1), translate or None)


def tipkeys(tree):
    return {key_of(l): l for l in tree.leaf}


def load_pantheria(mass_col="5-2_BasalMetRateMass_g", tree=None):
    tree = tree or load_tree_mcc()
    tk = tipkeys(tree)
    rows = list(csv.reader(open(os.path.join(DATA, "PanTHERIA_1-0_WR05_Aug2008.txt"), encoding="latin-1"), delimiter="\t"))
    h = rows[0]
    ib, im = h.index("18-1_BasalMetRate_mLO2hr"), h.index(mass_col)
    recs = []
    for r in rows[1:]:
        B, M = float(r[ib]), float(r[im])
        if B > 0 and M > 0:
            key = r[4].replace(" ", "_")
            recs.append(dict(key=key, order=r[0].strip(), family=r[1].strip(), B=B, M=M, tip=tk.get(key)))
    n_all = len(recs)
    recs = [r for r in recs if r["tip"]]
    recs = _dedupe(recs)
    return _frame(recs, n_all)


def _dedupe(recs):
    by = {}
    for r in recs:
        by.setdefault(r["key"], []).append(r)
    out = []
    for k, rs in by.items():
        r = dict(rs[0])
        r["B"] = float(np.exp(np.mean([np.log(x["B"]) for x in rs])))
        r["M"] = float(np.exp(np.mean([np.log(x["M"]) for x in rs])))
        out.append(r)
    return out


def _frame(recs, n_all=None):
    recs = sorted(recs, key=lambda r: r["key"])
    d = {k: [r[k] for r in recs] for k in recs[0]} if recs else {}
    d = {k: (np.array(v) if k in ("B", "M") else v) for k, v in d.items()}
    d["y"], d["x"] = np.log10(d["B"]), np.log10(d["M"])
    d["n"], d["n_before_tree_match"] = len(recs), n_all
    return d


def subset(d, mask):
    mask = np.asarray(mask)
    out = {}
    for k, v in d.items():
        if isinstance(v, np.ndarray) and v.shape == mask.shape:
            out[k] = v[mask]
        elif isinstance(v, list) and len(v) == len(mask):
            out[k] = [a for a, m in zip(v, mask) if m]
        else:
            out[k] = v
    out["n"] = int(mask.sum())
    return out


def load_anage():
    rows = list(csv.reader(open(os.path.join(DATA, "anage_data.txt"), encoding="latin-1"), delimiter="\t"))
    h = rows[0]
    g = lambda r, n: r[h.index(n)].strip()
    out = []
    for r in rows[1:]:
        if len(r) != len(h):
            continue
        if not (g(r, "Metabolic rate (W)") and g(r, "Body mass (g)")):
            continue
        out.append(dict(key=f"{g(r, 'Genus')}_{g(r, 'Species')}", cls=g(r, "Class"), order=g(r, "Order").upper(),
                        family=g(r, "Family").upper(), W=float(g(r, "Metabolic rate (W)")), M=float(g(r, "Body mass (g)")),
                        T=float(g(r, "Temperature (K)")) if g(r, "Temperature (K)") else None,
                        quality=g(r, "Data quality"), origin=g(r, "Specimen origin")))
    return out


def anage_frame(tree, cls="Mammalia", quality_ok=("acceptable", "high", "low"), origin=None, exclude_keys=None):
    tk = tipkeys(tree)
    rs = [r for r in load_anage() if r["cls"] == cls and r["W"] > 0 and r["M"] > 0 and r["quality"] in quality_ok]
    if origin:
        rs = [r for r in rs if r["origin"] == origin]
    if exclude_keys is not None:
        rs = [r for r in rs if r["key"] not in exclude_keys]
    n_all = len(rs)
    by = {}
    for r in rs:
        by.setdefault(r["key"], []).append(r)
    recs = []
    for k, grp in by.items():
        if k not in tk:
            continue
        Ts = [x["T"] for x in grp if x["T"]]
        recs.append(dict(key=k, order=grp[0]["order"], family=grp[0]["family"], tip=tk[k],
                         B=float(np.exp(np.mean([np.log(x["W"]) for x in grp]))),
                         M=float(np.exp(np.mean([np.log(x["M"]) for x in grp]))),
                         T=float(np.mean(Ts)) if Ts else float("nan")))
    return _frame(recs, n_all)


# ---- models -------------------------------------------------------------------------------------
def groups_for(order):
    from collections import Counter
    c = Counter(order)
    return [o if c[o] >= MIN_ORDER else "OTHER" for o in order]


def design_m3(x, grp, interaction=True):
    levels = sorted(set(grp))
    cols = [np.array([g == L for g in grp], float) for L in levels]
    X = np.column_stack(cols + ([c * x for c in cols] if interaction else [x]))
    return X, levels


def classify(L, U):
    if L > B23 and L <= B34 <= U:
        return "3/4"
    if U < B34 and L <= B23 <= U:
        return "2/3"
    if (L <= B23 <= U) and (L <= B34 <= U):
        return "underdetermined"
    if not (L <= B23 <= U) and not (L <= B34 <= U):
        return "neither"
    return "other"  # e.g. interval contains 3/4 and 2/3 excluded below / contains 2/3 and excludes 3/4 above (covered above)


def decide(d, C, lam=None, extra=False):
    """Run M1, fixed slopes, M2, M3a/b on one dataset and tree covariance. Returns metrics + classification."""
    y, x, n = d["y"], d["x"], d["n"]
    X1 = np.column_stack([np.ones(n), x])
    f1 = pgls.fit_pgls(y, X1, C, lam)
    L1, U1 = pgls.ci_t(f1, 1)
    f23 = pgls.fit_pgls(y - B23 * x, np.ones((n, 1)), C, lam)
    f34 = pgls.fit_pgls(y - B34 * x, np.ones((n, 1)), C, lam)
    xc = x - x.mean()
    f2 = pgls.fit_pgls(y, np.column_stack([np.ones(n), xc, xc ** 2]), C, lam)
    q05, q95 = np.quantile(x, [0.05, 0.95])
    s = lambda q: f2["beta"][1] + 2 * f2["beta"][2] * (q - x.mean())
    D = abs(s(q95) - s(q05))
    grp = groups_for(d["order"])
    Xa, lev = design_m3(x, grp, True)
    Xb, _ = design_m3(x, grp, False)
    f3a = pgls.fit_pgls(y, Xa, C, lam)
    f3b = pgls.fit_pgls(y, Xb, C, lam)
    G = len(lev)
    lrt = 2 * (f3a["ll"] - f3b["ll"])
    p_lrt = float(stats.chi2.sf(max(lrt, 0), G - 1))
    from collections import Counter
    cnt = Counter(grp)
    slopes = {L: float(f3a["beta"][G + i]) for i, L in enumerate(lev)}
    big = [v for L, v in slopes.items() if L != "OTHER" and cnt[L] >= MIN_ORDER]
    R = (max(big) - min(big)) if len(big) > 1 else float("nan")
    d_curve = f1["aicc"] - f2["aicc"]
    d_clade = f1["aicc"] - f3a["aicc"]
    curve_wins = bool(d_curve > D_AICC and D >= D_CURV)
    clade_wins = bool(d_clade > D_AICC and p_lrt < P_LRT and R >= R_SPREAD)
    cls1 = classify(L1, U1)
    classification = "heterogeneous" if (curve_wins or clade_wins) else cls1
    res = dict(
        n=n, M1=dict(b=float(f1["beta"][1]), se=float(f1["se"][1]), ci95=[float(L1), float(U1)], a=float(f1["beta"][0]),
                     lam=f1["lam"], ll=f1["ll"], aicc=f1["aicc"], bic=f1["bic"], class_M1=cls1),
        fixed23=dict(aicc=f23["aicc"], daicc_vs_M1=f23["aicc"] - f1["aicc"], bic=f23["bic"], lam=f23["lam"]),
        fixed34=dict(aicc=f34["aicc"], daicc_vs_M1=f34["aicc"] - f1["aicc"], bic=f34["bic"], lam=f34["lam"]),
        M2=dict(b1=float(f2["beta"][1]), b2=float(f2["beta"][2]), b2_se=float(f2["se"][2]),
                b2_ci95=[float(x_) for x_ in pgls.ci_t(f2, 2)], aicc=f2["aicc"], bic=f2["bic"], lam=f2["lam"],
                slope_q05=float(s(q05)), slope_q95=float(s(q95)), D=float(D), daicc_M1_minus_M2=float(d_curve),
                dbic_M1_minus_M2=float(f1["bic"] - f2["bic"]), q05_mass_g=float(10 ** q05), q95_mass_g=float(10 ** q95)),
        M3=dict(groups=lev, group_n={L: cnt[L] for L in lev}, slopes=slopes, R=float(R), aicc_M3a=f3a["aicc"],
                aicc_M3b=f3b["aicc"], bic_M3a=f3a["bic"], lrt=float(lrt), lrt_df=G - 1, p_lrt=p_lrt,
                daicc_M1_minus_M3a=float(d_clade), dbic_M1_minus_M3a=float(f1["bic"] - f3a["bic"]), lam=f3a["lam"]),
        curve_wins=curve_wins, clade_wins=clade_wins, classification=classification,
        best_aicc_model=min([("M1", f1["aicc"]), ("M2", f2["aicc"]), ("M3a", f3a["aicc"])], key=lambda t: t[1])[0],
        best_bic_model=min([("M1", f1["bic"]), ("M2", f2["bic"]), ("M3a", f3a["bic"])], key=lambda t: t[1])[0],
    )
    if extra:
        res["_f1"] = f1
    return res


def compact(r):
    """one-line view for sensitivity tables"""
    return dict(n=r["n"], b=r["M1"]["b"], ci95=r["M1"]["ci95"], lam=r["M1"]["lam"], class_M1=r["M1"]["class_M1"],
                D=r["M2"]["D"], b2=r["M2"]["b2"], dAICc_curve=r["M2"]["daicc_M1_minus_M2"],
                dAICc_clade=r["M3"]["daicc_M1_minus_M3a"], p_lrt=r["M3"]["p_lrt"], R=r["M3"]["R"],
                classification=r["classification"])


def m1_only(d, C, lam=None):
    n = d["n"]
    f = pgls.fit_pgls(d["y"], np.column_stack([np.ones(n), d["x"]]), C, lam)
    lo, hi = pgls.ci_t(f, 1)
    return dict(n=n, b=float(f["beta"][1]), ci95=[float(lo), float(hi)], lam=f["lam"], class_M1=classify(lo, hi))


def curv_only(d, C):
    n = d["n"]; x = d["x"]; xc = x - x.mean()
    f1 = pgls.fit_pgls(d["y"], np.column_stack([np.ones(n), x]), C)
    f2 = pgls.fit_pgls(d["y"], np.column_stack([np.ones(n), xc, xc ** 2]), C)
    q05, q95 = np.quantile(x, [0.05, 0.95])
    D = abs(2 * f2["beta"][2] * (q95 - q05))
    return dict(b2=float(f2["beta"][2]), D=float(D), dAICc_curve=float(f1["aicc"] - f2["aicc"]))


def vcv_for(d, tree):
    tk = tipkeys(tree)
    keep = [tk[k] for k in d["key"]]
    C, base, scale = tree.vcv(keep)
    return C


def bootstrap_b(f1, d, C, rng, nboot):
    n = d["n"]
    X = np.column_stack([np.ones(n), d["x"]])
    bs = []
    for _ in range(nboot):
        ys = pgls.simulate(f1, X, rng)
        fb = pgls.fit_pgls(ys, X, C)
        bs.append(fb["beta"][1])
    bs = np.array(bs)
    return [float(np.quantile(bs, 0.025)), float(np.quantile(bs, 0.975))], float(bs.mean()), float(bs.std())


# ---- main ---------------------------------------------------------------------------------------
def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    S = {"prereg_sha256_registered": open(os.path.join(HERE, "PREREG.sha256")).read().split()[0],
         "nboot": NBOOT, "seed": SEED, "thresholds": dict(d_aicc=D_AICC, d_curv=D_CURV, p_lrt=P_LRT, r_spread=R_SPREAD,
                                                         min_order=MIN_ORDER, robust_trees=ROBUST_TREES)}
    tree0 = load_tree_mcc()
    P = load_pantheria(tree=tree0)
    S["P_data"] = dict(n=P["n"], n_bmr_positive_before_tree_match=P["n_before_tree_match"],
                       mass_range_g=[float(P["M"].min()), float(P["M"].max())],
                       n_orders=len(set(P["order"])), orders={o: P["order"].count(o) for o in sorted(set(P["order"]))})
    with open(os.path.join(OUT, "species_P.csv"), "w") as f:
        w = csv.writer(f)
        w.writerow(["binomial", "order", "family", "tip_label", "BMR_mLO2_per_h", "paired_mass_g"])
        for i in range(P["n"]):
            w.writerow([P["key"][i], P["order"][i], P["family"][i], P["tip"][i], P["B"][i], P["M"][i]])
    C0 = vcv_for(P, tree0)

    # headline on T0
    H = decide(P, C0, extra=True)
    f1 = H.pop("_f1")
    ci_b, mean_b, sd_b = bootstrap_b(f1, P, C0, rng, NBOOT)
    H["M1"]["bootstrap_ci95"] = ci_b
    H["M1"]["bootstrap_mean"], H["M1"]["bootstrap_sd"] = mean_b, sd_b
    H["M1"]["class_bootstrap"] = classify(*ci_b)
    H["M1"]["fixed_slope_support"] = dict(
        daicc_2_3_minus_free=H["fixed23"]["daicc_vs_M1"], daicc_3_4_minus_free=H["fixed34"]["daicc_vs_M1"])
    S["T0_headline"] = H
    print("T0", json.dumps(compact(H)), "bootstrap", ci_b, "t", round(time.time() - t0))

    # 100 posterior trees
    trees = pgls.read_nexus_trees(os.path.join(DATA, "upham_NDexp_sample100.trees"))
    per_tree = []
    for i, t in enumerate(trees):
        Ct = vcv_for(P, t)
        r = decide(P, Ct)
        row = dict(tree=i + 1, b=r["M1"]["b"], lo=r["M1"]["ci95"][0], hi=r["M1"]["ci95"][1], lam=r["M1"]["lam"],
                   class_M1=r["M1"]["class_M1"], dAICc_curve=r["M2"]["daicc_M1_minus_M2"], D=r["M2"]["D"], b2=r["M2"]["b2"],
                   dAICc_clade=r["M3"]["daicc_M1_minus_M3a"], p_lrt=r["M3"]["p_lrt"], R=r["M3"]["R"],
                   curve_wins=int(r["curve_wins"]), clade_wins=int(r["clade_wins"]), classification=r["classification"],
                   dAICc_fixed23=r["fixed23"]["daicc_vs_M1"], dAICc_fixed34=r["fixed34"]["daicc_vs_M1"])
        per_tree.append(row)
        if i % 10 == 0:
            print("tree", i + 1, row["b"], row["classification"], round(time.time() - t0))
    with open(os.path.join(OUT, "tree100_decisions.csv"), "w") as f:
        w = csv.DictWriter(f, fieldnames=list(per_tree[0].keys()))
        w.writeheader()
        w.writerows(per_tree)
    from collections import Counter
    bs_ = np.array([r["b"] for r in per_tree])
    S["T100"] = dict(
        n_trees=len(per_tree), b_median=float(np.median(bs_)), b_range=[float(bs_.min()), float(bs_.max())],
        ci_lo_median=float(np.median([r["lo"] for r in per_tree])), ci_hi_median=float(np.median([r["hi"] for r in per_tree])),
        lam_median=float(np.median([r["lam"] for r in per_tree])),
        classification_counts=dict(Counter(r["classification"] for r in per_tree)),
        class_M1_counts=dict(Counter(r["class_M1"] for r in per_tree)),
        curve_wins=sum(r["curve_wins"] for r in per_tree), clade_wins=sum(r["clade_wins"] for r in per_tree),
        dAICc_curve_median=float(np.median([r["dAICc_curve"] for r in per_tree])),
        dAICc_clade_median=float(np.median([r["dAICc_clade"] for r in per_tree])),
        D_median=float(np.median([r["D"] for r in per_tree])),
        dAICc_fixed23_median=float(np.median([r["dAICc_fixed23"] for r in per_tree])),
        dAICc_fixed34_median=float(np.median([r["dAICc_fixed34"] for r in per_tree])),
    )
    S["T100"]["robust_same_as_T0"] = S["T100"]["classification_counts"].get(H["classification"], 0) >= ROBUST_TREES

    # ---- sensitivity ----
    sens = {}
    # 1 adult body mass
    Pa = load_pantheria("5-1_AdultBodyMass_g", tree0)
    sens["adult_mass_5-1"] = compact(decide(Pa, vcv_for(Pa, tree0)))
    # 2 mass range
    x = P["x"]
    terc = np.quantile(x, [1 / 3, 2 / 3])
    for name, m in [("tercile_small", x <= terc[0]), ("tercile_mid", (x > terc[0]) & (x <= terc[1])), ("tercile_large", x > terc[1])]:
        d = subset(P, m)
        sens["range_" + name] = dict(m1_only(d, C0[np.ix_(m, m)]), mass_range_g=[float(d["M"].min()), float(d["M"].max())])
    m = (P["M"] >= 10) & (P["M"] <= 1e5)
    sens["range_10g_to_100kg"] = compact(decide(subset(P, m), C0[np.ix_(m, m)]))
    # 3 outliers
    keep = np.abs(f1["resid_std"]) <= 3
    sens["outliers_removed_abs_resid_gt_3"] = dict(compact(decide(subset(P, keep), C0[np.ix_(keep, keep)])), n_dropped=int((~keep).sum()),
                                                   dropped=[P["key"][i] for i in np.where(~keep)[0]])
    # 4 leave-one-order-out
    loo = {}
    for o in sorted(set(P["order"])):
        k = np.array([a != o for a in P["order"]])
        if k.sum() < 50:
            continue
        loo[o] = dict(m1_only(subset(P, k), C0[np.ix_(k, k)]), n_removed=int((~k).sum()))
    bsl = [v["b"] for v in loo.values()]
    sens["leave_one_order_out"] = dict(b_range=[min(bsl), max(bsl)], per_order=loo,
                                       classes=dict(Counter(v["class_M1"] for v in loo.values())))
    # 5 trees / lambda
    for nm, fn in [("upham_FBD_MCC", "upham_FBD_MCC.tre")]:
        tr = load_tree_mcc(fn)
        Pt = load_pantheria(tree=tr)
        sens["tree_" + nm] = compact(decide(Pt, vcv_for(Pt, tr)))
    try:
        txt = open(os.path.join(DATA, "bininda_emonds_2007.nex")).read()
        tr = read_one_nexus(txt)
        tk = {l: l for l in tr.leaf}
        recs = [dict(key=k, order=o, family=fm, B=b, M=mm, tip=k) for k, o, fm, b, mm in
                zip(P["key"], P["order"], P["family"], P["B"], P["M"]) if k in tk]
        Pb = _frame(recs, P["n"])
        Cb = tr.vcv(Pb["key"])[0]
        sens["tree_bininda_emonds_2007"] = compact(decide(Pb, Cb))
        sens["tree_bininda_emonds_2007"]["note"] = f"{Pb['n']} of {P['n']} species have an exact tip-name match"
    except Exception as e:  # logged, not hidden
        sens["tree_bininda_emonds_2007"] = dict(error=repr(e))
    sens["lambda_0_OLS"] = compact(decide(P, C0, lam=0.0))
    sens["lambda_1_Brownian"] = compact(decide(P, C0, lam=1.0))
    # 6 data source
    A = anage_frame(tree0)
    CA = vcv_for(A, tree0)
    Ares = decide(A, CA)
    S["S1_anage_mammals"] = dict(n=A["n"], n_rows_before_tree_match=A["n_before_tree_match"], **compact(Ares),
                                 aicc_best=Ares["best_aicc_model"], fixed23_dAICc=Ares["fixed23"]["daicc_vs_M1"],
                                 fixed34_dAICc=Ares["fixed34"]["daicc_vs_M1"], M3_groups=Ares["M3"]["group_n"],
                                 M3_slopes=Ares["M3"]["slopes"], D_curve_slope_q05_q95=[Ares["M2"]["slope_q05"], Ares["M2"]["slope_q95"]])
    S["S1_anage_mammals"]["replicates_P"] = bool(Ares["classification"] == H["classification"])
    Pkeys = set(P["key"])
    # all PanTHERIA BMR species (even unmatched to tree) for the independence test
    Anon = anage_frame(tree0, exclude_keys=Pkeys)
    S["S1_not_in_P"] = dict(n=Anon["n"], **compact(decide(Anon, vcv_for(Anon, tree0)))) if Anon["n"] >= 40 else dict(n=Anon["n"], note="too few (<40) to fit")
    S["S1_overlap_with_P"] = int(sum(1 for k in A["key"] if k in Pkeys))
    Aq = anage_frame(tree0, quality_ok=("acceptable", "high"))
    sens["S1_quality_acceptable_or_high"] = compact(decide(Aq, vcv_for(Aq, tree0)))
    for o in ("wild", "captivity"):
        Ao = anage_frame(tree0, origin=o)
        sens[f"S1_origin_{o}"] = compact(decide(Ao, vcv_for(Ao, tree0))) if Ao["n"] >= 40 else dict(n=Ao["n"], note="too few")
    # M4: temperature covariate (AnAge mammals with body temperature)
    mt = ~np.isnan(A["T"])
    At = subset(A, mt)
    Ct = CA[np.ix_(mt, mt)]
    Tc = -1.0 / (KB * At["T"])  # exp(-E/kT) form: coefficient on -1/kT is E
    Tc = Tc - Tc.mean()
    n = At["n"]
    f_a = pgls.fit_pgls(At["y"], np.column_stack([np.ones(n), At["x"]]), Ct)
    f_t = pgls.fit_pgls(At["y"], np.column_stack([np.ones(n), At["x"], Tc]), Ct)
    S["S1_M4_temperature"] = dict(n=n, b_without_T=float(f_a["beta"][1]), b_with_T=float(f_t["beta"][1]),
                                  b_with_T_ci95=[float(v) for v in pgls.ci_t(f_t, 1)],
                                  E_eV=float(f_t["beta"][2]), E_ci95=[float(v) for v in pgls.ci_t(f_t, 2)],
                                  daicc_without_minus_with=float(f_a["aicc"] - f_t["aicc"]),
                                  Tb_range_K=[float(np.nanmin(A["T"])), float(np.nanmax(A["T"]))])
    # union P + S1 (AnAge-only species added; log10 W units, 1 mL O2 = 20.1 J)
    conv = 20.1 / 3600.0
    un = {k: (b * conv, mm, o, fm, t) for k, b, mm, o, fm, t in zip(P["key"], P["B"], P["M"], P["order"], P["family"], P["tip"])}
    for i, k in enumerate(A["key"]):
        if k not in un:
            un[k] = (A["B"][i], A["M"][i], A["order"][i], A["family"][i], A["tip"][i])
    # AnAge orders are upper case Latin names; PanTHERIA are title case -> normalise
    recs = [dict(key=k, B=v[0], M=v[1], order=v[2].upper(), family=v[3].upper(), tip=v[4]) for k, v in un.items()]
    Un = _frame(recs, len(recs))
    sens["union_P_plus_S1"] = compact(decide(Un, vcv_for(Un, tree0)))
    S["sensitivity"] = sens
    S["runtime_s"] = round(time.time() - t0)
    json.dump(S, open(os.path.join(OUT, "summary.json"), "w"), indent=1, default=float)
    print("done", S["runtime_s"], "s")


if __name__ == "__main__":
    main()
