"""Cross-check of thompson1917-ch03-07 against the collaborator swarm's test of the same claim (added 2026-10-31 after the
result; the pre-registered verdict is unchanged).

The collaborator (origin/main, run cursor/claim-tests-thompson-efb7) reports a pooled individual-level exponent of 2.41 on
NHANES 2007-2018, ages 0 to 19.99 with recumbent length under 24 months, and a 'mixed' verdict. This test used NHANES
2013-2018, ages 2 to 19 (standing stature), age-bin means, and 'supports'. This script (1) refits the exponent on the
individuals of this test's own sample, so that binning versus individuals is tested directly, and (2) reads the
collaborator's result.json from origin/main, without merging anything, and records their pooled and age-window slopes.

Reads data/*.xpt via analysis.load(); writes derived/cross_check.json.
"""
import json
import os
import subprocess

import numpy as np
from scipy import stats

from analysis import DERIVED, HERE, load

ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
THEIR_PATH = "claim-tests/thompson-growth-form/thompson1917-ch03-07/result.json"


def git(*a):
    return subprocess.check_output(["git", *a], cwd=ROOT, text=True)


def fit(d):
    x = np.log(d["BMXHT"].to_numpy())
    y = np.log(d["BMXWT"].to_numpy())
    r = stats.linregress(x, y)
    t = stats.t.ppf(0.975, len(d) - 2)
    W = d["WTMEC2YR"].to_numpy()
    xm, ym = np.average(x, weights=W), np.average(y, weights=W)
    bw = float(np.sum(W * (x - xm) * (y - ym)) / np.sum(W * (x - xm) ** 2))
    return {"n_individuals": int(len(d)), "ols_exponent": float(r.slope), "ci95": [float(r.slope - t * r.stderr), float(r.slope + t * r.stderr)],
            "r2": float(r.rvalue ** 2), "survey_weighted_exponent": bw}


def main():
    df = load()
    ours = {"ages": "2-19 completed years, standing stature, NHANES 2013-2018 (this test's sample)",
            "pooled": fit(df), "male": fit(df[df["RIAGENDR"] == 1]), "female": fit(df[df["RIAGENDR"] == 2])}
    sha = git("rev-parse", "origin/main").strip()
    their_commit = git("log", "-1", "--format=%H %cI", "origin/main", "--", THEIR_PATH).strip()
    theirs_raw = json.loads(git("show", f"origin/main:{THEIR_PATH}"))
    ex = theirs_raw["measured"]["extra"]
    theirs = {"source": f"origin/main {sha[:12]} ({their_commit}), {THEIR_PATH}", "run": theirs_raw.get("agent", {}).get("run"),
              "verdict": theirs_raw["verdict"], "scope": "NHANES 2007-2018, ages 0 to 19.99, recumbent length under 24 months, individuals pooled",
              "pooled_0_19_individuals": ex["pooled"]["individuals"], "slope_by_age_window": ex["slope_by_age_window"],
              "age_median_curve_0_19": ex["pooled"]["age_median_curve"]}
    out = {"ours_individual_level": ours, "theirs": theirs,
           "reading": ("Binning versus individuals is not the cause of the difference: on this test's own sample the individual-level exponent "
                       f"({ours['pooled']['ols_exponent']:.3f}) is within 0.03 of the age-bin exponents. The cause is the age range. The "
                       f"collaborator's 2-20 year window gives {ex['slope_by_age_window']['2-20yr']['ols_slope']:.3f}, which reproduces this test, "
                       f"while their 0-2 year window gives {ex['slope_by_age_window']['0-2yr']['ols_slope']:.3f} and pulls their pooled 0-19 "
                       f"exponent to {ex['pooled']['individuals']['ols_slope']:.3f}, below the 2.5 edge of the band both tests pre-registered. "
                       "The verdict is therefore conditional on the pre-registered scope (ages 2-19): including infancy makes it 'mixed'.")}
    os.makedirs(DERIVED, exist_ok=True)
    json.dump(out, open(os.path.join(DERIVED, "cross_check.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
