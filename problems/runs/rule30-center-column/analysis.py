#!/usr/bin/env python3
"""Assemble the pre-registered tests (PREREG.md) into derived tables and result.json.

usage: analysis.py COLUMN.bin L
Reads derived/stats_full.json and derived/stats_1e6.json (written by stats.c), recomputes the
simple statistics independently with numpy as a cross-check, fetches the Wolfram sources (T5), applies
the verdict rule fixed in PREREG.md and writes derived/*, result.json.  Needs numpy and network.
"""
import csv, datetime, hashlib, json, math, os, re, sys, urllib.request, html

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.environ.get("WORK", "/tmp/rule30-work")
import numpy as np


def sha256(b): return hashlib.sha256(b).hexdigest()
def utcnow(): return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def fetch(url, name):
    req = urllib.request.Request(url, headers={"User-Agent": "delphisci-rule30-run"})
    data = urllib.request.urlopen(req, timeout=90).read()
    return {"download_url": url, "retrieved_at": utcnow(), "byte_size": len(data), "sha256": sha256(data), "_raw": data, "name": name}


def text_of(raw):
    t = raw.decode("utf-8", "ignore")
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t)


def main(colpath, L):
    L = int(L)
    raw = open(colpath, "rb").read()
    bits = np.unpackbits(np.frombuffer(raw, dtype=np.uint8))[:L].astype(np.int64)
    assert len(bits) == L
    col_sha = sha256(raw)
    full = json.load(open(os.path.join(HERE, "derived/stats_full.json")))
    mil = json.load(open(os.path.join(HERE, "derived/stats_1e6.json")))
    assert full["L"] == L

    # ---- T1: monobit (analytic) and numpy cross-check of the C statistics
    def t1(Lw):
        ones = int(bits[:Lw].sum()); z = (2 * ones - Lw) / math.sqrt(Lw)
        return {"L": Lw, "ones": ones, "density": ones / Lw, "z": z, "p": math.erfc(abs(z) / math.sqrt(2)),
                "deviation": ones / Lw - 0.5, "sigma_density": 0.5 / math.sqrt(Lw)}
    T1 = t1(L); T1m = t1(1000001)
    assert T1["ones"] == int(full["observed"]["ones"]) and T1m["ones"] == int(mil["observed"]["ones"])

    # ---- block table (T3) and numpy cross-check of chi2
    B = L // 1_000_000
    rows = []
    for b in range(B):
        o = int(bits[b * 10**6:(b + 1) * 10**6].sum()); rows.append((b, o, (2 * o - 10**6) / 1000.0))
    chi2 = sum(r[2] ** 2 for r in rows)
    assert abs(chi2 - full["observed"]["block_chi2"]) < 1e-6 * max(1, chi2)
    os.makedirs(os.path.join(HERE, "derived"), exist_ok=True)
    with open(os.path.join(HERE, "derived/block_z.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["block", "start_t", "ones", "z"])
        for b, o, z in rows: w.writerow([b, b * 10**6, o, "%.4f" % z])

    # ---- running density table (T2 context): powers-of-two-ish and every 5e6 bits
    cs = np.cumsum(bits)
    ms = sorted(set([4096 * 2 ** j for j in range(0, 40) if 4096 * 2 ** j <= L] + [10**k * f for k in range(3, 9) for f in (1, 2, 5) if 10**k * f <= L] +
                    list(range(5_000_000, L + 1, 5_000_000)) + [L]))
    with open(os.path.join(HERE, "derived/running_density.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["m", "ones", "s_m", "s_m_over_sqrt_m", "lil_ratio"])
        for m in ms:
            o = int(cs[m - 1]); s = 2 * o - m
            lil = abs(s) / math.sqrt(2 * m * math.log(math.log(m))) if m > 15 else float("nan")
            w.writerow([m, o, s, "%.4f" % (s / math.sqrt(m)), "%.4f" % lil])

    # ---- Monte Carlo p-values
    def pu(S, k): return S["null"][k]["p_upper"]
    def p2(S, k): return min(1.0, 2 * min(S["null"][k]["p_upper"], S["null"][k]["p_lower"]))
    T2 = {"lambda": full["observed"]["lil_ratio_max"], "p": pu(full, "lil_ratio_max"),
          "null_mean": full["null"]["lil_ratio_max"]["mean"], "null_q99": full["null"]["lil_ratio_max"]["q99"],
          "max_abs_s_over_sqrt_m": full["observed"]["max_abs_s_over_sqrt_m"],
          "p_claim_window": pu(mil, "lil_ratio_max"), "lambda_claim_window": mil["observed"]["lil_ratio_max"]}
    T3 = {"blocks": B, "chi2": chi2, "p_two_sided": p2(full, "block_chi2"), "ks": full["observed"]["block_ks"], "p_ks": pu(full, "block_ks"),
          "max_abs_z": full["observed"]["block_max_abs_z"], "frac_abs_z_gt_2": full["observed"]["block_frac_abs_z_gt_2"],
          "p_max_abs_z": pu(full, "block_max_abs_z"), "null_chi2_mean": full["null"]["block_chi2"]["mean"]}
    third = L // 3; third_m = 1000001 // 3
    T4a = {"L": L, "bound": third, "min_istar_p_le_L3": int(full["observed"]["min_istar_over_p_le_L3"])}
    T4a["pass"] = T4a["min_istar_p_le_L3"] >= third
    T4b = {"L": 1000001, "bound": third_m, "min_istar_p_le_L3": int(mil["observed"]["min_istar_over_p_le_L3"])}
    T4b["pass"] = T4b["min_istar_p_le_L3"] >= third_m
    Rm = int(full["observed"]["max_suffix_agreement_R"])
    T4c = {"R": Rm, "argmax_p": int(full["observed"]["argmax_p_of_R"]), "excluded_p_plus_q_le": L - 1 - Rm,
           "null_R_mean": full["null"]["max_suffix_agreement_R"]["mean"], "null_R_max": full["null"]["max_suffix_agreement_R"]["max"],
           "p_upper": pu(full, "max_suffix_agreement_R"), "log2_L": math.log2(L)}

    # ---- secondary battery
    sec = {}
    for k in ["autocorr_max_abs_z", "autocorr_sum_z2"] + ["psi2_m%02d" % m for m in range(1, 21)] + ["max_suffix_agreement_R", "longest_run"]:
        sec[k] = {"observed": full["observed"][k], "null_mean": full["null"][k]["mean"], "null_sd": full["null"][k]["sd"], "p_upper": pu(full, k), "p_lower": full["null"][k]["p_lower"]}
    sec["runs_z"] = {"observed": full["observed"]["runs_z"], "null_mean": full["null"]["runs_z"]["mean"], "null_sd": full["null"]["runs_z"]["sd"], "p_abs": full["null"]["runs_z"]["p_abs_upper"]}
    flags = [k for k, v in sec.items() if (v.get("p_upper", v.get("p_abs"))) <= 0.001 and k != "longest_run"]
    # longest_run is reported but is not among the registered flagged statistics
    bm = full.get("berlekamp_massey")

    # ---- T5 sources
    srcs = {}
    for name, url in [("rule30prize_org", "https://www.rule30prize.org/"),
                      ("wolfram_announcement_2019", "https://writings.stephenwolfram.com/2019/10/announcing-the-rule-30-prizes/"),
                      ("data_repository_billion_bits", "https://datarepository.wolframcloud.com/resources/A-Billion-Bits-of-the-Center-Column-of-the-Rule-30-Cellular-Automaton")]:
        try:
            d = fetch(url, name); t = text_of(d.pop("_raw"))
            d["sentences"] = [m.group(0).strip() for m in re.finditer(r"[^.]*\b(?:billion|million)\b[^.]*\.", t) if len(m.group(0)) < 300 and "&#10005" not in m.group(0)][:5]
            d["mentions_2_billion"] = bool(re.search(r"\b(2 billion|two billion|2,000,000,000|2\.0\s*billion)\b", t, re.I))
        except Exception as e:  # noqa
            d = {"download_url": url, "error": repr(e)}
        srcs[name] = d
    json.dump(srcs, open(os.path.join(HERE, "derived/sources.json"), "w"), indent=1)

    # ---- verdict (rule fixed in PREREG.md)
    prim = [T1["p"], T2["p"], T3["p_two_sided"]]
    if L < 10**7: verdict, why = "inconclusive", "underpowered"
    elif not T4a["pass"] or not T4b["pass"]: verdict, why = "refutes", "apparent eventual period within the window; must be re-checked"
    elif min(prim) < 1e-6: verdict, why = "refutes", "primary p < 1e-6"
    elif min(prim) <= 0.01 or len(flags) >= 2: verdict, why = "mixed", "primary p in (1e-6, 0.01] or >= 2 secondary flags"
    else: verdict, why = "supports", None

    summary = {"L": L, "column_sha256": col_sha, "T1": T1, "T1_claim_window": T1m, "T2": T2, "T3": T3, "T4a": T4a, "T4b": T4b, "T4c": T4c,
               "secondary": sec, "secondary_flags": flags, "berlekamp_massey": bm, "verdict": verdict, "reason": why,
               "primary_p": {"T1": T1["p"], "T2": T2["p"], "T3": T3["p_two_sided"]}}
    json.dump(summary, open(os.path.join(HERE, "derived/summary.json"), "w"), indent=1)

    # ---- result.json
    oeis = [{"download_url": "https://oeis.org/A051023/b051023.txt", "sha256_note": "see derived/verify.log", "role": "terms 0..100000 of A051023"}]
    prereg = open(os.path.join(HERE, "PREREG.md"), "rb").read()
    res = {
        "claim_id": "wolfram2002-ch02-05",
        "claim_iri": "https://w3id.org/delphi/resource/claim/wolfram2002-ch02-05",
        "project": "wolfram-nks",
        "problem": "rule30-center-column",
        "status": "complete",
        "hypothesis": "The Rule 30 center column from a single black cell is not eventually periodic within its first %d cells and its density of ones is 1/2 with fluctuations of an i.i.d. fair sequence." % L,
        "pass_criterion": "Pre-registered in PREREG.md (sha256 %s): T4a/T4b no eventual period (p, q) with p, q <= L/3 in the computed window and in the first 10^6 cells; monobit z, running-density LIL maximum and 10^6-block chi-square each with Monte Carlo/analytic p > 0.01; at most one secondary flag (p <= 0.001) among autocorrelation, pattern, runs and suffix-agreement statistics." % sha256(prereg),
        "fail_criterion": "Pre-registered: a confirmed eventual period within the window, or any primary p < 1e-6 refutes; a primary p in (1e-6, 0.01] or two or more secondary flags gives mixed; L < 10^7 or a failed validity gate gives inconclusive.",
        "planned_datasets": ["rule30-center-column-generated", "oeis-a051023-bfile", "wolfram-rule30-prize-pages"],
        "test_contract": {
            "expected_observation": "No eventual period within the window and every statistic inside the range of fair-coin PRNG sequences of the same length.",
            "disconfirming_observation": "A period or an eventual period within the window, or a primary statistic far outside the PRNG null range.",
            "admissible_datasets": "Exact output of the Rule 30 recurrence from a single black cell, validated against an independent slow implementation and OEIS A051023.",
            "inference_method": "Exact suffix-agreement scan for periods; monobit z (normal), LIL running-density maximum, block chi-square against 1000 PRNG null sequences; secondary statistics against the same null.",
        },
        "interpretation": "The claim says 'first million steps'; this run uses %d cells (a larger window, scope extension noted) and also reports the first 10^6+1 cells separately. 'Never repeats' is read as 'not eventually periodic within the window'; 'no meaningful deviation from perfect randomness' is read as the registered statistics being inside the null range. Passing cannot show randomness or prove any Prize statement." % L,
        "datasets": [
            {"id": "rule30-center-column-generated", "name": "Rule 30 center column generated by rule30.c", "landing_url": None, "doi": None, "version": "N=%d" % (L - 1), "license": "n/a (computed)",
             "files": [{"download_url": None, "generating_command": "rule30 %d -j 6 -o column.bin" % (L - 1), "retrieved_at": utcnow(), "byte_size": len(raw), "sha256": col_sha}],
             "role": "the data under test; packed MSB-first, c[0]=1"},
            {"id": "oeis-a051023-bfile", "name": "OEIS A051023 b-file", "landing_url": "https://oeis.org/A051023", "doi": None, "version": None, "license": "CC BY-NC 3.0 (OEIS)",
             "files": oeis, "role": "independent check of the first 100001 terms"},
            {"id": "wolfram-rule30-prize-pages", "name": "Wolfram Rule 30 Prize pages", "landing_url": "https://www.rule30prize.org/", "doi": None, "version": None, "license": "n/a",
             "files": [{k: v for k, v in d.items() if k in ("download_url", "retrieved_at", "byte_size", "sha256")} for d in srcs.values()], "role": "statements of the Prize problems and of the published computed horizon"},
        ],
        "method": "rule30.c (bit-parallel, light-cone trimmed, 6 threads) generated %d cells; verify.sh checked it against a slow big-integer reference and OEIS A051023. stats.c computed the pre-registered statistics on the column and on 1000 xoshiro256** null sequences of equal length; analysis.py cross-checked ones and block chi-square with numpy and assembled the verdict by the registered rule." % L,
        "measured": {"value": T1["density"], "unit": "fraction of ones", "n": L, "uncertainty": "1 sigma under H0 = %.3e" % T1["sigma_density"],
                     "extra": {k: summary[k] for k in ("T1", "T1_claim_window", "T2", "T3", "T4a", "T4b", "T4c", "secondary_flags", "berlekamp_massey", "primary_p", "column_sha256")}},
        "verdict": verdict,
        "confidence": 0.9 if verdict == "supports" else 0.6,
        "data_kind": "computational",
        "caveats": [
            "Computational evidence about a mathematical sequence; it says nothing about organisms and proves none of the three Prize problems.",
            "N = %d is far short of the approach's 10^10 to 10^11 target and %.0f times shorter than the billion bits Wolfram published; the period exclusion adds nothing beyond that published check." % (L - 1, 1e9 / L),
            "The period test excludes only eventual periods with p + q <= L - 1 - R inside the window, nothing larger.",
            "Statistics were tested against a PRNG null, which is itself only pseudorandom.",
        ],
        "agent": {"kind": "local-agent", "model": "claude-sonnet-5.5", "run": "problems/runs/rule30-center-column", "date": "2026-11-01"},
    }
    if why: res["reason"] = why
    json.dump(res, open(os.path.join(HERE, "result.json"), "w"), indent=1)
    print(json.dumps({k: summary[k] for k in ("L", "verdict", "reason", "primary_p", "secondary_flags")}, indent=1))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
