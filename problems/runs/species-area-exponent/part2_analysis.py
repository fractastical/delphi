#!/usr/bin/env python3
"""Part 2 (PREREG.md): GIFT island species-area test. Needs derived/gift_richness.csv (fetch_gift.py).

Writes derived/part2_summary.json, part2_groups.csv, part2_models.csv, part2_grok_null.csv.
"""
import json, os, sys, time
import numpy as np
import pandas as pd
from scipy import optimize, special, stats
from statsmodels.tools.numdiff import approx_hess3

HERE = os.path.dirname(os.path.abspath(__file__))
DER = os.path.join(HERE, "derived")
SEED = 20261101
QUICK = "--quick" in sys.argv


# ------------------------------------------------------------------ NB2 machinery
def nb_ll(y, mu, loga):
    r = np.exp(-loga)
    mu = np.maximum(mu, 1e-10)
    return float((special.gammaln(y + r) - special.gammaln(r) - special.gammaln(y + 1)
                  + r * (np.log(r) - np.log(r + mu)) + y * (np.log(mu) - np.log(r + mu))).sum())


def nb_ll_vec(y, mu, loga):
    r = np.exp(-loga)
    mu = np.maximum(mu, 1e-10)
    return (special.gammaln(y + r) - special.gammaln(r) - special.gammaln(y + 1)
            + r * (np.log(r) - np.log(r + mu)) + y * (np.log(mu) - np.log(r + mu)))


class Model:
    def __init__(self, name, k, mu_fn, starts):
        self.name, self.k, self.mu_fn, self.starts = name, k, mu_fn, starts


def lnA_of(A):
    return np.log(A)


MODELS = {
    "pow": Model("pow", 2, lambda p, lnA: np.exp(np.clip(p[0] + p[1] * lnA, -30, 30)),
                 lambda y, lnA: [[np.log(y.mean()), 0.25], [np.log(y.mean()), 0.15]]),
    "quad": Model("quad", 3, lambda p, lnA: np.exp(np.clip(p[0] + p[1] * lnA + p[2] * lnA ** 2, -30, 30)),
                  lambda y, lnA: [[np.log(y.mean()), 0.25, 0.0], [np.log(y.mean()), 0.3, -0.01]]),
    "gle": Model("gle", 2, lambda p, lnA: np.maximum(p[0] + p[1] * lnA, 1e-6),
                 lambda y, lnA: [list(np.polyfit(lnA, y, 1)[::-1]), [y.mean(), 20.0]]),
    "lom": Model("lom", 3, lambda p, lnA: np.exp(p[0]) / (1 + np.exp(p[1] - p[2] * lnA)),
                 lambda y, lnA: [[np.log(y.max() * 1.5), 2.0, 0.5], [np.log(y.max() * 5), 4.0, 0.3], [np.log(y.max() * 1.1), 0.0, 1.0]]),
    "ls": Model("ls", 2, lambda p, lnA: np.exp(p[0]) * np.log1p(np.exp(np.clip(lnA - p[1], -50, 50))),
                lambda y, lnA: [[np.log(y.max() / 3), np.log(np.exp(lnA).min())], [np.log(y.max()), np.log(np.exp(lnA).max()) - 3],
                                [np.log(y.max() / 6), np.log(np.exp(lnA).max())]]),
}


def fit(model, A, y, extra_starts=None):
    lnA = np.log(A)
    best = None
    starts = [list(s) for s in model.starts(y, lnA)]
    if extra_starts is not None:
        starts.append(list(extra_starts))
    for s in starts:
        for la0 in (-0.5,):
            x0 = np.array(list(s) + [la0], dtype=float)
            f = lambda p: -nb_ll(y, model.mu_fn(p[:-1], lnA), p[-1]) if np.isfinite(p).all() else 1e12
            r = optimize.minimize(f, x0, method="Nelder-Mead", options=dict(xatol=1e-6, fatol=1e-8, maxiter=2500, maxfev=2500))
            r = optimize.minimize(f, r.x, method="BFGS", options=dict(gtol=1e-6))
            if np.isfinite(r.fun) and (best is None or r.fun < best.fun):
                best = r
    ll = -best.fun
    return dict(p=best.x, ll=ll, aic=2 * (model.k + 1) - 2 * ll)


def power_fit_fast(A, y, x0=None):
    """NB2 power law via BFGS (used in bootstrap and null loops)."""
    lnA = np.log(A)
    if x0 is None:
        x0 = np.array([np.log(max(y.mean(), 0.5)), 0.25, -0.5])
    f = lambda p: -nb_ll(y, np.exp(np.clip(p[0] + p[1] * lnA, -30, 30)), p[2])
    r = optimize.minimize(f, x0, method="BFGS", options=dict(gtol=1e-5))
    return r.x, -r.fun


def wald(model, p, A, y):
    lnA = np.log(A)
    f = lambda q: -nb_ll(y, model.mu_fn(q[:-1], lnA), q[-1])
    H = approx_hess3(p, f)
    try:
        cov = np.linalg.inv(H)
        se = np.sqrt(np.maximum(np.diag(cov), 0))
    except np.linalg.LinAlgError:
        se = np.full(len(p), np.nan)
    return se


def group_ids(df):
    lon = np.clip(np.floor((df.longitude + 180) / 60).astype(int), 0, 5)
    lat = np.clip(np.floor((df.latitude + 90) / 30).astype(int), 0, 5)
    return [f"lon{-180 + 60 * a}_lat{-90 + 30 * b}" for a, b in zip(lon, lat)]


def main():
    t0 = time.time()
    df = pd.read_csv(os.path.join(DER, "gift_richness.csv"))
    isl = df[df.role == "island"].copy().reset_index(drop=True)
    mainl = df[df.role == "mainland"].copy().reset_index(drop=True)
    isl["group"] = group_ids(isl)
    out = dict(n_islands=int(len(isl)), n_mainland=int(len(mainl)))
    A, y = isl.area.values.astype(float), isl.native_richness.values.astype(float)
    out["island_area_range_km2"] = [float(A.min()), float(A.max())]
    out["island_richness_range"] = [int(y.min()), int(y.max())]
    out["island_area_decades"] = float(np.log10(A.max() / A.min()))

    # ---------------- pooled model fits
    fits = {m: fit(MODELS[m], A, y) for m in MODELS}
    lnA = np.log(A)
    rows = []
    for m, f in fits.items():
        mu = MODELS[m].mu_fn(f["p"][:-1], lnA)
        rows.append(dict(model=m, k=MODELS[m].k + 1, loglik=f["ll"], aic=f["aic"], mean_abs_resid_lnS=float(np.mean(np.abs(np.log(y) - np.log(np.maximum(mu, 1e-10))))),
                         params=json.dumps([float(v) for v in f["p"]])))
    mt = pd.DataFrame(rows)
    mt["dAIC_vs_pow"] = mt.aic - mt.loc[mt.model == "pow", "aic"].values[0]
    z_pool = float(fits["pow"]["p"][1])
    se_pow = wald(MODELS["pow"], fits["pow"]["p"], A, y)
    out["pooled_power"] = dict(b0=float(fits["pow"]["p"][0]), z=z_pool, z_se_wald=float(se_pow[1]),
                               nb_alpha=float(np.exp(fits["pow"]["p"][2])))
    se_q = wald(MODELS["quad"], fits["quad"]["p"], A, y)
    out["pooled_quad"] = dict(z=float(fits["quad"]["p"][1]), q=float(fits["quad"]["p"][2]), q_se_wald=float(se_q[2]),
                              q_ci95=[float(fits["quad"]["p"][2] - 1.96 * se_q[2]), float(fits["quad"]["p"][2] + 1.96 * se_q[2])],
                              local_z_at_min_area=float(fits["quad"]["p"][1] + 2 * fits["quad"]["p"][2] * np.log(A.min())),
                              local_z_at_median_area=float(fits["quad"]["p"][1] + 2 * fits["quad"]["p"][2] * np.log(np.median(A))),
                              local_z_at_max_area=float(fits["quad"]["p"][1] + 2 * fits["quad"]["p"][2] * np.log(A.max())))

    # ---------------- bootstrap CI of pooled z
    rng = np.random.default_rng(SEED)
    B = 100 if QUICK else 1000
    zb = []
    x0 = np.array([fits["pow"]["p"][0], z_pool, fits["pow"]["p"][2]])
    for b in range(B):
        ix = rng.integers(0, len(isl), len(isl))
        p, _ = power_fit_fast(A[ix], y[ix], x0)
        zb.append(p[1])
    ci_pool = np.percentile(zb, [2.5, 97.5])
    out["pooled_z_bootstrap_ci95"] = [float(ci_pool[0]), float(ci_pool[1])]
    out["pooled_z_ci_width"] = float(ci_pool[1] - ci_pool[0])

    # ---------------- groups
    grows = []
    for g, d in isl.groupby("group"):
        if len(d) < 10:
            grows.append(dict(group=g, n=len(d), qualifying=False))
            continue
        Ag, yg = d.area.values.astype(float), d.native_richness.values.astype(float)
        p, ll = power_fit_fast(Ag, yg)
        se = wald(MODELS["pow"], p, Ag, yg)
        qf = fit(MODELS["quad"], Ag, yg)
        grows.append(dict(group=g, n=len(d), qualifying=True, z=float(p[1]), z_se=float(se[1]),
                          z_lo=float(p[1] - 1.96 * se[1]), z_hi=float(p[1] + 1.96 * se[1]),
                          area_decades=float(np.log10(Ag.max() / Ag.min())), q=float(qf["p"][2]),
                          S_median=float(np.median(yg))))
    gt = pd.DataFrame(grows)
    q = gt[gt.qualifying == True].copy()  # noqa
    n_q = len(q)
    out["n_groups_total"] = int(len(gt))
    out["n_groups_qualifying"] = int(n_q)
    if n_q:
        q["overlaps_pooled"] = (q.z_hi >= ci_pool[0]) & (q.z_lo <= ci_pool[1])
        out["groups_overlapping_pooled"] = int(q.overlaps_pooled.sum())
        dis = [(a.group, b.group) for i, a in q.iterrows() for j, b in q.iterrows() if i < j and (a.z_hi < b.z_lo or b.z_hi < a.z_lo)]
        out["n_disjoint_group_pairs"] = len(dis)
        out["n_group_pairs"] = n_q * (n_q - 1) // 2
        w = 1 / q.z_se ** 2
        zbar = (w * q.z).sum() / w.sum()
        Qs = (w * (q.z - zbar) ** 2).sum()
        tau2 = max(0.0, (Qs - (n_q - 1)) / (w.sum() - (w ** 2).sum() / w.sum()))
        out["tau_DL"] = float(np.sqrt(tau2))
        out["group_z_unweighted_sd"] = float(q.z.std())
        out["group_z_range"] = [float(q.z.min()), float(q.z.max())]
        out["share_groups_q_negative"] = float((q.q < 0).mean())
        out["share_groups_q_same_sign_as_pooled"] = float((np.sign(q.q) == np.sign(out["pooled_quad"]["q"])).mean())
        q.to_csv(os.path.join(DER, "part2_groups.csv"), index=False, float_format="%.5g")

    # ---------------- spatially blocked CV (leave one qualifying group out)
    elpd = {m: 0.0 for m in MODELS}
    nheld = 0
    qual_groups = list(q.group) if n_q else []
    for g in qual_groups:
        te = (isl.group == g).values
        for m in MODELS:
            f = fit(MODELS[m], A[~te], y[~te])
            mu = MODELS[m].mu_fn(f["p"][:-1], np.log(A[te]))
            elpd[m] += float(nb_ll(y[te], mu, f["p"][-1]))
        nheld += int(te.sum())
    out["cv_elpd_held_out"] = elpd
    out["cv_n_held_out"] = nheld
    out["cv_dELPD_vs_pow"] = {m: elpd[m] - elpd["pow"] for m in elpd}
    mt["cv_elpd"] = mt.model.map(elpd)
    mt.to_csv(os.path.join(DER, "part2_models.csv"), index=False, float_format="%.6g")
    out["models"] = mt.drop(columns=["params"]).to_dict(orient="records")

    # ---------------- decision rules
    daic = {m: float(mt.set_index("model").loc["pow", "aic"] - mt.set_index("model").loc[m, "aic"]) for m in MODELS if m != "pow"}
    out["aic_advantage_over_pow"] = daic
    U1 = 0.15 <= z_pool <= 0.35
    U2 = out["pooled_z_ci_width"] < 0.1
    U3 = bool(n_q >= 5 and out["groups_overlapping_pooled"] == n_q)
    U4 = bool(n_q >= 5 and out["tau_DL"] < 0.05)
    best_alt_aic = max(daic.values())
    best_alt_elpd = max(out["cv_dELPD_vs_pow"][m] for m in MODELS if m != "pow") if nheld else float("nan")
    U5 = bool(best_alt_aic <= 10 and best_alt_elpd <= 10)
    out["universal_rule"] = {"U1_pooled_z_in_0.15_0.35": bool(U1), "U2_ci_width_lt_0.1": bool(U2), "U3_all_groups_overlap": U3,
                             "U4_tau_lt_0.05": U4, "U5_no_alt_beats_pow": U5}
    out["universal_power_law"] = bool(U1 and U2 and U3 and U4 and U5)
    refuted = bool(n_q >= 1 and (out["n_disjoint_group_pairs"] > 0 or out["groups_overlapping_pooled"] < n_q))
    out["universality_refuted"] = refuted
    sd_ok = bool(daic["quad"] > 10 and out["cv_dELPD_vs_pow"]["quad"] > 10 and
                 (out["pooled_quad"]["q_ci95"][0] > 0 or out["pooled_quad"]["q_ci95"][1] < 0) and
                 (n_q >= 1 and (out["share_groups_q_same_sign_as_pooled"] >= 0.7)))
    out["scale_dependent_supported"] = sd_ok
    ms = mt.set_index("model")
    mete_aic_win = daic["ls"] > 10
    mete_resid_win = bool(ms.loc["ls", "mean_abs_resid_lnS"] < ms.loc["pow", "mean_abs_resid_lnS"])
    out["mete_type_rule"] = dict(aic_win=bool(mete_aic_win), resid_win=mete_resid_win,
                                 outcome="win" if (mete_aic_win and mete_resid_win) else ("split" if (mete_aic_win or mete_resid_win) else "no win"))
    best_model = ms.aic.idxmin()
    out["best_model_by_aic"] = best_model
    underpowered = len(isl) < 150 or n_q < 5
    if underpowered:
        cls = "inconclusive (underpowered)"
    elif out["universal_power_law"]:
        cls = "universal power law"
    elif sd_ok and (refuted or not U5):
        cls = "scale-dependent / non-power"
    elif U1 and U5 and not (U3 and U4):
        cls = "power law holds on average but exponent is not universal"
    else:
        cls = "neither"
    out["classification"] = cls

    # ---------------- robustness (never decide a verdict)
    rob = {}
    X = np.column_stack([np.ones(len(A)), np.log10(A)])
    b = np.linalg.lstsq(X, np.log10(y), rcond=None)[0]
    res = np.log10(y) - X @ b
    rob["ols_log10_z"] = float(b[1])
    rob["ols_log10_r2"] = float(1 - res.var() / np.log10(y).var())
    ge1 = A >= 1
    p, _ = power_fit_fast(A[ge1], y[ge1])
    rob["nb_z_area_ge_1km2"] = float(p[1])
    rob["n_area_ge_1km2"] = int(ge1.sum())
    iso = isl.copy()
    iso["cls"] = pd.cut(iso.distance_to_mainland, [-1, 100, 1000, 1e9], labels=["<100km", "100-1000km", ">1000km"])
    rob["z_by_isolation"] = {}
    for c, d in iso.groupby("cls", observed=True):
        if len(d) >= 10:
            Ac, yc = d.area.values.astype(float), d.native_richness.values.astype(float)
            pc, _ = power_fit_fast(Ac, yc)
            sec = wald(MODELS["pow"], pc, Ac, yc)
            rob["z_by_isolation"][str(c)] = dict(n=int(len(d)), z=float(pc[1]), ci95=[float(pc[1] - 1.96 * sec[1]), float(pc[1] + 1.96 * sec[1])])
    out["robustness"] = rob

    # ---------------- darwin1859-ch12-04: islands versus equal-area mainland
    mA, my = mainl.area.values.astype(float), mainl.native_richness.values.astype(float)
    mp, _ = power_fit_fast(mA, my)
    mse = wald(MODELS["pow"], mp, mA, my)
    ocean = isl[isl.distance_to_mainland >= 500].copy()
    pred = np.exp(mp[0] + mp[1] * np.log(ocean.area.values))
    ratio = ocean.native_richness.values / pred
    lr = np.log(ratio)
    w = stats.wilcoxon(lr, alternative="less")
    inr = (ocean.area.values >= mA.min()) & (ocean.area.values <= mA.max())
    out["ch12_04"] = dict(mainland_n=int(len(mainl)), mainland_area_range_km2=[float(mA.min()), float(mA.max())],
                          mainland_z=float(mp[1]), mainland_z_se=float(mse[1]),
                          oceanic_proxy_n=int(len(ocean)), median_ratio=float(np.median(ratio)),
                          share_below_prediction=float((ratio < 1).mean()), wilcoxon_p_one_sided=float(w.pvalue),
                          n_in_mainland_area_range=int(inr.sum()),
                          median_ratio_in_range=float(np.median(ratio[inr])) if inr.any() else None,
                          share_below_in_range=float((ratio[inr] < 1).mean()) if inr.any() else None)
    r0 = out["ch12_04"]
    out["ch12_04"]["verdict"] = ("supports" if (r0["median_ratio"] <= 0.5 and r0["share_below_prediction"] >= 0.7 and r0["wilcoxon_p_one_sided"] < 0.01)
                                  else "refutes" if r0["median_ratio"] >= 1 else "mixed")
    # all islands (not just oceanic proxy): descriptive
    predall = np.exp(mp[0] + mp[1] * np.log(A))
    out["ch12_04"]["all_islands_median_ratio"] = float(np.median(y / predall))

    # ---------------- grok-4-7 n=2: logseries null calibrated on the largest island
    ci = int(np.argmax(A))
    Acal, Scal = A[ci], int(y[ci])
    others = np.arange(len(A)) != ci
    Ao, yo = A[others], y[others]
    p_emp, _ = power_fit_fast(Ao, yo)
    z_emp = float(p_emp[1])
    gro = dict(calibration_island=str(isl.geo_entity[ci]), A_cal=float(Acal), S_cal=Scal, n_test=int(len(Ao)), z_empirical=z_emp)
    R = 20 if QUICK else 300
    rho_grid = [1e1, 1e2, 1e3, 1e4, 1e5, 1e6, 1e7, 1e8]
    nrows = []
    ain = Ao / Acal
    la = np.log1p(-np.minimum(ain, 1 - 1e-12))
    rg = np.random.default_rng([SEED, 5])
    for rho in rho_grid:
        N = rho * Acal
        if N <= Scal * 1.0001:
            nrows.append(dict(rho=rho, feasible=False))
            continue
        alpha = optimize.brentq(lambda al: al * np.log1p(N / al) - Scal, 1e-6, Scal)
        xparam = N / (N + alpha)
        zs, Sexp_z = [], None
        # expected-richness curve exponent (noise-free) at this density
        Eexp = alpha * np.log1p(ain * N / alpha)
        pe, _ = power_fit_fast(Ao, np.round(Eexp))
        for rep in range(R):
            nn = np.minimum(stats.logser.rvs(xparam, size=Scal, random_state=rg).astype(np.float64), 4e18)
            S = np.zeros(len(Ao))
            for c0 in range(0, len(Ao), 400):
                pij = -np.expm1(nn[None, :] * la[c0:c0 + 400, None])
                S[c0:c0 + 400] = (rg.random(pij.shape) < pij).sum(1)
            pz, _ = power_fit_fast(Ao, S)
            zs.append(pz[1])
        zs = np.array(zs)
        lo, hi = np.percentile(zs, [2.5, 97.5])
        nrows.append(dict(rho=rho, feasible=True, alpha=float(alpha), z_null_median=float(np.median(zs)), z_null_lo=float(lo), z_null_hi=float(hi),
                          z_expected_curve=float(pe[1]), inside=bool(lo <= z_emp <= hi), n_rep=R))
        print("grok null rho", rho, round(time.time() - t0), "s", flush=True)
    gdf = pd.DataFrame(nrows)
    gdf.to_csv(os.path.join(DER, "part2_grok_null.csv"), index=False, float_format="%.5g")
    feas = gdf[gdf.feasible == True]  # noqa
    gro["densities_feasible"] = int(len(feas))
    gro["densities_inside"] = int(feas.inside.sum()) if len(feas) else 0
    gro["outcome"] = "pass" if gro["densities_inside"] >= 1 else "fail"
    gro["no_discriminating_power_flag"] = bool(gro["densities_inside"] >= 5)
    out["grok_n2"] = gro
    out["runtime_s"] = round(time.time() - t0)
    json.dump(out, open(os.path.join(DER, "part2_summary.json"), "w"), indent=1, default=float)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main()
