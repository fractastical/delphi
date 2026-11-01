#!/usr/bin/env python3
"""Part 1 (PREREG.md): sampling-only species-area null and Preston canonical lognormal.

Outputs derived/part1_cells.csv.gz, derived/part1_stochastic.csv.gz, derived/part1_preston.json,
derived/part1_summary.json. Deterministic given the seed.
"""
import gzip, json, os, sys, time
import numpy as np
import pandas as pd
from scipy import stats, optimize, special

HERE = os.path.dirname(os.path.abspath(__file__))
DER = os.path.join(HERE, "derived")
os.makedirs(DER, exist_ok=True)
SEED = 20261101
rng = np.random.default_rng(SEED)
QUICK = "--quick" in sys.argv

# ------------------------------------------------------------------ pools
def ln_pool(S0, sigma, J):
    q = stats.norm.ppf((np.arange(S0) + 0.5) / S0)
    mu = np.log(J / S0) - sigma ** 2 / 2
    return np.maximum(1, np.round(np.exp(mu + sigma * q))).astype(np.float64)


def expS_vec(n, a):
    """Coleman: sum_j 1-(1-a)^n_j for an array of area fractions a."""
    a = np.atleast_1d(a)
    out = np.empty(len(a))
    la = np.log1p(-a)
    for i, l in enumerate(la):
        out[i] = (-np.expm1(n * l)).sum()
    return out


def ls_expS(alpha, J, a):
    return alpha * np.log1p(np.asarray(a) * J / alpha)


def check_logseries_closed_form():
    """Numerical sum over the logseries pmf versus the closed form."""
    res = []
    for alpha, J in [(20, 1e5), (100, 1e5), (5, 1e4)]:
        x = J / (J + alpha)
        nmax = int(60 * (J + alpha) / alpha)
        n = np.arange(1, nmax + 1, dtype=float)
        w = alpha * np.exp(n * np.log(x) - np.log(n))
        for a in [1e-4, 1e-2, 0.3]:
            num = (w * (-np.expm1(n * np.log1p(-a)))).sum()
            cf = ls_expS(alpha, J, a)
            res.append(dict(alpha=alpha, J=J, a=a, numeric=float(num), closed=float(cf), rel_err=float(abs(num - cf) / cf)))
    return res


def islands(n_isl, D, amax, r):
    u = np.concatenate([[0.0], r.uniform(0, 1, n_isl - 2), [1.0]])
    return amax * 10.0 ** (-D * u)


# ------------------------------------------------------------------ fits
def ols_z(A, S):
    m = S >= 1
    if m.sum() < 4:
        return np.nan
    x, y = np.log10(A[m]), np.log10(S[m])
    return np.polyfit(x, y, 1)[0]


def quad_q(A, S):
    x, y = np.log10(A), np.log10(S)
    return np.polyfit(x, y, 2)[0]


def pois_ll(y, mu):
    mu = np.maximum(mu, 1e-12)
    return float((y * np.log(mu) - mu - special.gammaln(y + 1)).sum())


def pois_glm(X, y, beta0=None, it=60):
    beta = np.zeros(X.shape[1]) if beta0 is None else beta0.copy()
    if beta0 is None:
        beta[0] = np.log(max(y.mean(), 0.5))
    for _ in range(it):
        eta = np.clip(X @ beta, -50, 50)
        mu = np.exp(eta)
        W = mu
        z = eta + (y - mu) / np.maximum(mu, 1e-12)
        XtW = X.T * W
        try:
            new = np.linalg.solve(XtW @ X + 1e-10 * np.eye(X.shape[1]), XtW @ z)
        except np.linalg.LinAlgError:
            break
        if np.max(np.abs(new - beta)) < 1e-9:
            beta = new
            break
        beta = new
    mu = np.exp(np.clip(X @ beta, -50, 50))
    return beta, pois_ll(y, mu)


def fit_models(A, S):
    """Poisson-likelihood fits of the four forms; returns dict of AIC (and z of the power law)."""
    lnA = np.log(A)
    y = S.astype(float)
    X1 = np.column_stack([np.ones_like(lnA), lnA])
    b1, ll1 = pois_glm(X1, y)
    c = lnA.mean()
    X2 = np.column_stack([np.ones_like(lnA), lnA - c, (lnA - c) ** 2])
    b2, ll2 = pois_glm(X2, y)

    def nll_gle(p):
        return -pois_ll(y, np.maximum(p[0] + p[1] * lnA, 1e-6))
    ols = np.polyfit(lnA, y, 1)
    r = optimize.minimize(nll_gle, [ols[1], ols[0]], method="Nelder-Mead", options=dict(xatol=1e-6, fatol=1e-9, maxiter=4000))
    ll3 = -r.fun

    def nll_ls(p):
        al, As = np.exp(p)
        return -pois_ll(y, al * np.log1p(A / As))
    best = None
    for al0 in [y.max() / 3, y.max()]:
        for lAs in [np.log(A.min()), np.log(A.max()) - 3, np.log(A.max())]:
            r = optimize.minimize(nll_ls, [np.log(al0), lAs], method="Nelder-Mead", options=dict(xatol=1e-6, fatol=1e-9, maxiter=4000))
            if best is None or r.fun < best.fun:
                best = r
    ll4 = -best.fun
    k = dict(pow=2, quad=3, gle=2, ls=2)
    ll = dict(pow=ll1, quad=ll2, gle=ll3, ls=ll4)
    aic = {m: 2 * k[m] - 2 * ll[m] for m in k}
    return aic, b1[1], b2[2]


# ------------------------------------------------------------------ gaussian-log analytic model comparison
def analytic_aic(A, ES):
    """Noise-free curve fits on log10 E[S]: AIC = n ln(RSS/n) + 2k for the four forms."""
    lnA = np.log(A)
    y = np.log10(ES)
    n = len(y)

    def aic(rss, k):
        return n * np.log(max(rss, 1e-300) / n) + 2 * k
    out = {}
    p = np.polyfit(lnA, y, 1)
    out["pow"] = aic(((np.polyval(p, lnA) - y) ** 2).sum(), 2)
    p = np.polyfit(lnA, y, 2)
    out["quad"] = aic(((np.polyval(p, lnA) - y) ** 2).sum(), 3)
    # Gleason S = c + z ln A, residual on log10 S
    def r_gle(q):
        mu = np.maximum(q[0] + q[1] * lnA, 1e-6)
        return ((np.log10(mu) - y) ** 2).sum()
    ols = np.polyfit(lnA, ES, 1)
    out["gle"] = aic(optimize.minimize(r_gle, [ols[1], ols[0]], method="Nelder-Mead", options=dict(xatol=1e-8, fatol=1e-14, maxiter=4000)).fun, 2)
    def r_ls(q):
        al, As = np.exp(q)
        return ((np.log10(al * np.log1p(A / As)) - y) ** 2).sum()
    best = None
    for al0 in [ES.max() / 3, ES.max()]:
        for lAs in [np.log(A.min()), np.log(A.max()) - 3, np.log(A.max())]:
            r = optimize.minimize(r_ls, [np.log(al0), lAs], method="Nelder-Mead", options=dict(xatol=1e-8, fatol=1e-14, maxiter=4000))
            if best is None or r.fun < best.fun:
                best = r
    out["ls"] = aic(best.fun, 2)
    return out


# ------------------------------------------------------------------ grid
LN_S0 = [100, 1000, 10000]
LN_SIG = [1.0, 1.5, 2.0, 2.45, 3.0]
LS_ALPHA = [5, 20, 100, 500]
JS = [1e5, 1e7, 1e9]
NISL = [10, 30, 100]
DS = [1, 2, 3, 4, 5]
AMAX = [1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 0.5]


def pools():
    for S0 in LN_S0:
        for sg in LN_SIG:
            for J in JS:
                if J / S0 < 10:
                    continue
                n = ln_pool(S0, sg, J)
                yield dict(family="lognormal", S0=S0, param=sg, J=J, Jreal=float(n.sum())), n
    for al in LS_ALPHA:
        for J in JS:
            yield dict(family="logseries", S0=al * np.log1p(J / al), param=al, J=J, Jreal=J), None


def plausible(p, n_kept, span_kept, amax):
    fam_ok = (p["family"] == "lognormal" and p["param"] in (1.5, 2.0, 2.45, 3.0)) or \
             (p["family"] == "logseries" and p["param"] in (20, 100, 500))
    return bool(fam_ok and p["J"] >= 1e7 and amax <= 0.1 and n_kept >= 8 and span_kept >= 1.5)


def run_grid():
    t0 = time.time()
    rows, stoch = [], []
    cell_id = 0
    for p, n in pools():
        for n_isl in NISL:
            for D in DS:
                for amax in AMAX:
                    r_isl = np.random.default_rng([SEED, cell_id])
                    cell_id += 1
                    A = islands(n_isl, D, amax, r_isl)
                    ES = expS_vec(n, A) if p["family"] == "lognormal" else ls_expS(p["param"], p["J"], A)
                    keep = ES >= 1
                    Ak, ESk = A[keep], ES[keep]
                    nk = int(keep.sum())
                    span = float(np.log10(Ak.max() / Ak.min())) if nk >= 2 else 0.0
                    feasible = nk >= 8 and span >= 1.5
                    row = dict(p, n_isl=n_isl, D=D, amax=amax, n_kept=nk, span_kept=round(span, 3), feasible=feasible)
                    if feasible:
                        row["z_ols"] = ols_z(Ak, ESk)
                        row["q"] = quad_q(Ak, ESk)
                        aa = analytic_aic(Ak, ESk)
                        row.update({f"aicG_{k}": v for k, v in aa.items()})
                    row["plausible"] = plausible(p, nk, span, amax)
                    rows.append(row)
                    # stochastic pass: n_isl == 30 and feasible
                    if feasible and n_isl == 30 and not (p["family"] == "logseries" and p["J"] > 1e7):
                        R = 4 if QUICK else 30
                        zo, zp = [], []
                        aics = []
                        for rep in range(R):
                            rr = np.random.default_rng([SEED, cell_id, rep, 1])
                            if p["family"] == "lognormal":
                                nn = n
                            else:
                                x = p["J"] / (p["J"] + p["param"])
                                nn = np.minimum(stats.logser.rvs(x, size=int(round(p["S0"])), random_state=rr), 2 ** 62).astype(np.float64)
                            counts = rr.binomial(nn[None, :].astype(np.int64), Ak[:, None])
                            S = (counts > 0).sum(1)
                            zo.append(ols_z(Ak, S))
                            beta, _ = pois_glm(np.column_stack([np.ones(len(Ak)), np.log(Ak)]), S.astype(float))
                            zp.append(beta[1])
                            if row["plausible"] and rep < (2 if QUICK else 5) and (S >= 1).all() and S.max() > 5:
                                try:
                                    aic, _, _ = fit_models(Ak, S)
                                    aics.append(aic)
                                except Exception:
                                    pass
                        s = dict(cell=cell_id - 1, family=p["family"], param=p["param"], S0=p["S0"], J=p["J"], D=D, amax=amax,
                                 n_kept=nk, plausible=row["plausible"], z_ols_mean=np.nanmean(zo), z_ols_sd=np.nanstd(zo),
                                 z_pois_mean=np.mean(zp), z_pois_sd=np.std(zp), z_analytic=row.get("z_ols"))
                        if aics:
                            ad = pd.DataFrame(aics)
                            s["n_aic_reps"] = len(ad)
                            for m in ["quad", "gle", "ls"]:
                                s[f"dAIC_pow_minus_{m}"] = float((ad["pow"] - ad[m]).mean())
                        stoch.append(s)
        print(f"pool {p['family']} {p['param']} J={p['J']:.0e} done {round(time.time() - t0)}s", flush=True)
    return pd.DataFrame(rows), pd.DataFrame(stoch)


# ------------------------------------------------------------------ Preston
def preston():
    out = {}
    Sgrid = np.unique(np.round(np.logspace(np.log10(30), 6, 40)).astype(int))
    rows = []
    for S in Sgrid:
        qS = stats.norm.ppf(1 - 1 / (2 * S))
        sigma, mu = qS, qS ** 2
        # abundances by quantile midpoints; use log-sum for huge S
        n = np.maximum(1, np.round(np.exp(mu + sigma * stats.norm.ppf((np.arange(S) + 0.5) / S))))
        rows.append(dict(S=int(S), sigma=float(sigma), mu=float(mu), N=float(n.sum()), S_over_N_exact=float(S / n.sum())))
    df = pd.DataFrame(rows)
    ls, lN = np.log(df.S), np.log(df.N)
    m = (df.S >= 100) & (df.S <= 1e5)
    z_glob = np.polyfit(lN[m], ls[m], 1)[0]
    local = np.gradient(ls, lN)
    out["isolate_z_global_S100_1e5"] = float(z_glob)
    out["isolate_z_local"] = {int(S): float(z) for S, z in zip(df.S[m][::3], local[m][::3])}
    out["isolate_z_range_local"] = [float(local[m].min()), float(local[m].max())]
    out["sigma_at_S"] = {int(S): float(s) for S, s in zip(df.S[::6], df.sigma[::6])}
    # veil-free analytic approximation: N = S exp(1.5 sigma^2), sigma = q_S -> z = 1/(1 + 3 q dq/dlnS)
    # stochastic confirmation
    stoch = {}
    r = np.random.default_rng([SEED, 77])
    for S in [100, 1000, 10000]:
        qS = stats.norm.ppf(1 - 1 / (2 * S))
        sigma, mu = qS, qS ** 2
        Ns, Ss = [], []
        # draw independent communities of S lognormal species, truncate at 1 individual (veil line)
        # realised S counts species with abundance >= 1 after rounding
        ab = np.exp(mu + sigma * r.standard_normal((200, S)))
        ab = np.round(ab)
        Sreal = (ab >= 1).sum(1)
        Nreal = np.where(ab >= 1, ab, 0).sum(1)
        stoch[S] = dict(mean_realised_S=float(Sreal.mean()), mean_N=float(Nreal.mean()))
    # z from the stochastic communities: slope of ln S on ln N over S=100..10000 (three points)
    xs = np.log([stoch[S]["mean_N"] for S in stoch]); ys = np.log([stoch[S]["mean_realised_S"] for S in stoch])
    out["stochastic_isolate_z_S100_1e4"] = float(np.polyfit(xs, ys, 1)[0])
    out["stochastic_detail"] = stoch
    # canonical a=0.2 community sampled by random placement ("sample" exponent)
    sig2 = 1 / (0.2 * np.sqrt(2)) * np.log(2)  # natural-log units
    # S at which gamma=1 holds: sigma = q_S
    from scipy.optimize import brentq
    S_can = brentq(lambda s: stats.norm.ppf(1 - 1 / (2 * s)) - sig2, 5, 1e6)
    out["canonical_a0.2"] = dict(sigma_ln=float(sig2), S_gamma1=float(S_can))
    Sc = int(round(S_can))
    qS = stats.norm.ppf(1 - 1 / (2 * Sc))
    n = np.maximum(1, np.round(np.exp(sig2 ** 2 + sig2 * stats.norm.ppf((np.arange(Sc) + 0.5) / Sc))))
    fr = np.logspace(-6, 0, 25)[:-1]
    ES = np.array([(-np.expm1(n * np.log1p(-f))).sum() for f in fr])
    k = ES >= 1
    out["canonical_a0.2"].update(S_total=Sc, N=float(n.sum()),
                                 sample_z_over_fractions=float(np.polyfit(np.log(fr[k] * n.sum()), np.log(ES[k]), 1)[0]),
                                 sample_z_local={f"{f:.1e}": float(z) for f, z in zip(fr[k][::3], np.gradient(np.log(ES[k]), np.log(fr[k]))[::3])})
    return out, df


def main():
    summ = {}
    summ["logseries_closed_form_check"] = check_logseries_closed_form()
    pr, pdf = preston()
    json.dump(pr, open(os.path.join(DER, "part1_preston.json"), "w"), indent=1)
    pdf.round(6).to_csv(os.path.join(DER, "part1_preston_table.csv"), index=False)
    cells, stoch = run_grid()
    with gzip.open(os.path.join(DER, "part1_cells.csv.gz"), "wt") as f:
        cells.round(5).to_csv(f, index=False)
    with gzip.open(os.path.join(DER, "part1_stochastic.csv.gz"), "wt") as f:
        stoch.round(5).to_csv(f, index=False)
    # ---------------- summary / decision rules
    pl = cells[cells.plausible & cells.feasible]
    summ["n_cells_total"] = int(len(cells))
    summ["n_cells_feasible"] = int(cells.feasible.sum())
    summ["n_plausible"] = int(len(pl))
    summ["plausible_z_quantiles"] = {str(q): float(pl.z_ols.quantile(q)) for q in [0, .05, .25, .5, .75, .95, 1]}
    summ["plausible_z_sd"] = float(pl.z_ols.std())
    summ["H1A_share_in_0.15_0.35"] = float(((pl.z_ols >= 0.15) & (pl.z_ols <= 0.35)).mean())
    summ["H1A"] = summ["H1A_share_in_0.15_0.35"] >= 0.5
    summ["H1B"] = bool(summ["H1A"] and summ["plausible_z_sd"] < 0.05)
    summ["H1C_share_q_below_-0.01"] = float((pl.q < -0.01).mean())
    summ["plausible_by_family"] = {fam: dict(n=int(len(g)), median=float(g.z_ols.median()), sd=float(g.z_ols.std()),
                                             share_in_range=float(((g.z_ols >= .15) & (g.z_ols <= .35)).mean()))
                                   for fam, g in pl.groupby("family")}
    for key in ["amax", "D"]:
        summ[f"plausible_median_z_by_{key}"] = {str(k): float(v) for k, v in pl.groupby(key).z_ols.median().items()}
    summ["plausible_median_z_by_param"] = {f"{k[0]}-{k[1]}": float(v) for k, v in pl.groupby(["family", "param"]).z_ols.median().items()}
    summ["plausible_median_z_by_J"] = {f"{k:.0e}": float(v) for k, v in pl.groupby("J").z_ols.median().items()}
    sp = stoch[stoch.plausible]
    summ["stochastic_plausible_n"] = int(len(sp))
    summ["stochastic_z_ols_minus_analytic_mean"] = float((sp.z_ols_mean - sp.z_analytic).mean())
    summ["stochastic_z_pois_minus_analytic_mean"] = float((sp.z_pois_mean - sp.z_analytic).mean())
    summ["stochastic_z_pois_quantiles"] = {str(q): float(sp.z_pois_mean.quantile(q)) for q in [.05, .25, .5, .75, .95]}
    summ["stochastic_share_pois_z_in_range"] = float(((sp.z_pois_mean >= .15) & (sp.z_pois_mean <= .35)).mean())
    if "dAIC_pow_minus_ls" in sp:
        a = sp.dropna(subset=["dAIC_pow_minus_ls"])
        summ["H1C_stochastic"] = dict(n_cells=int(len(a)),
                                       share_ls_beats_pow_by_10=float((a.dAIC_pow_minus_ls > 10).mean()),
                                       share_quad_beats_pow_by_10=float((a.dAIC_pow_minus_quad > 10).mean()),
                                       share_gle_beats_pow_by_10=float((a.dAIC_pow_minus_gle > 10).mean()),
                                       median_dAIC_pow_minus_ls=float(a.dAIC_pow_minus_ls.median()))
        summ["H1C"] = bool(summ["H1C_share_q_below_-0.01"] >= 0.7 and summ["H1C_stochastic"]["share_ls_beats_pow_by_10"] >= 0.7)
    pa = pl.dropna(subset=["aicG_pow"])
    summ["analytic_gaussianlog_aic"] = dict(share_ls_beats_pow_by_10=float(((pa.aicG_pow - pa.aicG_ls) > 10).mean()),
                                            share_quad_beats_pow_by_10=float(((pa.aicG_pow - pa.aicG_quad) > 10).mean()),
                                            share_gle_beats_pow_by_10=float(((pa.aicG_pow - pa.aicG_gle) > 10).mean()))
    z = pr["isolate_z_global_S100_1e5"]
    summ["H1D_preston_isolate_z"] = z
    summ["H1D"] = bool(abs(z - 0.262) <= 0.02)
    if summ["H1A"] and summ["H1B"]:
        summ["claude_n2_outcome"] = "pass"
    elif summ["plausible_z_sd"] >= 0.10 or not summ["H1A"]:
        summ["claude_n2_outcome"] = "fail"
    else:
        summ["claude_n2_outcome"] = "partial"
    json.dump(summ, open(os.path.join(DER, "part1_summary.json"), "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in summ.items() if k not in ("logseries_closed_form_check",)}, indent=1, default=float))


if __name__ == "__main__":
    main()
