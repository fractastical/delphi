#!/usr/bin/env python3
"""Cross-check the Lean hygromorph definitions against the code published with Marom et al. 2026.

Runs the unmodified Grasshopper components in vendor/ (stimulus -> fibre -> lamina -> tissue ->
beta reducer -> element, on both the Nat and Art branches) on random inputs, reads the Lean
definitions out of ThompsonLaws/Hygromorphs.lean, and compares. Pre-registered in the two
result.json files (hygromorph-antisymmetric-twist and hygromorph-bilayer-curvature); this script
fills in `measured`, `verdict`, etc. in both. Standard library only (numpy is not needed).

    python3 analysis.py
"""
import hashlib
import json
import math
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from lean_eval import LeanDefs  # noqa: E402

ENGINE = HERE.parents[4]
LEAN = ENGINE / "claim-sources/thompson-growth-form/lean/ThompsonLaws/Hygromorphs.lean"
VENDOR = HERE / "vendor"
TESTS = HERE.parents[1]
TWIST_DIR = TESTS / "hygromorph-antisymmetric-twist/marom-crosscheck-01"
BILAYER_DIR = TESTS / "hygromorph-bilayer-curvature/marom-crosscheck-01"
SEED, N, N_ANTI = 20261101, 1000, 500
COMMIT = "fa8100bad1b43525f28106da94a7f055730fb325"

# ---------------------------------------------------------------- the published scripts, verbatim
for line in (VENDOR / "SHA256SUMS").read_text().splitlines():
    digest, name = line.split()
    assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == digest, f"vendor/{name} was edited"

BRANCH = {
    "Nat": dict(F="F_fib", a1="alpha_1", L="L_lam", a2="alpha_2", T="T_tis", ag="alpha_geo", S="S_elem", sfx=""),
    "Art": dict(F="F_fil", a1="alpha_1_prime", L="L_lay", a2="alpha_2_prime", T="T_stack",
                ag="alpha_geo_prime", S="S_print", sfx="_prime"),
}
STIM = {"hygro": "stim_hygro", "thermal": "stim_thermal"}
RESP = {"bend": "beta_bend", "twist": "beta_twist"}


def load_sources(mutate=None):
    """name -> compiled code; `mutate` is {script: [(old, new)]} applied to the source text."""
    out = {}
    for p in VENDOR.glob("*.py"):
        text = p.read_text()
        for old, new in (mutate or {}).get(p.stem, []):
            assert old in text, f"{p.stem}: {old!r} not found"
            text = text.replace(old, new)
        out[p.stem] = compile(text, str(p), "exec")
    return out


def run(code, **ports):
    ns = dict(ports)
    exec(code, ns)
    return ns["bundle"]


def parse(b):
    d = {}
    for t in b.split(";"):
        if "=" in t:
            k, v = t.split("=", 1)
            try:
                d[k.strip()] = float(v)
            except ValueError:
                d[k.strip()] = v
    return d


def chain(src, branch, stim, resp, dr):
    """The Grasshopper wiring of gh_scripts/README.md for one draw. Returns the parsed bundles at the
    tissue stage, after the beta reducer, and at the element stage."""
    B = BRANCH[branch]
    sfx = B["sfx"]
    mats = [f"name=m{i};E={dr['E'][i]};{'chi' if stim == 'hygro' else 'alpha'}_L={dr['cL'][i]:.4f};"
            f"{'chi' if stim == 'hygro' else 'alpha'}_T={dr['cT'][i]:.4f}" for i in (0, 1)]
    if stim == "hygro":
        b = run(src[STIM[stim] + sfx], mat1=mats[0], mat2=mats[1], RH_ref=dr["x0"], RH=dr["x1"])
    else:
        b = run(src[STIM[stim] + sfx], mat1=mats[0], mat2=mats[1], T_ref=dr["x0"], T_cur=dr["x1"])
    geo = run(src["geo"], theta_1=dr["th"][0], theta_2=dr["th"][1], h_1=dr["h"][0], h_2=dr["h"][1], L=8.0, W=1.2, bc="free")
    b = run(src[B["F"]], bundle_in=b)
    b = run(src[B["a1"]], bundle_in=b)
    b = run(src[B["L"]], bundle_in=b)
    b = run(src[B["a2"]], bundle_in=b, geo_bundle=geo)
    b = run(src[B["T"]], bundle_in=b)
    tissue = parse(b)
    b = run(src[RESP[resp] + sfx], bundle_in=b)
    beta = parse(b)
    b = run(src[B["ag"]], bundle_in=b, geo_bundle=geo)
    b = run(src[B["S"]], bundle_in=b)
    return tissue, beta, parse(b)


# ---------------------------------------------------------------- draws
def draw_one(rng, stim, anti=False):
    def coefs():
        while True:
            cl, ct = rng.randint(-2000, 3000), rng.randint(-2000, 3000)
            if abs(cl - ct) >= 50:
                return cl / 1e4, ct / 1e4
    cl1, ct1 = coefs()
    cl2, ct2 = (cl1, ct1) if anti else coefs()
    logE = lambda: int(round(math.exp(rng.uniform(math.log(100), math.log(20000)))))
    E1 = logE()
    E2 = E1 if anti else logE()
    if anti:
        t = rng.choice([k for k in range(-9000, 9001) if k != 0]) / 100
        th = (t, -t)
    else:
        th = (rng.randint(-9000, 9000) / 100, rng.randint(-9000, 9000) / 100)
    if stim == "hygro":
        x0, x1 = float(rng.randint(0, 50)), float(rng.randint(50, 100))
        du = (x1 - x0) / 100
    else:
        x0, x1 = float(rng.randint(0, 50)), float(rng.randint(50, 150))
        du = x1 - x0
    return dict(cL=(cl1, cl2), cT=(ct1, ct2), E=(E1, E2), th=th, x0=x0, x1=x1, du=du,
                h=(rng.randint(200, 2000) / 1e4, rng.randint(200, 2000) / 1e4))


# ---------------------------------------------------------------- Lean side
LEAN_NAMES = ["timoshenkoCoefficient", "bilayerCurvature", "shearStrain", "axialStrain"]


def lean_values(lean, dr):
    rad = [math.radians(t) for t in dr["th"]]  # the only convention bridge: the code takes degrees, Lean radians
    eL = [c * dr["du"] for c in dr["cL"]]
    eT = [c * dr["du"] for c in dr["cT"]]
    ax = [lean("axialStrain", eL[i], eT[i], rad[i]) for i in (0, 1)]
    sh = [lean("shearStrain", eL[i], eT[i], rad[i]) for i in (0, 1)]
    h1, h2 = dr["h"]
    h, m, n = h1 + h2, h1 / h2, dr["E"][0] / dr["E"][1]
    C = lean("timoshenkoCoefficient", h, m, n)
    d_thk, d_12 = ax[0] - ax[1], sh[0] - sh[1]
    return dict(ax=ax, sh=sh, d_thk=d_thk, d_12=d_12, C=C,
                k_bend=lean("bilayerCurvature", h, m, n, d_thk), k_twist=lean("bilayerCurvature", h, m, n, d_12),
                eL=eL, eT=eT, rad=rad)


def equilibrium_kappa(dr, delta):
    """Solve the hypotheses of bilayerCurvature_ofEquilibrium for kappa (P2 = -P1 eliminated)."""
    h1, h2 = dr["h"]
    E1, E2 = dr["E"]
    S = (E1 * h1 ** 3 + E2 * h2 ** 3) / 12
    a11, a12, b1 = (h1 + h2) / 2, S, 0.0                       # moment: a11 P1 + a12 kappa = b1
    a21, a22, b2 = 1 / (E1 * h1) + 1 / (E2 * h2), -(h1 + h2) / 2, -delta  # compat: ... = eps2 - eps1
    det = a11 * a22 - a12 * a21
    return (a11 * b2 - a21 * b1) / det


def compare(lv, tissue, beta, S, response):
    """err / bound for each quantity the published code shares with the Lean definitions."""
    r = {}
    ratio = lambda err, bound: abs(err) / bound
    for i in (0, 1):
        r[f"eps_strip_{i+1}"] = ratio(tissue[f"eps_strip_{i+1}"] - lv["ax"][i], 5e-7 + 1e-12)
        r[f"delta_12_{i+1}"] = ratio(tissue[f"delta_12_{i+1}"] - lv["sh"][i], 5e-7 + 1e-12)
    r["delta_eps_thk"] = ratio(beta["delta_eps_thk"] - lv["d_thk"], 1e-6 + 1e-12)
    r["delta_eps_12"] = ratio(beta["delta_eps_12"] - lv["d_12"], 1e-6 + 1e-12)
    kb = 1e-6 * abs(lv["C"]) + 5e-7 + 1e-12
    act = lv["k_twist"] if response == "twist" else lv["k_bend"]
    r["kappa"] = ratio(S["kappa"] - act, kb)
    r["kappa_bend"] = ratio(S["kappa_bend"] - lv["k_bend"], kb)
    r["kappa_twist"] = ratio(S["kappa_twist"] - lv["k_twist"], kb)
    return r


TWIST_Q = ["eps_strip_1", "eps_strip_2", "delta_12_1", "delta_12_2", "delta_eps_thk", "delta_eps_12"]
KAPPA_Q = ["kappa", "kappa_bend", "kappa_twist"]
CONFIGS = [(s, b, r) for s in STIM for b in BRANCH for r in RESP]

# ---------------------------------------------------------------- main experiment
def main():
    rng = random.Random(SEED)
    draws = {}
    for cfg in CONFIGS:
        draws[cfg] = [draw_one(rng, cfg[0]) for _ in range(N)]
    anti = {(b, r): [draw_one(rng, "hygro", anti=True) for _ in range(N_ANTI)] for b in BRANCH for r in RESP}

    lean = LeanDefs(LEAN, LEAN_NAMES)
    src = load_sources()

    # unmutated configurations
    outs, lvs = {}, {}
    maxr = {q: 0.0 for q in TWIST_Q + KAPPA_Q}
    worst = {}
    eq_rel = 0.0
    for cfg in CONFIGS:
        stim, branch, resp = cfg
        outs[cfg], lvs[cfg] = [], []
        for dr in draws[cfg]:
            out = chain(src, branch, stim, resp, dr)
            lv = lean_values(lean, dr)
            outs[cfg].append(out)
            lvs[cfg].append(lv)
            for q, v in compare(lv, *out, resp).items():
                if v > maxr[q]:
                    maxr[q], worst[q] = v, dict(config=list(cfg), draw=dr)
            for k, dl in (("k_bend", lv["d_thk"]), ("k_twist", lv["d_12"])):
                keq = equilibrium_kappa(dr, dl)
                eq_rel = max(eq_rel, abs(keq - lv[k]) / (abs(lv[k]) + 1e-300))

    # antisymmetric sets (shearStrain_mismatch, axialStrain_mismatch)
    anti_thk, anti_12 = 0.0, 0.0
    for (branch, resp), lst in anti.items():
        for dr in lst:
            tissue, beta, S = chain(src, branch, "hygro", resp, dr)
            lv = lean_values(lean, dr)
            for q, v in compare(lv, tissue, beta, S, resp).items():
                if v > maxr[q]:
                    maxr[q], worst[q] = v, dict(config=["hygro", branch, resp, "antisymmetric"], draw=dr)
            anti_thk = max(anti_thk, abs(beta["delta_eps_thk"]) / (1e-6 + 1e-12))
            rhs = (dr["cL"][0] - dr["cT"][0]) * dr["du"] * math.sin(2 * lv["rad"][0])  # (epsL - epsT) sin 2 phi
            anti_12 = max(anti_12, abs(beta["delta_eps_12"] - rhs) / (1e-6 + 1e-12))

    # controls: fault injection
    LEAN_FAULTS = {
        "L1": ("shearStrain", "Real.sin (2 * φ)", "Real.sin φ"),
        "L2": ("axialStrain", "εL * (Real.cos φ) ^ 2 + εT * (Real.sin φ) ^ 2", "εL * (Real.sin φ) ^ 2 + εT * (Real.cos φ) ^ 2"),
        "L3": ("shearStrain", "1 / 2 * ", ""),
        "L4": ("timoshenkoCoefficient", "6 * (1 + m) ^ 2", "3 * (1 + m) ^ 2"),
        "L5": ("timoshenkoCoefficient", "(1 + m * n)", "(1 + m / n)"),
    }
    MAROM_FAULTS = {
        "M1": (["T_tis", "T_stack"], "math.sin(2.0 * r1)", "math.sin(r1)", None),
        "M2": (["T_tis", "T_stack"], "r2  = math.radians(", "r2  = (", None),
        "M3": (["S_elem", "S_print"], "(1.0 + m*n)", "(1.0 + m/n)", None),
        "M4": (["beta_twist", "beta_twist_prime"], "d_12  = d12_1 - d12_2", "d_12  = d12_1 + d12_2", "twist"),
    }
    twist_set, kappa_set = set(TWIST_Q), set(KAPPA_Q)
    det = {}  # fault -> {scope: {config: fraction}}

    def tally(fault, scope_q, cfg, ratios_per_draw):
        hits = sum(1 for r in ratios_per_draw if any(r[q] > 1 for q in scope_q))
        det.setdefault(fault, {}).setdefault("twist" if scope_q is TWIST_Q else "bilayer", {})["/".join(cfg)] = hits / len(ratios_per_draw)

    for name, (dname, old, new) in LEAN_FAULTS.items():
        lf = LeanDefs(LEAN, LEAN_NAMES, {dname: [(old, new)]})
        for cfg in CONFIGS:
            rs = [compare(lean_values(lf, dr), *out, cfg[2]) for dr, out in zip(draws[cfg], outs[cfg])]
            tally(name, TWIST_Q, cfg, rs)
            tally(name, KAPPA_Q, cfg, rs)
    for name, (scripts, old, new, only) in MAROM_FAULTS.items():
        msrc = load_sources({s: [(old, new)] for s in scripts})
        for cfg in CONFIGS:
            if only and cfg[2] != only:
                continue
            rs = [compare(lvs[cfg][i], *chain(msrc, cfg[1], cfg[0], cfg[2], dr), cfg[2]) for i, dr in enumerate(draws[cfg])]
            tally(name, TWIST_Q, cfg, rs)
            tally(name, KAPPA_Q, cfg, rs)

    RELEVANT = {"twist": ["L1", "L2", "L3", "M1", "M2", "M4"], "bilayer": ["L4", "L5", "M3"]}
    ctl = {sc: {f: min(det[f][sc].values()) for f in fs} for sc, fs in RELEVANT.items()}
    ctl_ok = {sc: all(v >= 0.9 for v in d.values()) for sc, d in ctl.items()}

    # ------------------------------------------------------------ write both result.json
    files = []
    for p in sorted(VENDOR.glob("*.py")) + [VENDOR / "LICENSE"]:
        b = p.read_bytes()
        files.append(dict(download_url=f"https://raw.githubusercontent.com/lamm-mit/CategoryTheoryDesign/{COMMIT}/"
                          + ("LICENSE" if p.name == "LICENSE" else f"gh_scripts/{p.name}"),
                          retrieved_at="2026-11-01", byte_size=len(b), sha256=hashlib.sha256(b).hexdigest()))
    total_draws = N * len(CONFIGS) + N_ANTI * len(anti)
    caveats_common = [
        "Output rounding is the only discrepancy permitted: the published scripts serialize bundle values with six decimals, so the comparison uses the pre-registered rounding-aware bound rather than machine precision. Agreement within that bound does not exclude differences smaller than 1e-6.",
        "The degrees-to-radians conversion of the fibre angle is done by this harness, not by Lean: the published code takes degrees and the Lean definitions take radians. The control M2 (radians dropped from one angle) shows the harness would see a mismatch of that kind inside the published code, but a wrong conversion in the harness itself would show as a failure of every draw.",
        "S_elem.py and S_print.py recompute the through-thickness and shear mismatches from the tissue-stage values themselves, so the final curvature does not depend on the beta reducer's output; the reducer only selects which one is active. The published pipeline is compositional in its interfaces but the mismatch is derived twice.",
        "The inputs cover ranges (thermal strains up to 4500 %) far beyond physical ones because the identities are algebraic and domain-independent; this checks the functions, not any material.",
        "The paper's measured-vs-predicted actuator results (its Table 4: predicted and measured opening or twist angles for four cases, n = 3 or 4 each, L = 100 mm, h1 = h2 = 0.6 mm) are not reproduced here: the repository ships only two of the four material panels (PA6-GF and PLA-CF; PA612-CF15 and PLA are missing), and the shipped G-code headers record a baseline curvature of 0.0763 1/cm, which is not the 0.0635 1/cm implied by the paper's predicted 36.4 degrees, with the two baseline raster angles swapped relative to the paper's Table 2, and 0.0000 1/cm for both thermal cases.",
        "Computational data only: it shows the Lean definitions and the published implementation agree, not that organisms follow the claim.",
    ]
    jobs = [
        (TWIST_DIR, "twist", TWIST_Q, max(maxr[q] for q in TWIST_Q),
         dict(max_ratio_by_quantity={q: maxr[q] for q in TWIST_Q},
              antisymmetric_max_ratio=dict(delta_eps_thk_zero=anti_thk, delta_eps_12_equals_epsL_minus_epsT_sin2phi=anti_12),
              fault_detection_min_fraction=ctl["twist"], fault_detection_all=det,
              worst_draws={q: worst.get(q) for q in TWIST_Q if maxr[q] > 1})),
        (BILAYER_DIR, "bilayer", KAPPA_Q, max(maxr[q] for q in KAPPA_Q),
         dict(max_ratio_by_quantity={q: maxr[q] for q in KAPPA_Q}, equilibrium_vs_lean_max_relative_difference=eq_rel,
              fault_detection_min_fraction=ctl["bilayer"], fault_detection_all=det,
              worst_draws={q: worst.get(q) for q in KAPPA_Q if maxr[q] > 1})),
    ]
    for d, sc, qs, headline, extra in jobs:
        res = json.loads((d / "result.json").read_text())
        passed = headline <= 1
        if sc == "twist":
            passed = passed and anti_thk <= 1 and anti_12 <= 1
        else:
            passed = passed and eq_rel <= 1e-9
        if not ctl_ok[sc]:
            verdict, reason = "inconclusive", "other"
        else:
            verdict, reason = ("supports" if passed else "refutes"), None
        res["datasets"][0]["files"] = files
        res["status"] = "complete"
        res["method"] = (
            f"Seed {SEED}. Each of {len(CONFIGS)} configurations (stimulus x Nat/Art branch x beta_bend/beta_twist) got {N} random draws, plus "
            f"{N_ANTI} antisymmetric draws per branch and response ({total_draws} draws in all). For each draw the published Grasshopper "
            "components in vendor/ (commit " + COMMIT[:9] + ") were exec'd unmodified in the wiring of gh_scripts/README.md, and the same "
            "inputs were evaluated with shearStrain, axialStrain, timoshenkoCoefficient and bilayerCurvature parsed from "
            "ThompsonLaws/Hygromorphs.lean by lean_eval.py. Differences were divided by the pre-registered rounding bound. The equilibrium "
            "equations of bilayerCurvature_ofEquilibrium were solved as a 2x2 linear system. Nine faults were injected one at a time as controls.")
        res["measured"] = dict(
            value=headline, unit="max |published - Lean| / rounding bound over all draws (<= 1 passes)",
            n=total_draws, uncertainty="deterministic given the seed; no sampling error is claimed",
            extra=extra)
        res["verdict"] = verdict
        if reason:
            res["reason"] = reason
        res["confidence"] = 0.95 if verdict != "inconclusive" else 0.5
        res["caveats"] = caveats_common
        (d / "result.json").write_text(json.dumps(res, indent=2, ensure_ascii=False) + "\n")
        print(sc, "verdict", verdict, "headline max ratio", round(headline, 4), "controls", ctl[sc])
    print("max ratios", {q: round(v, 4) for q, v in maxr.items()})
    print("antisym", anti_thk, anti_12, "equilibrium rel diff", eq_rel)


if __name__ == "__main__":
    main()
