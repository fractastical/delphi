"""Post-hoc discriminating-power check for thompson1917-ch03-07 (added 2026-10-31 after the pre-registered result; the
verdict is unchanged).

Question: would the pre-registered rule (free exponent in [2.5, 3.5] and cubic-model R^2 >= 0.90, both sexes) have
rejected a wrong law? Simulate age-bin mean weights from the observed mean heights under the cube law and under
perturbed exponents (2, 2.5, 3.5, 4) with the observed log-scale scatter of the bins around the fitted power law, apply the
rule from analysis.py unchanged, and report the pass fraction per exponent. A simulation result shows what the rule would
do, nothing more.

Reads data/*.xpt via analysis.load(); writes derived/perturbation.json.
"""
import json
import os

import numpy as np
from scipy import stats

from analysis import DERIVED, load, per_sex

N_SIM = 2000
EXPONENTS = [3.0, 2.0, 2.5, 3.5, 4.0]


def rule_from_bins(h, w):
    lw, lh = np.log(w), np.log(h)
    free = stats.linregress(lh, lw)
    logk = float(np.mean(lw - 3 * lh))
    pred = np.exp(logk) * h ** 3
    r2 = 1 - float(np.sum((w - pred) ** 2)) / float(np.sum((w - w.mean()) ** 2))
    return bool(2.5 <= free.slope <= 3.5 and r2 >= 0.90), float(free.slope), float(r2)


def main():
    df = load()
    rng = np.random.default_rng(20261031)
    out = {"n_simulations_per_exponent": N_SIM, "sexes": {}}
    for code, name in ((1, "male"), (2, "female")):
        bins, r = per_sex(df[df["RIAGENDR"] == code])
        h = bins["mean_height_cm"].to_numpy()
        w = bins["mean_weight_kg"].to_numpy()
        lw, lh = np.log(w), np.log(h)
        free = stats.linregress(lh, lw)
        resid_sd = float(np.std(lw - (free.intercept + free.slope * lh), ddof=2))
        sex = {"observed": {"free_exponent_b": r["free_exponent_b"], "cubic_model_r2": r["cubic_model_r2_original_scale"], "passes": bool(2.5 <= r["free_exponent_b"] <= 3.5 and r["cubic_model_r2_original_scale"] >= 0.90),
                            "n_age_bins": int(len(bins)), "residual_sd_log_weight": resid_sd}, "simulated": {}}
        for b in EXPONENTS:
            passes, slopes, r2s = 0, [], []
            for _ in range(N_SIM):
                lw_sim = lw.mean() + b * (lh - lh.mean()) + rng.normal(0, resid_sd, len(lh))
                ok, s, r2 = rule_from_bins(h, np.exp(lw_sim))
                passes += ok
                slopes.append(s)
                r2s.append(r2)
            sex["simulated"][str(b)] = {"true_exponent": b, "pass_fraction": passes / N_SIM, "mean_fitted_exponent": float(np.mean(slopes)),
                                        "mean_cubic_r2": float(np.mean(r2s))}
        out["sexes"][name] = sex
    out["reading"] = ("The rule passes under the cube law and under exponents inside the pre-registered band, and fails under an exponent of 2 "
                      "(surface scaling) or 4 at the fractions shown, with the observed heights and the observed bin scatter. The band was "
                      "pre-registered as a tolerance for Thompson's 'mainly (though not wholly)'; this check shows what it can and cannot reject.")
    os.makedirs(DERIVED, exist_ok=True)
    json.dump(out, open(os.path.join(DERIVED, "perturbation.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
